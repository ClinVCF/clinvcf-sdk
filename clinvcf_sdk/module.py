"""Classe abstraite de base pour tous les modules ClinVCF.

Tout module tiers (et tout module Fdevelopment) doit hériter de
``ClinVCFModule`` et implémenter ses méthodes abstraites. C'est la classe
qui formalise le contrat technique entre les modules et la plateforme.

Cycle de vie d'un module dans ClinVCF :

    1. ClinVCF charge le manifest.json (validé par ``clinvcf_sdk.manifest``).
    2. ClinVCF instancie la classe déclarée dans ``manifest.entry_class``.
    3. ClinVCF appelle ``module.setup()`` (chargement données, init).
    4. Pour chaque exécution :
       a. ``module.validate_inputs(inputs)`` → ValidationResult
       b. Si valide : ``module.run(inputs, config)`` → ModuleResult
       c. ``module.render_report(result, format)`` → bytes
    5. À la fin : ``module.teardown()``.

Exemple d'implémentation minimale :

    from clinvcf_sdk import ClinVCFModule, ModuleManifest, ModuleResult

    class MyModule(ClinVCFModule):
        @property
        def manifest(self) -> ModuleManifest:
            return self._manifest  # chargé dans __init__

        def validate_inputs(self, inputs):
            return ValidationResult(is_valid=True)

        def run(self, inputs, config):
            return ModuleResult(...)

        def render_report(self, result, format):
            return b"..."
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clinvcf_sdk.exceptions import (
    ConfigurationError,
    InputError,
    ManifestNotFoundError,
    ReportingError,
)
from clinvcf_sdk.manifest import SDK_VERSION, ModuleManifest, load_manifest
from clinvcf_sdk.types import (
    ModuleResult,
    ReportFormat,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class ModuleInputs:
    """Conteneur pour les données d'entrée passées à un module.

    Wrap léger autour d'un dictionnaire pour permettre l'accès attribut
    et la validation typée. Les modules accèdent à leurs inputs via
    ``inputs.get("vcf_file")`` ou ``inputs["vcf_file"]``.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._data: dict[str, Any] = dict(kwargs)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        if key not in self._data:
            raise InputError(
                f"Donnée d'entrée manquante : '{key}'",
                code="missing_input",
                details={"key": key, "available": list(self._data.keys())},
            )
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def keys(self) -> Any:
        return self._data.keys()

    def items(self) -> Any:
        return self._data.items()

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class ClinVCFModule(ABC):
    """Classe abstraite pour tout module ClinVCF.

    Tous les modules doivent hériter de cette classe et implémenter au
    minimum ``manifest``, ``validate_inputs``, ``run`` et ``render_report``.
    Les méthodes ``setup`` et ``teardown`` sont optionnelles mais recommandées
    pour la gestion propre des ressources.

    Attributes:
        module_dir: Répertoire racine du module (où vit ``manifest.json``).
        config: Configuration runtime du module (dict).
        sdk_version: Version du SDK utilisée.
    """

    sdk_version: str = SDK_VERSION

    def __init__(
        self,
        module_dir: str | Path,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.module_dir = Path(module_dir).resolve()
        if not self.module_dir.exists():
            raise ConfigurationError(
                f"Répertoire du module introuvable : {self.module_dir}",
                details={"module_dir": str(self.module_dir)},
            )

        manifest_path = self.module_dir / "manifest.json"
        if not manifest_path.exists():
            raise ManifestNotFoundError(
                f"manifest.json absent dans {self.module_dir}",
                details={"expected_path": str(manifest_path)},
            )

        self._manifest_cached = load_manifest(manifest_path)
        self.config: dict[str, Any] = config or {}

        logger.info(
            "Initialisation du module %s v%s (SDK %s)",
            self._manifest_cached.id,
            self._manifest_cached.version,
            SDK_VERSION,
        )

    @property
    def manifest(self) -> ModuleManifest:
        """Manifest validé du module."""
        return self._manifest_cached

    @property
    def module_id(self) -> str:
        return self._manifest_cached.id

    @property
    def module_version(self) -> str:
        return self._manifest_cached.version

    def setup(self) -> None:
        """Hook d'initialisation appelé une fois par ClinVCF avant le premier ``run``.

        À surcharger pour : charger des données embarquées en mémoire,
        établir des connexions, vérifier des prérequis.

        Implémentation par défaut : no-op.
        """
        pass

    def teardown(self) -> None:
        """Hook de nettoyage appelé par ClinVCF avant déchargement du module.

        À surcharger pour : libérer des ressources, fermer des connexions.

        Implémentation par défaut : no-op.
        """
        pass

    @abstractmethod
    def validate_inputs(self, inputs: ModuleInputs) -> ValidationResult:
        """Valide les données d'entrée avant exécution.

        Cette méthode DOIT vérifier que :
        - tous les inputs requis du manifest sont présents
        - les fichiers sont accessibles et non corrompus
        - les méta-données du VCF (référence génomique, etc.) sont cohérentes
          avec ce que le module sait analyser

        Elle peut retourner ``is_valid=True`` avec des warnings non-bloquants
        (par exemple "couverture incomplète mais analyse possible avec
        confiance dégradée").

        Args:
            inputs: Conteneur des données d'entrée.

        Returns:
            ValidationResult décrivant la validité, les erreurs, les
            avertissements, et toute méta-donnée inférée utile pour ``run``.
        """
        ...

    @abstractmethod
    def run(self, inputs: ModuleInputs, config: dict[str, Any]) -> ModuleResult:
        """Exécute l'analyse sur les inputs validés.

        Cette méthode est appelée APRÈS ``validate_inputs`` ; elle peut
        supposer que les inputs sont valides. Elle doit retourner un
        ``ModuleResult`` complet, avec tous les résultats par gène,
        leurs statuts, niveaux de confiance et criticité.

        Args:
            inputs: Conteneur des données d'entrée (validés).
            config: Configuration runtime fusionnée (default_config + overrides).

        Returns:
            ModuleResult complet, prêt à être consommé pour le rendu de rapport.
        """
        ...

    @abstractmethod
    def render_report(
        self,
        result: ModuleResult,
        format: ReportFormat,
        language: str = "fr",
    ) -> bytes:
        """Génère le rapport au format demandé.

        Args:
            result: Résultat retourné par ``run``.
            format: Format de sortie (HTML, PDF ou JSON).
            language: Langue du rapport ("fr" ou "en").

        Returns:
            Contenu binaire du rapport (encodé UTF-8 pour HTML/JSON).
        """
        ...

    def to_qml_payload(
        self,
        result: ModuleResult,
        language: str = "fr",
    ) -> dict[str, Any]:
        """Sérialise un ``ModuleResult`` en dict consommable par QML.

        Implémentation par défaut : appelle ``clinvcf_sdk.reporting.to_qml_payload``
        qui produit un payload générique à partir du ``ModuleResult``. Les
        modules qui ont besoin d'un payload personnalisé (recommandations
        triées par criticité, disclaimers spécifiques, etc.) peuvent
        surcharger cette méthode.

        Le retour est un ``dict`` Python avec exclusivement des types
        primitifs (str, int, float, bool, list, dict, None) → directement
        convertible en ``QVariantMap`` côté PySide6 sans conversion manuelle.

        Args:
            result: Résultat retourné par ``run``.
            language: Langue du rapport ("fr" ou "en").

        Returns:
            Dict QML-friendly avec la structure standardisée ClinVCF
            (module, report, patient_metadata, executive_summary,
            gene_results, recommendations, disclaimers, metadata).
        """
        from clinvcf_sdk.reporting import to_qml_payload as _to_qml_payload

        return _to_qml_payload(result, language=language)

    def supported_formats(self) -> list[ReportFormat]:
        """Liste des formats de rapport supportés par ce module.

        Par défaut, déduit du manifest. À surcharger si nécessaire.
        """
        formats: list[ReportFormat] = []
        for spec in self._manifest_cached.data_outputs.values():
            try:
                formats.append(ReportFormat(spec.type))
            except ValueError:
                pass
        return formats

    def execute_full_pipeline(
        self,
        inputs: ModuleInputs,
        config: dict[str, Any] | None = None,
        report_format: ReportFormat = ReportFormat.HTML,
        language: str = "fr",
    ) -> tuple[ModuleResult, bytes]:
        """Pipeline complet : validate → run → render.

        Méthode utilitaire qui appelle dans l'ordre les trois étapes en
        gérant les erreurs proprement. Utilisée principalement pour les
        tests et l'exécution standalone.

        Returns:
            Tuple ``(ModuleResult, rapport_bytes)``.

        Raises:
            InputError: Si la validation des inputs échoue.
            ModuleExecutionError: Si l'exécution du module échoue.
            ReportingError: Si le rendu du rapport échoue.
        """
        merged_config = {**self.config, **(config or {})}

        validation = self.validate_inputs(inputs)
        if not validation.is_valid:
            raise InputError(
                f"Validation des inputs en échec : {'; '.join(validation.errors)}",
                code="input_validation_failed",
                details={"errors": validation.errors, "warnings": validation.warnings},
            )

        for w in validation.warnings:
            logger.warning("[%s] validation warning : %s", self.module_id, w)

        result = self.run(inputs, merged_config)

        if result.executed_at is None:
            result = ModuleResult(
                module_id=result.module_id,
                module_version=result.module_version,
                sdk_version=result.sdk_version,
                executed_at=datetime.now(timezone.utc),
                gene_results=result.gene_results,
                global_warnings=result.global_warnings,
                excluded_genes=result.excluded_genes,
                execution_metadata=result.execution_metadata,
                patient_metadata=result.patient_metadata,
            )

        try:
            rendered = self.render_report(result, report_format, language)
        except Exception as e:
            raise ReportingError(
                f"Échec du rendu de rapport : {e}",
                details={"format": report_format.value, "language": language},
            ) from e

        return result, rendered
