"""Construction du résumé exécutif d'un rapport.

Le résumé exécutif est ce qui apparaît en haut du rapport : le clinicien
doit pouvoir voir en 2 secondes s'il y a un problème. Le SDK fournit la
classe ``ExecutiveSummary`` qui construit cette synthèse à partir d'un
``ModuleResult``.
"""
from __future__ import annotations

from dataclasses import dataclass

from clinvcf_sdk.types import (
    CriticalityLevel,
    ModuleResult,
)


@dataclass(slots=True)
class SummaryEntry:
    """Une case du résumé exécutif."""

    criticality: CriticalityLevel
    label: str
    count: int
    related_genes: list[str]
    css_class: str

    @property
    def is_actionable(self) -> bool:
        """True si la case mérite l'attention immédiate du clinicien."""
        return self.count > 0 and self.criticality in (
            CriticalityLevel.ABSOLUTE_CONTRAINDICATION,
            CriticalityLevel.MAJOR_ALERT,
            CriticalityLevel.PRECAUTION,
        )


@dataclass(slots=True)
class ExecutiveSummary:
    """Résumé exécutif d'un ``ModuleResult``.

    Quatre cases standard : alertes majeures, précautions, normaux,
    non évaluables. Plus une case optionnelle pour les contre-indications
    absolues si présentes.
    """

    entries: list[SummaryEntry]
    total_genes_analyzed: int

    @classmethod
    def from_result(
        cls, result: ModuleResult, language: str = "fr"
    ) -> "ExecutiveSummary":
        """Construit un résumé exécutif depuis un ``ModuleResult``."""
        genes_by_crit: dict[CriticalityLevel, list[str]] = {
            level: [] for level in CriticalityLevel
        }
        for r in result.gene_results:
            genes_by_crit[r.criticality].append(r.gene)

        order = [
            CriticalityLevel.ABSOLUTE_CONTRAINDICATION,
            CriticalityLevel.MAJOR_ALERT,
            CriticalityLevel.PRECAUTION,
            CriticalityLevel.NORMAL,
            CriticalityLevel.NOT_EVALUABLE,
        ]

        entries: list[SummaryEntry] = []
        for level in order:
            count = len(genes_by_crit[level])
            if (
                level == CriticalityLevel.ABSOLUTE_CONTRAINDICATION
                and count == 0
            ):
                continue
            label = level.label_fr if language == "fr" else level.label_en
            entries.append(
                SummaryEntry(
                    criticality=level,
                    label=label,
                    count=count,
                    related_genes=genes_by_crit[level],
                    css_class=level.color_class,
                )
            )

        return cls(
            entries=entries,
            total_genes_analyzed=len(result.gene_results),
        )

    def has_critical_findings(self) -> bool:
        """True si au moins une contre-indication absolue ou alerte majeure."""
        for e in self.entries:
            if e.is_actionable and e.criticality in (
                CriticalityLevel.ABSOLUTE_CONTRAINDICATION,
                CriticalityLevel.MAJOR_ALERT,
            ):
                return True
        return False

    def has_partial_evaluation(self) -> bool:
        """True si certains gènes n'ont pas pu être évalués."""
        for e in self.entries:
            if (
                e.criticality == CriticalityLevel.NOT_EVALUABLE
                and e.count > 0
            ):
                return True
        return False
