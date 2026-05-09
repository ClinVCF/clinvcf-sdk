"""Exceptions du SDK ClinVCF.

Hiérarchie d'exceptions standardisée que tous les modules tiers doivent
réutiliser pour que ClinVCF puisse les présenter uniformément à l'utilisateur.

Hiérarchie :

    ClinVCFSDKError                     (base, exception générique du SDK)
    ├── ManifestError                   (problème dans manifest.json)
    │   ├── ManifestValidationError
    │   ├── ManifestNotFoundError
    │   └── ManifestVersionMismatchError
    ├── InputError                      (problème dans les données d'entrée)
    │   ├── VCFParsingError
    │   ├── VCFCoverageInsufficientError
    │   └── ExternalDataMissingError
    ├── ModuleExecutionError            (erreur métier pendant run())
    │   ├── ConfigurationError
    │   ├── DataSourceError
    │   └── CallingError
    ├── LicensingError                  (licence invalide, quota dépassé)
    │   ├── LicenseInvalidError
    │   ├── LicenseExpiredError
    │   ├── QuotaExceededError
    │   └── TierMismatchError
    └── ReportingError                  (rendu de rapport en échec)

Convention : tous les messages d'erreur sont en français pour cohérence avec
ClinVCF. Le champ ``code`` est en anglais et stable (utilisé pour i18n et
analytics).
"""
from __future__ import annotations

from typing import Any


class ClinVCFSDKError(Exception):
    """Exception racine du SDK ClinVCF.

    Tous les modules tiers doivent lever des sous-classes de celle-ci, jamais
    des exceptions natives Python directement, pour que ClinVCF puisse afficher
    un message structuré à l'utilisateur.
    """

    code: str = "sdk_error"
    user_message: str = "Une erreur est survenue dans le module."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.user_message)
        if code:
            self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.args[0]} — détails : {self.details}"
        return f"[{self.code}] {self.args[0]}"


class ManifestError(ClinVCFSDKError):
    """Problème lié au fichier manifest.json du module."""

    code = "manifest_error"
    user_message = "Le manifeste du module est invalide ou inaccessible."


class ManifestValidationError(ManifestError):
    code = "manifest_validation_error"
    user_message = "Le manifeste du module ne respecte pas le schéma SDK requis."


class ManifestNotFoundError(ManifestError):
    code = "manifest_not_found"
    user_message = "Aucun fichier manifest.json trouvé pour ce module."


class ManifestVersionMismatchError(ManifestError):
    code = "manifest_version_mismatch"
    user_message = (
        "La version SDK requise par le module est incompatible avec celle de ClinVCF."
    )


class InputError(ClinVCFSDKError):
    """Problème dans les données fournies en entrée."""

    code = "input_error"
    user_message = "Les données d'entrée sont invalides ou incomplètes."


class VCFParsingError(InputError):
    code = "vcf_parsing_error"
    user_message = "Le fichier VCF ne peut pas être analysé."


class VCFCoverageInsufficientError(InputError):
    code = "vcf_coverage_insufficient"
    user_message = (
        "La couverture du fichier VCF est insuffisante pour produire un résultat fiable."
    )


class ExternalDataMissingError(InputError):
    code = "external_data_missing"
    user_message = (
        "Une donnée externe nécessaire est manquante (ex. typage HLA dédié)."
    )


class ModuleExecutionError(ClinVCFSDKError):
    """Erreur métier pendant l'exécution du module."""

    code = "module_execution_error"
    user_message = "Le module a rencontré une erreur durant son exécution."


class ConfigurationError(ModuleExecutionError):
    code = "configuration_error"
    user_message = "La configuration du module est invalide."


class DataSourceError(ModuleExecutionError):
    code = "data_source_error"
    user_message = "Une source de données externe est inaccessible ou corrompue."


class CallingError(ModuleExecutionError):
    code = "calling_error"
    user_message = "L'appel des génotypes a échoué."


class LicensingError(ClinVCFSDKError):
    """Problème de licence ou de quota."""

    code = "licensing_error"
    user_message = "Un problème de licence empêche l'exécution du module."


class LicenseInvalidError(LicensingError):
    code = "license_invalid"
    user_message = "La licence fournie est invalide ou ne correspond pas à ce module."


class LicenseExpiredError(LicensingError):
    code = "license_expired"
    user_message = "La licence du module a expiré."


class QuotaExceededError(LicensingError):
    code = "quota_exceeded"
    user_message = "Le quota mensuel du module est atteint pour votre tier."


class TierMismatchError(LicensingError):
    code = "tier_mismatch"
    user_message = "Votre tier ne donne pas accès à ce module."


class ReportingError(ClinVCFSDKError):
    """Échec du rendu d'un rapport."""

    code = "reporting_error"
    user_message = "La génération du rapport a échoué."
