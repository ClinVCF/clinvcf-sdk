"""Source de données hybride : snapshot embarqué + refresh distant optionnel.

Trois modes :

* ``EMBEDDED`` — utilise uniquement le snapshot livré avec le module.
  Aucun appel réseau. Recommandé pour les déploiements air-gapped.
* ``REMOTE`` — tente un refresh distant à chaque chargement. Bascule sur
  embedded en cas d'échec. Adapté aux installations avec connectivité
  fiable et besoin de fraîcheur maximale.
* ``HYBRID`` (défaut) — utilise embedded par défaut, refresh périodique
  en arrière-plan. Compromis recommandé pour la majorité des cas.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from clinvcf_sdk.exceptions import DataSourceError

logger = logging.getLogger(__name__)


class DataSourceMode(str, Enum):
    EMBEDDED = "embedded"
    REMOTE = "remote"
    HYBRID = "hybrid"


@dataclass(slots=True)
class CacheManifest:
    """Méta-données d'un cache local de données distantes."""

    source_name: str
    fetched_at: datetime
    etag: str | None
    sha256: str
    remote_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "fetched_at": self.fetched_at.isoformat(),
            "etag": self.etag,
            "sha256": self.sha256,
            "remote_url": self.remote_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheManifest":
        fetched = datetime.fromisoformat(data["fetched_at"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return cls(
            source_name=data["source_name"],
            fetched_at=fetched,
            etag=data.get("etag"),
            sha256=data["sha256"],
            remote_url=data["remote_url"],
        )


class HybridDataSource:
    """Source de données hybride avec fallback gracieux.

    Args:
        name: Identifiant logique de la source (ex. "cpic_guidelines").
        embedded_dir: Répertoire contenant le snapshot embarqué (JSON).
        remote_url: URL de l'API officielle (optionnelle si mode=EMBEDDED).
        cache_dir: Répertoire local pour stocker les snapshots téléchargés.
        mode: ``EMBEDDED``, ``REMOTE`` ou ``HYBRID``.
        refresh_interval_days: Période entre refreshes automatiques en
            mode ``HYBRID``. Par défaut 30j.
        fetcher: Fonction de fetch personnalisée (sinon utilise ``requests``).
            Signature : ``fetcher(url, etag=None) -> tuple[bytes, dict]``
            où le dict est {"etag": str | None, "status": int}.
        clock_now: Fonction d'horloge (paramétrable pour tests).
    """

    def __init__(
        self,
        name: str,
        *,
        embedded_dir: str | Path | None = None,
        remote_url: str | None = None,
        cache_dir: str | Path | None = None,
        mode: DataSourceMode | str = DataSourceMode.HYBRID,
        refresh_interval_days: int = 30,
        fetcher: Callable | None = None,
        clock_now: Callable | None = None,
    ) -> None:
        self.name = name
        self.embedded_dir = Path(embedded_dir) if embedded_dir else None
        self.remote_url = remote_url
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.mode = DataSourceMode(mode) if isinstance(mode, str) else mode
        self.refresh_interval_days = refresh_interval_days
        self.fetcher = fetcher
        self.clock_now = clock_now or (lambda: datetime.now(timezone.utc))

        if self.mode in (DataSourceMode.REMOTE, DataSourceMode.HYBRID):
            if self.remote_url is None:
                raise DataSourceError(
                    f"Source {name!r} en mode {self.mode.value} mais "
                    "remote_url manquant.",
                    code="missing_remote_url",
                )

    def load(self) -> dict[str, Any]:
        """Charge la donnée selon le mode configuré.

        Returns:
            Dictionnaire représentant la donnée scientifique chargée.

        Raises:
            DataSourceError: Si aucune source n'est utilisable.
        """
        if self.mode == DataSourceMode.EMBEDDED:
            return self._load_embedded()

        if self.mode == DataSourceMode.REMOTE:
            try:
                return self._load_remote()
            except DataSourceError as e:
                logger.warning(
                    "Source %r en mode REMOTE indisponible (%s) — "
                    "fallback sur embedded.",
                    self.name,
                    e,
                )
                return self._load_embedded()

        if self._needs_refresh():
            try:
                return self._load_remote()
            except DataSourceError as e:
                logger.info(
                    "Refresh de %r impossible (%s) — utilisation du cache "
                    "ou de l'embedded.",
                    self.name,
                    e,
                )

        cached = self._load_cached()
        if cached is not None:
            return cached
        return self._load_embedded()

    def _load_embedded(self) -> dict[str, Any]:
        if self.embedded_dir is None or not self.embedded_dir.exists():
            raise DataSourceError(
                f"Source {self.name!r} : aucun snapshot embedded disponible.",
                code="embedded_missing",
                details={"name": self.name},
            )

        index = self.embedded_dir / "index.json"
        if not index.exists():
            json_files = sorted(self.embedded_dir.glob("*.json"))
            if not json_files:
                raise DataSourceError(
                    f"Source {self.name!r} : aucun JSON dans le snapshot.",
                    code="embedded_empty",
                    details={"path": str(self.embedded_dir)},
                )
            return self._read_json(json_files[0])

        return self._read_json(index)

    def _load_remote(self) -> dict[str, Any]:
        if self.remote_url is None:
            raise DataSourceError(
                f"Source {self.name!r} : remote_url manquant.",
                code="no_remote_url",
            )

        existing = self._load_cache_manifest()
        etag = existing.etag if existing else None

        try:
            content, headers = self._fetch(self.remote_url, etag=etag)
        except Exception as e:
            raise DataSourceError(
                f"Échec du fetch de {self.remote_url} : {e}",
                code="fetch_error",
                details={"url": self.remote_url, "name": self.name},
            ) from e

        if headers.get("status") == 304 and existing is not None:
            cached = self._load_cached()
            if cached is not None:
                return cached

        sha = hashlib.sha256(content).hexdigest()

        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            data_path = self.cache_dir / f"{self.name}.json"
            data_path.write_bytes(content)

            manifest = CacheManifest(
                source_name=self.name,
                fetched_at=self.clock_now(),
                etag=headers.get("etag"),
                sha256=sha,
                remote_url=self.remote_url,
            )
            self._save_cache_manifest(manifest)

        try:
            return json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise DataSourceError(
                f"Réponse remote non parsable JSON : {e}",
                code="invalid_response",
            ) from e

    def _load_cached(self) -> dict[str, Any] | None:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / f"{self.name}.json"
        if not path.exists():
            return None
        try:
            return self._read_json(path)
        except DataSourceError:
            return None

    def _needs_refresh(self) -> bool:
        manifest = self._load_cache_manifest()
        if manifest is None:
            return True
        elapsed = self.clock_now() - manifest.fetched_at
        return elapsed >= timedelta(days=self.refresh_interval_days)

    def _load_cache_manifest(self) -> CacheManifest | None:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / f"{self.name}.manifest.json"
        if not path.exists():
            return None
        try:
            return CacheManifest.from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def _save_cache_manifest(self, manifest: CacheManifest) -> None:
        if self.cache_dir is None:
            return
        path = self.cache_dir / f"{self.name}.manifest.json"
        try:
            path.write_text(
                json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
            )
        except OSError as e:
            logger.warning("Échec d'écriture du manifest cache : %s", e)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise DataSourceError(
                f"Lecture JSON impossible : {path} ({e})",
                code="json_read_error",
            ) from e

    def _fetch(
        self, url: str, *, etag: str | None = None
    ) -> tuple[bytes, dict[str, Any]]:
        if self.fetcher is not None:
            return self.fetcher(url, etag=etag)

        try:
            import requests
        except ImportError as e:
            raise DataSourceError(
                "La bibliothèque 'requests' est requise pour les data "
                "sources distantes. Installer via : pip install "
                "'clinvcf-sdk[networking]'.",
                code="requests_missing",
            ) from e

        headers = {"Accept": "application/json"}
        if etag:
            headers["If-None-Match"] = etag

        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 304:
            return b"", {"status": 304, "etag": etag}
        if resp.status_code != 200:
            raise DataSourceError(
                f"Réponse HTTP non-200 : {resp.status_code}",
                code="http_error",
                details={"status": resp.status_code, "url": url},
            )
        return resp.content, {
            "status": 200,
            "etag": resp.headers.get("ETag"),
        }
