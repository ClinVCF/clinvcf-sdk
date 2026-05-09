"""Schéma de validation du fichier ``manifest.json`` des modules ClinVCF.

Validation STRICTE : un module qui ne respecte pas exactement ce schéma sera
rejeté par ClinStore à l'upload et par ClinVCF à l'installation. Cette
rigueur protège l'utilisateur final et l'écosystème.

La validation s'appuie sur Pydantic v2. Tout module doit être chargeable
via :

    from clinvcf_sdk.manifest import ModuleManifest, load_manifest

    manifest = load_manifest("path/to/manifest.json")
    # Lève ManifestValidationError si le fichier est invalide
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from clinvcf_sdk.exceptions import (
    ManifestNotFoundError,
    ManifestValidationError,
    ManifestVersionMismatchError,
)


SDK_VERSION = "1.0.1"


SemverPattern = Annotated[
    str,
    Field(
        pattern=r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
        r"(?:-(?:[a-zA-Z\d][a-zA-Z\d-]*)(?:\.[a-zA-Z\d][a-zA-Z\d-]*)*)?$",
        description="Version SemVer 2.0",
    ),
]


ModuleIdPattern = Annotated[
    str,
    Field(
        min_length=2,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_-]*[a-z0-9]$",
        description=(
            "Identifiant module : minuscules, alphanumérique avec tirets/underscores, "
            "doit commencer par une lettre et finir par alphanumérique."
        ),
    ),
]


class CompatibilitySpec(BaseModel):
    """Compatibilité du module avec ClinVCF, Python et l'OS."""

    model_config = ConfigDict(extra="forbid")

    clinvcf_min_version: SemverPattern
    clinvcf_max_version: SemverPattern | None = None
    sdk_min_version: SemverPattern = Field(default=SDK_VERSION)
    python_min_version: str = Field(pattern=r"^3\.\d+$", default="3.10")
    platforms: list[Literal["linux", "darwin", "win32"]] = Field(
        default_factory=lambda: ["linux", "darwin", "win32"]
    )


class DataInputSpec(BaseModel):
    """Description d'une donnée d'entrée attendue par le module."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["vcf", "json", "csv", "bam", "fasta", "text"]
    description: str = Field(min_length=10, max_length=2000)
    schema_path: str | None = Field(default=None, alias="schema")
    min_columns: list[str] | None = None
    recommended_columns: list[str] | None = None


class DataOutputSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["html", "pdf", "json", "csv", "txt"]
    description: str = Field(min_length=10, max_length=500)


class DataInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: dict[str, DataInputSpec] = Field(default_factory=dict)
    optional: dict[str, DataInputSpec] = Field(default_factory=dict)


class PricingTier(str):
    """Tier supporté par le module."""

    pass


class CommunityQuota(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports_per_month: int = Field(ge=0, le=10_000)
    reset_period: Literal["monthly", "weekly", "daily"] = "monthly"


class AddonPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=100)
    price_eur: float = Field(ge=0)
    reports: int = Field(ge=1)


class PricingSpec(BaseModel):
    """Modèle de monétisation du module sur ClinStore."""

    model_config = ConfigDict(extra="forbid")

    tier_inclusion: list[Literal["community", "pro", "team", "enterprise"]] = Field(
        default_factory=list
    )
    community_quota: CommunityQuota | None = None
    pro_unlimited: bool = True
    team_unlimited: bool = True
    addon_packs: list[AddonPack] = Field(default_factory=list)


class ScientificSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str
    license: str


class ScientificSources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guidelines: list[ScientificSource] = Field(default_factory=list)
    allele_definitions: list[ScientificSource] = Field(default_factory=list)


class EmbeddedDataVersions(BaseModel):
    """Versions des snapshots embarqués dans le module."""

    model_config = ConfigDict(extra="allow")

    snapshot_date: date


class NetworkPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_domains: list[str] = Field(default_factory=list)
    purpose: str = Field(min_length=10, max_length=500)


class Permissions(BaseModel):
    """Permissions demandées par le module au runtime ClinVCF.

    Les permissions sont strictement limitatives : un module qui essaye
    d'accéder à une ressource non déclarée est interrompu par le sandbox.
    """

    model_config = ConfigDict(extra="forbid")

    filesystem_read: list[str] = Field(default_factory=list)
    filesystem_write: list[str] = Field(default_factory=list)
    network: NetworkPermissions | None = None


class ModuleManifest(BaseModel):
    """Manifeste complet d'un module ClinVCF.

    Validation Pydantic stricte sur les champs critiques (typage, format,
    cohérence). Les champs inconnus sont ignorés (``extra="ignore"``) plutôt
    que rejetés, pour permettre :

    * la rétrocompatibilité avec le ``manifest_schema.json`` historique de
      ClinVCF-OS (champs ``publisher``, ``entry``, ``apis``, ``requires``)
    * l'ajout futur de champs par des outils tiers (review, ClinStore)
      sans casser la validation côté module

    Compatibilité ClinVCF-OS :

    * ``publisher`` est un alias de ``author`` (auto-rempli si absent).
    * ``entry`` est auto-calculé depuis ``main`` + ``entry_class`` si absent
      (forme ``"python:<dotted-module>:<class>"``).
    * ``icon`` est un champ standard, déjà optionnel dans le SDK.
    * ``apis`` liste les APIs ClinVCF-OS utilisées par le module
      (ex. ``["library", "session"]``).
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: ModuleIdPattern
    name: str = Field(min_length=2, max_length=100)
    version: SemverPattern
    description: str = Field(min_length=20, max_length=2000)
    description_fr: str | None = Field(default=None, max_length=2000)

    author: str = Field(min_length=2, max_length=200)
    author_url: str | None = None
    license: str = Field(min_length=2, max_length=100)
    license_file: str = Field(default="LICENSE.txt")
    copyright: str = Field(min_length=5, max_length=500)
    homepage: str | None = None
    documentation: str | None = None
    support_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    category: Literal[
        "prediction",
        "annotation",
        "qc",
        "analysis",
        "visualization",
        "report",
        "system",
    ]
    tags: list[str] = Field(default_factory=list, max_length=20)
    icon: str | None = None

    main: str = Field(default="main.py", description="Chemin du point d'entrée.")
    entry_class: str = Field(
        min_length=1,
        max_length=100,
        description=(
            "Nom de la classe Python implémentant ClinVCFModule. "
            "Doit être importable depuis le fichier 'main'."
        ),
    )

    compatibility: CompatibilitySpec
    data_inputs: DataInputs = Field(default_factory=DataInputs)
    data_outputs: dict[str, DataOutputSpec] = Field(default_factory=dict)

    configurable: bool = False
    config_schema: str | None = None
    default_config: str | None = None

    pricing: PricingSpec
    scientific_sources: ScientificSources = Field(default_factory=ScientificSources)
    embedded_data_versions: EmbeddedDataVersions | None = None
    permissions: Permissions = Field(default_factory=Permissions)

    # ─── Champs additionnels pour compatibilité ClinVCF-OS ───────────────
    publisher: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Éditeur du module — alias de ``author`` pour compatibilité avec "
            "le ``manifest_schema.json`` historique de ClinVCF-OS. "
            "Auto-rempli depuis ``author`` si absent."
        ),
    )
    entry: str | None = Field(
        default=None,
        description=(
            "Point d'entrée formaté pour ClinVCF-OS, sous la forme "
            "``python:<dotted-module>:<class>``. Auto-calculé depuis "
            "``main`` + ``entry_class`` si absent."
        ),
    )
    apis: list[str] = Field(
        default_factory=list,
        description=(
            "Identifiants des APIs ClinVCF-OS utilisées par le module "
            "au runtime (ex. ``['library', 'session', 'ml']``). Sert à "
            "l'analyse de permissions par ClinVCF-OS et ClinStore."
        ),
    )

    @field_validator("entry_class")
    @classmethod
    def _validate_entry_class(cls, v: str) -> str:
        if not re.match(r"^[A-Z][A-Za-z0-9_]*$", v):
            raise ValueError(
                "entry_class doit être un nom de classe Python valide (PascalCase)"
            )
        return v

    @model_validator(mode="after")
    def _check_configurable_consistency(self) -> "ModuleManifest":
        if self.configurable and not self.default_config:
            raise ValueError(
                "configurable=True nécessite la déclaration de default_config"
            )
        return self

    @model_validator(mode="after")
    def _check_pricing_consistency(self) -> "ModuleManifest":
        pricing = self.pricing
        if "community" in pricing.tier_inclusion and pricing.community_quota is None:
            raise ValueError(
                "L'inclusion dans le tier 'community' requiert un community_quota défini"
            )
        return self

    @model_validator(mode="after")
    def _fill_publisher_from_author(self) -> "ModuleManifest":
        """Auto-remplit ``publisher`` depuis ``author`` pour compat ClinVCF-OS."""
        if self.publisher is None:
            self.publisher = self.author
        return self

    @model_validator(mode="after")
    def _fill_entry_from_main_class(self) -> "ModuleManifest":
        """Auto-calcule ``entry`` depuis ``main`` + ``entry_class`` si absent.

        Forme produite : ``python:<dotted-module>:<class>``.
        Exemple : ``main="pharmgx/main.py"`` + ``entry_class="PharmGxModule"``
        donne ``entry="python:pharmgx.main:PharmGxModule"``.
        """
        if self.entry is None:
            main_path = self.main.replace("\\", "/")
            if main_path.endswith(".py"):
                main_path = main_path[:-3]
            dotted = main_path.replace("/", ".").strip(".")
            self.entry = f"python:{dotted}:{self.entry_class}"
        return self


def _normalize_manifest_keys(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise quelques alias historiques avant validation Pydantic."""
    if "data_inputs" not in raw and ("required" in raw or "optional" in raw):
        raw["data_inputs"] = {
            "required": raw.pop("required", {}),
            "optional": raw.pop("optional", {}),
        }
    return raw


def load_manifest(path: str | Path) -> ModuleManifest:
    """Charge et valide un manifest.json.

    Args:
        path: Chemin vers le fichier manifest.json.

    Returns:
        Instance validée de ``ModuleManifest``.

    Raises:
        ManifestNotFoundError: Si le fichier n'existe pas.
        ManifestValidationError: Si le contenu n'est pas conforme au schéma.
        ManifestVersionMismatchError: Si la version SDK requise est incompatible.
    """
    p = Path(path)
    if not p.exists():
        raise ManifestNotFoundError(
            f"Fichier manifest.json introuvable : {p}",
            details={"path": str(p)},
        )

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ManifestValidationError(
            f"manifest.json contient un JSON invalide : {e}",
            details={"path": str(p), "json_error": str(e)},
        ) from e

    raw = _normalize_manifest_keys(raw)

    try:
        manifest = ModuleManifest.model_validate(raw)
    except Exception as e:
        raise ManifestValidationError(
            f"manifest.json ne respecte pas le schéma SDK : {e}",
            details={"path": str(p), "validation_errors": str(e)},
        ) from e

    _check_sdk_compatibility(manifest)
    return manifest


def _check_sdk_compatibility(manifest: ModuleManifest) -> None:
    """Vérifie que la version SDK requise est compatible avec celle installée."""
    required = manifest.compatibility.sdk_min_version
    if _semver_lt(SDK_VERSION, required):
        raise ManifestVersionMismatchError(
            f"Le module {manifest.id} requiert clinvcf_sdk>={required}, "
            f"mais la version installée est {SDK_VERSION}",
            details={"required": required, "installed": SDK_VERSION},
        )


def _semver_lt(a: str, b: str) -> bool:
    """Comparaison SemVer simple (sans pre-release)."""

    def parts(s: str) -> tuple[int, ...]:
        return tuple(int(x) for x in s.split("-")[0].split("."))

    return parts(a) < parts(b)
