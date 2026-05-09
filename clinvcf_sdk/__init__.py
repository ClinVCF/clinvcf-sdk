"""SDK ClinVCF — Boîte à outils officielle pour les modules tiers.

Ce package est publié sous licence MIT sur PyPI. Les modules qui l'utilisent
peuvent être propriétaires ou open-source selon le choix du développeur.

Usage typique pour un développeur de module tiers :

    from clinvcf_sdk import (
        ClinVCFModule,
        ModuleInputs,
        ModuleResult,
        GeneCallResult,
        CallStatus,
        ConfidenceLevel,
        CriticalityLevel,
        ReportFormat,
        CoverageReport,
        DataSourceRef,
        DrugRecommendation,
        ValidationResult,
    )

    class MyModule(ClinVCFModule):
        def validate_inputs(self, inputs):
            ...
        def run(self, inputs, config):
            ...
        def render_report(self, result, format, language="fr"):
            ...
"""

from clinvcf_sdk.exceptions import (
    CallingError,
    ClinVCFSDKError,
    ConfigurationError,
    DataSourceError,
    ExternalDataMissingError,
    InputError,
    LicenseExpiredError,
    LicenseInvalidError,
    LicensingError,
    ManifestError,
    ManifestNotFoundError,
    ManifestValidationError,
    ManifestVersionMismatchError,
    ModuleExecutionError,
    QuotaExceededError,
    ReportingError,
    TierMismatchError,
    VCFCoverageInsufficientError,
    VCFParsingError,
)
from clinvcf_sdk.coverage import (
    CallingMethod,
    ConfidenceScorer,
    CoverageAnalyzer,
    GeneConfidenceProfile,
)
from clinvcf_sdk.data_sources import DataSourceMode, HybridDataSource
from clinvcf_sdk.licensing import (
    LicenseChecker,
    LicenseInfo,
    QuotaTracker,
    Tier,
)
from clinvcf_sdk.manifest import SDK_VERSION, ModuleManifest, load_manifest
from clinvcf_sdk.module import ClinVCFModule, ModuleInputs
from clinvcf_sdk.reporting import (
    ClinicalDisclaimer,
    ExecutiveSummary,
    ReportContext,
    to_qml_payload,
)
from clinvcf_sdk.types import (
    CallStatus,
    ConfidenceLevel,
    CoveragePosition,
    CoverageReport,
    CriticalityLevel,
    DataSourceRef,
    DrugRecommendation,
    GeneCallResult,
    GeneticReference,
    GenomicPosition,
    ModuleResult,
    ReportFormat,
    ValidationResult,
)

__version__ = SDK_VERSION

__all__ = [
    "SDK_VERSION",
    "__version__",
    "ClinVCFModule",
    "ModuleInputs",
    "ModuleManifest",
    "ModuleResult",
    "GeneCallResult",
    "DrugRecommendation",
    "CoverageReport",
    "CoveragePosition",
    "CallStatus",
    "ConfidenceLevel",
    "CriticalityLevel",
    "ReportFormat",
    "GeneticReference",
    "GenomicPosition",
    "DataSourceRef",
    "ValidationResult",
    "load_manifest",
    "CoverageAnalyzer",
    "ConfidenceScorer",
    "GeneConfidenceProfile",
    "CallingMethod",
    "ClinicalDisclaimer",
    "ExecutiveSummary",
    "ReportContext",
    "to_qml_payload",
    "LicenseChecker",
    "LicenseInfo",
    "Tier",
    "QuotaTracker",
    "HybridDataSource",
    "DataSourceMode",
    "ClinVCFSDKError",
    "ManifestError",
    "ManifestNotFoundError",
    "ManifestValidationError",
    "ManifestVersionMismatchError",
    "InputError",
    "VCFParsingError",
    "VCFCoverageInsufficientError",
    "ExternalDataMissingError",
    "ModuleExecutionError",
    "ConfigurationError",
    "DataSourceError",
    "CallingError",
    "LicensingError",
    "LicenseInvalidError",
    "LicenseExpiredError",
    "QuotaExceededError",
    "TierMismatchError",
    "ReportingError",
]
