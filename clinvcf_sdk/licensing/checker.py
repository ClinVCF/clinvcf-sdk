"""Vérificateur de licence runtime — Ed25519 + grace period.

Format du JWT licence émis par ClinStore (claims) :

    {
      "iss": "clinstore.fdevelopment.io",
      "aud": "<module_id>",
      "sub": "<user_id_anonymized>",
      "iat": 1714672800,
      "exp": 1746208800,
      "tier": "pro" | "community" | "team" | "enterprise",
      "quota_per_month": 5 | null,
      "license_id": "lic_abc123",
      "module_version_constraint": ">=1.0.0,<2.0.0"
    }

Signature : Ed25519 ; vérifiée avec la clé publique Fdevelopment embarquée
dans le SDK (publication sécurisée — la clé publique peut fuiter sans risque,
seule la clé privée doit être protégée chez Fdevelopment).
"""
from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clinvcf_sdk.exceptions import (
    LicenseExpiredError,
    LicenseInvalidError,
)
from clinvcf_sdk.licensing.tier import Tier

logger = logging.getLogger(__name__)

CLINSTORE_PUBLIC_KEY_BASE64 = "REPLACE_WITH_REAL_PUBLIC_KEY_AT_RELEASE_TIME"

LICENSE_PING_INTERVAL_SECONDS = 24 * 3600
DEFAULT_GRACE_PERIOD_DAYS = 30


@dataclass(slots=True)
class LicenseInfo:
    """Résultat de la vérification d'une licence."""

    is_valid: bool
    reason: str = ""
    tier: Tier | None = None
    license_id: str | None = None
    user_id: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    last_verified_at: datetime | None = None
    grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
    quota_per_month: int | None = None
    quota_exceeded: bool = False
    raw_claims: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class LicenseChecker:
    """Vérifie une licence JWT Ed25519 émise par ClinStore.

    Args:
        module_id: ID du module dont on vérifie la licence (doit matcher
            le claim ``aud`` du JWT).
        license_token: JWT signé fourni par ClinStore au client.
        cache_dir: Répertoire où stocker le cache local de la dernière
            vérification réussie (pour la grace period offline).
        grace_period_days: Durée en jours pendant laquelle le module
            peut tourner sans contacter ClinStore. Configurable par module
            via le manifest (clé ``compatibility.license_grace_period_days``).
        public_key_base64: Clé publique Ed25519 de ClinStore au format
            base64. Par défaut : ``CLINSTORE_PUBLIC_KEY_BASE64`` du SDK.
        clock_now: Fonction retournant l'heure courante (paramétrable
            pour les tests).
    """

    def __init__(
        self,
        module_id: str,
        license_token: str | None,
        *,
        cache_dir: str | Path | None = None,
        grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS,
        public_key_base64: str | None = None,
        clock_now=None,
    ) -> None:
        self.module_id = module_id
        self.license_token = license_token
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.grace_period_days = grace_period_days
        self.public_key_base64 = (
            public_key_base64 or CLINSTORE_PUBLIC_KEY_BASE64
        )
        self.clock_now = clock_now or (lambda: datetime.now(timezone.utc))

    def verify(self, *, allow_offline: bool = True) -> LicenseInfo:
        """Vérifie la licence et retourne les infos associées.

        Args:
            allow_offline: Si True (défaut), accepte un cache local valide
                même si ClinStore est inaccessible.

        Returns:
            ``LicenseInfo`` avec ``is_valid`` reflétant le verdict.

        Raises:
            LicenseInvalidError: Si la licence est cryptographiquement invalide.
            LicenseExpiredError: Si la licence a expiré et que la grace
                period offline est elle-même dépassée.
        """
        if not self.license_token:
            return LicenseInfo(
                is_valid=False,
                reason="Aucun token de licence fourni.",
            )

        try:
            claims = self._verify_signature(self.license_token)
        except LicenseInvalidError:
            cached = self._load_cached_info()
            if cached and allow_offline and self._is_within_grace(cached):
                cached.warnings.append(
                    "Licence non vérifiable en ligne ; utilisation du cache "
                    f"local (valide jusqu'au "
                    f"{(cached.last_verified_at or self.clock_now()).strftime('%Y-%m-%d')}"
                    f" + {self.grace_period_days} jours)."
                )
                return cached
            raise

        info = self._claims_to_info(claims)
        info.last_verified_at = self.clock_now()
        info.is_valid = self._is_active(info)
        if not info.is_valid and info.expires_at and info.expires_at < self.clock_now():
            info.reason = (
                f"Licence expirée le {info.expires_at.strftime('%Y-%m-%d')}."
            )

        self._save_cached_info(info)
        return info

    def should_ping_now(self) -> bool:
        """True si plus de 24h depuis la dernière vérification en ligne."""
        cached = self._load_cached_info()
        if cached is None or cached.last_verified_at is None:
            return True
        delta = (self.clock_now() - cached.last_verified_at).total_seconds()
        return delta >= LICENSE_PING_INTERVAL_SECONDS

    def _verify_signature(self, token: str) -> dict[str, Any]:
        """Vérifie la signature Ed25519 et retourne les claims."""
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )
        except ImportError as e:
            raise LicenseInvalidError(
                "La bibliothèque 'cryptography' est requise pour la "
                "vérification des licences Ed25519. "
                "Installer avec : pip install cryptography",
                code="cryptography_missing",
            ) from e

        parts = token.split(".")
        if len(parts) != 3:
            raise LicenseInvalidError(
                "Format JWT invalide (3 segments attendus).",
                code="malformed_jwt",
            )

        header_b64, payload_b64, signature_b64 = parts

        try:
            header = json.loads(_b64url_decode(header_b64))
        except (ValueError, json.JSONDecodeError) as e:
            raise LicenseInvalidError(
                f"En-tête JWT illisible : {e}", code="invalid_header"
            ) from e

        if header.get("alg") != "EdDSA":
            raise LicenseInvalidError(
                f"Algorithme non supporté : {header.get('alg')!r} "
                "(EdDSA attendu).",
                code="invalid_algorithm",
            )

        signed_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature = _b64url_decode(signature_b64)

        try:
            public_key_bytes = base64.b64decode(self.public_key_base64)
            pub = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            pub.verify(signature, signed_input)
        except InvalidSignature as e:
            raise LicenseInvalidError(
                "Signature de la licence invalide.",
                code="invalid_signature",
            ) from e
        except Exception as e:
            raise LicenseInvalidError(
                f"Erreur de vérification cryptographique : {e}",
                code="crypto_error",
            ) from e

        try:
            claims = json.loads(_b64url_decode(payload_b64))
        except (ValueError, json.JSONDecodeError) as e:
            raise LicenseInvalidError(
                f"Payload JWT illisible : {e}",
                code="invalid_payload",
            ) from e

        return claims

    def _claims_to_info(self, claims: dict[str, Any]) -> LicenseInfo:
        if claims.get("aud") != self.module_id:
            raise LicenseInvalidError(
                f"Cette licence n'est pas valide pour le module "
                f"{self.module_id!r} (audience: {claims.get('aud')!r}).",
                code="audience_mismatch",
            )

        try:
            tier = Tier(claims["tier"])
        except (KeyError, ValueError) as e:
            raise LicenseInvalidError(
                f"Tier de licence invalide : {claims.get('tier')!r}",
                code="invalid_tier",
            ) from e

        issued_at = (
            datetime.fromtimestamp(claims["iat"], tz=timezone.utc)
            if "iat" in claims
            else None
        )
        expires_at = (
            datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
            if "exp" in claims
            else None
        )

        return LicenseInfo(
            is_valid=False,
            tier=tier,
            license_id=claims.get("license_id"),
            user_id=claims.get("sub"),
            issued_at=issued_at,
            expires_at=expires_at,
            grace_period_days=self.grace_period_days,
            quota_per_month=claims.get("quota_per_month"),
            raw_claims=claims,
        )

    def _is_active(self, info: LicenseInfo) -> bool:
        now = self.clock_now()
        if info.expires_at and info.expires_at < now:
            return False
        if info.issued_at and info.issued_at > now + _SKEW:
            return False
        return True

    def _is_within_grace(self, info: LicenseInfo) -> bool:
        if info.last_verified_at is None:
            return False
        elapsed_days = (self.clock_now() - info.last_verified_at).days
        return elapsed_days <= self.grace_period_days

    def _cache_path(self) -> Path | None:
        if self.cache_dir is None:
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f"{self.module_id}.license_cache.json"

    def _load_cached_info(self) -> LicenseInfo | None:
        path = self._cache_path()
        if path is None or not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        try:
            return LicenseInfo(
                is_valid=bool(data.get("is_valid", False)),
                reason=data.get("reason", ""),
                tier=Tier(data["tier"]) if data.get("tier") else None,
                license_id=data.get("license_id"),
                user_id=data.get("user_id"),
                issued_at=_parse_dt(data.get("issued_at")),
                expires_at=_parse_dt(data.get("expires_at")),
                last_verified_at=_parse_dt(data.get("last_verified_at")),
                grace_period_days=int(data.get("grace_period_days", self.grace_period_days)),
                quota_per_month=data.get("quota_per_month"),
                quota_exceeded=bool(data.get("quota_exceeded", False)),
                raw_claims=data.get("raw_claims", {}),
                warnings=list(data.get("warnings", [])),
            )
        except Exception:
            return None

    def _save_cached_info(self, info: LicenseInfo) -> None:
        path = self._cache_path()
        if path is None:
            return
        try:
            payload = {
                "is_valid": info.is_valid,
                "reason": info.reason,
                "tier": info.tier.value if info.tier else None,
                "license_id": info.license_id,
                "user_id": info.user_id,
                "issued_at": info.issued_at.isoformat() if info.issued_at else None,
                "expires_at": info.expires_at.isoformat() if info.expires_at else None,
                "last_verified_at": (
                    info.last_verified_at.isoformat()
                    if info.last_verified_at
                    else None
                ),
                "grace_period_days": info.grace_period_days,
                "quota_per_month": info.quota_per_month,
                "quota_exceeded": info.quota_exceeded,
                "raw_claims": info.raw_claims,
                "warnings": info.warnings,
            }
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("Échec de l'écriture du cache de licence : %s", e)


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


from datetime import timedelta as _td

_SKEW = _td(seconds=60)
