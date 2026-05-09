"""Tests fonctionnels du SDK ClinVCF.

Ces tests valident les **contrats publics** du SDK — ce que les développeurs
de modules tiers utilisent au quotidien :
- L'import du paquet et la version exposée
- Les enums sémantiques (CallStatus, CriticalityLevel, ReportFormat)
- L'instanciation des dataclasses publiques (GeneCallResult, ModuleResult)
- Le helper `to_qml_payload` qui sérialise pour l'UI ClinVCF-OS

Note : ils ne testent pas la logique métier des modules (parsing VCF, etc.) —
c'est le rôle des tests des modules eux-mêmes (PharmGx, etc.).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from clinvcf_sdk import (
    CallStatus,
    ClinVCFModule,
    ConfidenceLevel,
    CriticalityLevel,
    GeneCallResult,
    ModuleResult,
    ReportFormat,
    SDK_VERSION,
    to_qml_payload,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Import & version
# ─────────────────────────────────────────────────────────────────────────────


class TestSDKImport:
    """Vérifie que le SDK s'importe et expose ses contrats publics."""

    def test_sdk_version_is_exposed(self) -> None:
        """SDK_VERSION doit être une chaîne semver non vide."""
        assert isinstance(SDK_VERSION, str)
        assert len(SDK_VERSION) > 0
        # Format X.Y.Z minimum
        parts = SDK_VERSION.split(".")
        assert len(parts) >= 3, f"SDK_VERSION '{SDK_VERSION}' doit suivre semver X.Y.Z"
        assert all(p.isdigit() for p in parts[:3]), (
            f"SDK_VERSION '{SDK_VERSION}' doit contenir des chiffres"
        )

    def test_dunder_version_matches_sdk_version(self) -> None:
        """`clinvcf_sdk.__version__` doit être identique à `SDK_VERSION`."""
        import clinvcf_sdk

        assert clinvcf_sdk.__version__ == SDK_VERSION

    def test_clinvcf_module_is_abstract(self) -> None:
        """`ClinVCFModule` doit être abstrait — non instanciable directement."""
        with pytest.raises(TypeError):
            ClinVCFModule()  # type: ignore[abstract]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Enums sémantiques (grammaire clinique)
# ─────────────────────────────────────────────────────────────────────────────


class TestEnums:
    """Vérifie les enums centraux du SDK."""

    def test_call_status_actionability(self) -> None:
        """`is_actionable` distingue les statuts qui autorisent une recommandation."""
        # Statuts actionnables (recommandation clinique possible)
        assert CallStatus.CALLED.is_actionable is True
        assert CallStatus.CALLED_EXPERIMENTAL.is_actionable is True

        # Statuts NON actionnables (jamais en vert dans l'UI)
        assert CallStatus.NOT_EVALUABLE.is_actionable is False
        assert CallStatus.NOT_COVERED.is_actionable is False
        assert CallStatus.BLOCKED.is_actionable is False

    def test_report_format_includes_qml_payload(self) -> None:
        """`ReportFormat.QML_PAYLOAD` doit être disponible (M1 — host integration)."""
        assert ReportFormat.QML_PAYLOAD.value == "qml_payload"
        # Et les formats classiques aussi
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.PDF.value == "pdf"
        assert ReportFormat.JSON.value == "json"

    def test_criticality_levels_are_distinct(self) -> None:
        """Les niveaux de criticité doivent être tous distincts."""
        values = [level.value for level in CriticalityLevel]
        assert len(values) == len(set(values)), "CriticalityLevel a des doublons"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dataclasses publiques
# ─────────────────────────────────────────────────────────────────────────────


class TestModuleResult:
    """Vérifie l'API du conteneur de résultat principal."""

    def test_module_result_summary_counts(
        self, sample_module_result: ModuleResult
    ) -> None:
        """`summary_counts()` doit compter correctement par criticité."""
        counts = sample_module_result.summary_counts()
        # Toutes les CriticalityLevel doivent être présentes (même à 0)
        for level in CriticalityLevel:
            assert level in counts, f"{level} manquant dans summary_counts"
        # Le seul gène a criticality=MAJOR_ALERT
        assert counts[CriticalityLevel.MAJOR_ALERT] == 1
        # Les autres doivent être à 0
        other_total = sum(
            v for k, v in counts.items() if k != CriticalityLevel.MAJOR_ALERT
        )
        assert other_total == 0

    def test_module_result_has_required_fields(
        self, sample_module_result: ModuleResult
    ) -> None:
        """ModuleResult expose les champs essentiels pour l'audit."""
        assert sample_module_result.module_id == "test-module"
        assert sample_module_result.module_version == "1.0.0"
        assert sample_module_result.sdk_version == SDK_VERSION
        assert isinstance(sample_module_result.executed_at, datetime)
        assert sample_module_result.executed_at.tzinfo is not None, (
            "executed_at doit être timezone-aware (UTC)"
        )

    def test_gene_call_result_is_immutable_compatible(
        self, sample_gene_result: GeneCallResult
    ) -> None:
        """GeneCallResult contient les champs critiques pour l'UI."""
        assert sample_gene_result.gene == "DPYD"
        assert sample_gene_result.status == CallStatus.CALLED
        assert sample_gene_result.criticality == CriticalityLevel.MAJOR_ALERT
        assert len(sample_gene_result.recommendations) == 1
        assert len(sample_gene_result.data_sources) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 4. Helper to_qml_payload (host integration)
# ─────────────────────────────────────────────────────────────────────────────


class TestToQmlPayload:
    """Vérifie le helper `to_qml_payload` utilisé par ClinVCF-OS."""

    def test_to_qml_payload_returns_dict(
        self, sample_module_result: ModuleResult
    ) -> None:
        """Le retour doit être un dict (pour QVariantMap côté Qt)."""
        payload = to_qml_payload(sample_module_result)
        assert isinstance(payload, dict)

    def test_to_qml_payload_contains_genes_list(
        self, sample_module_result: ModuleResult
    ) -> None:
        """Le payload doit contenir une liste de gènes consommable par QML."""
        payload = to_qml_payload(sample_module_result)
        assert "gene_results" in payload, (
            f"Clé 'gene_results' manquante. Clés : {list(payload)}"
        )
        assert isinstance(payload["gene_results"], list)
        assert len(payload["gene_results"]) == 1
        gene = payload["gene_results"][0]
        assert isinstance(gene, dict)
        assert gene.get("gene") == "DPYD"

    def test_to_qml_payload_propagates_recommendations(
        self, sample_module_result: ModuleResult
    ) -> None:
        """Les recommandations attachées aux gènes doivent remonter au top-level."""
        payload = to_qml_payload(sample_module_result)
        assert "recommendations" in payload
        recs = payload["recommendations"]
        assert isinstance(recs, list)
        assert len(recs) >= 1, "La recommandation DPYD/5-FU doit être présente"

    def test_to_qml_payload_respects_language(
        self, sample_module_result: ModuleResult
    ) -> None:
        """Le paramètre `language` doit être accepté sans planter."""
        # Test que l'appel ne lève pas
        payload_fr = to_qml_payload(sample_module_result, language="fr")
        payload_en = to_qml_payload(sample_module_result, language="en")
        assert isinstance(payload_fr, dict)
        assert isinstance(payload_en, dict)
