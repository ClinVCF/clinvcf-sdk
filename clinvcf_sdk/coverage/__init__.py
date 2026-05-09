"""Helpers d'analyse de couverture VCF.

Fournit les outils standardisés pour qu'un module puisse :

* Vérifier qu'un VCF couvre les positions clés d'un gène
* Calculer un niveau de confiance basé sur la couverture
* Générer un ``CoverageReport`` standardisé pour le SDK

Usage typique dans un module :

    from clinvcf_sdk.coverage import CoverageAnalyzer, ConfidenceScorer

    analyzer = CoverageAnalyzer(vcf_path, min_depth=10, min_quality=20)
    coverage = analyzer.analyze_gene("DPYD", required_positions=DPYD_POSITIONS)

    scorer = ConfidenceScorer()
    confidence = scorer.score(coverage, gene_method="snv_indel")
"""

from clinvcf_sdk.coverage.analyzer import CoverageAnalyzer
from clinvcf_sdk.coverage.confidence import (
    CallingMethod,
    ConfidenceScorer,
    GeneConfidenceProfile,
)

__all__ = [
    "CoverageAnalyzer",
    "ConfidenceScorer",
    "GeneConfidenceProfile",
    "CallingMethod",
]
