"""Pytest fixtures partagées pour les tests du SDK."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from clinvcf_sdk import (
    CallStatus,
    ConfidenceLevel,
    CoverageReport,
    CriticalityLevel,
    DataSourceRef,
    DrugRecommendation,
    GeneCallResult,
    ModuleResult,
    SDK_VERSION,
)


@pytest.fixture
def sample_data_source() -> DataSourceRef:
    """Source scientifique de référence pour tests."""
    return DataSourceRef(
        name="CPIC DPYD Guideline",
        version="2018",
        snapshot_date=date(2026, 4, 15),
        url="https://cpicpgx.org/guidelines/guideline-for-fluoropyrimidines-and-dpyd/",
    )


@pytest.fixture
def sample_coverage_report() -> CoverageReport:
    """CoverageReport minimal pour tests."""
    return CoverageReport(
        gene="DPYD",
        total_positions_required=5,
        called_count=5,
        missing_count=0,
        low_quality_count=0,
    )


@pytest.fixture
def sample_recommendation(sample_data_source: DataSourceRef) -> DrugRecommendation:
    """Recommandation médicament pour tests."""
    return DrugRecommendation(
        drug_name="5-Fluorouracile",
        related_genes=["DPYD"],
        recommendation_text="Réduire la dose initiale de 50% — cf. CPIC.",
        criticality=CriticalityLevel.MAJOR_ALERT,
        guideline_source=sample_data_source,
        action_required="Réduire dose 50%",
    )


@pytest.fixture
def sample_gene_result(
    sample_coverage_report: CoverageReport,
    sample_recommendation: DrugRecommendation,
    sample_data_source: DataSourceRef,
) -> GeneCallResult:
    """GeneCallResult complet pour tests."""
    return GeneCallResult(
        gene="DPYD",
        diplotype="*1/*2A",
        activity_score=1.0,
        phenotype="Intermediate Metabolizer",
        status=CallStatus.CALLED,
        confidence=ConfidenceLevel.HIGH,
        criticality=CriticalityLevel.MAJOR_ALERT,
        coverage=sample_coverage_report,
        warnings=[],
        recommendations=[sample_recommendation],
        data_sources=[sample_data_source],
    )


@pytest.fixture
def sample_module_result(sample_gene_result: GeneCallResult) -> ModuleResult:
    """ModuleResult complet pour tests."""
    return ModuleResult(
        module_id="test-module",
        module_version="1.0.0",
        sdk_version=SDK_VERSION,
        executed_at=datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc),
        gene_results=[sample_gene_result],
    )
