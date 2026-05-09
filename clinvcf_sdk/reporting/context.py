"""Contexte unifié pour le rendu de rapports.

Le ``ReportContext`` agrège tout ce dont un template de rapport a besoin :
le résultat du module, le résumé exécutif, les disclaimers, les méta-données
patient, l'identité visuelle du module, et les méta-données techniques.

Tous les modules consomment cette structure dans leurs templates Jinja2,
ce qui garantit que tous les rapports ClinVCF ont la même structure de base.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from clinvcf_sdk.reporting.disclaimer import ClinicalDisclaimer, DisclaimerBlock
from clinvcf_sdk.reporting.summary import ExecutiveSummary
from clinvcf_sdk.types import ModuleResult


@dataclass(slots=True)
class ModuleBranding:
    """Identité visuelle du module pour le rendu du rapport."""

    name: str
    short_name: str
    publisher: str
    is_verified_publisher: bool = False
    logo_svg: str | None = None
    accent_color: str = "#7C3AED"
    accent_gradient: str = (
        "linear-gradient(135deg, #7C3AED 0%, #5B5FE9 50%, #0EA5E9 100%)"
    )
    homepage_url: str | None = None


@dataclass(slots=True)
class ReportContext:
    """Contexte complet pour le rendu d'un rapport ClinVCF.

    Attributes:
        result: Résultat ``ModuleResult`` à présenter.
        executive_summary: Résumé exécutif déjà calculé.
        disclaimers: Liste ordonnée des disclaimers à afficher.
        branding: Identité visuelle du module.
        patient_metadata: Méta-données patient (anonymisées).
        report_metadata: Méta-données du rapport (référence, date, langue).
        language: Langue du rendu ("fr" ou "en").
    """

    result: ModuleResult
    executive_summary: ExecutiveSummary
    disclaimers: list[DisclaimerBlock]
    branding: ModuleBranding
    patient_metadata: dict[str, Any] = field(default_factory=dict)
    report_metadata: dict[str, Any] = field(default_factory=dict)
    language: str = "fr"

    @classmethod
    def build(
        cls,
        result: ModuleResult,
        branding: ModuleBranding,
        *,
        language: str = "fr",
        report_type: str = "clinical",
        patient_metadata: dict[str, Any] | None = None,
        report_reference: str | None = None,
        methodology_notes: list[str] | None = None,
    ) -> "ReportContext":
        """Construit un contexte de rapport complet.

        Args:
            result: ``ModuleResult`` à présenter.
            branding: Identité visuelle du module.
            language: Langue du rendu ("fr" ou "en").
            report_type: "clinical" (par défaut), "research" ou "demo".
            patient_metadata: Méta-données patient pour le rapport.
            report_reference: Référence/numéro du rapport.
            methodology_notes: Limitations méthodologiques à intégrer dans
                le disclaimer dédié.

        Returns:
            ``ReportContext`` prêt pour le rendu Jinja2.
        """
        summary = ExecutiveSummary.from_result(result, language=language)

        is_third_party = not branding.is_verified_publisher
        disclaimers = ClinicalDisclaimer.for_report(
            language=language,
            report_type=report_type,
            is_third_party_module=is_third_party,
            methodology_notes=methodology_notes
            or cls._collect_methodology_notes(result),
        )

        report_metadata: dict[str, Any] = {
            "reference": report_reference
            or cls._generate_reference(result),
            "generated_at": result.executed_at or datetime.now(timezone.utc),
            "language": language,
            "report_type": report_type,
            "module_id": result.module_id,
            "module_version": result.module_version,
            "sdk_version": result.sdk_version,
        }

        return cls(
            result=result,
            executive_summary=summary,
            disclaimers=disclaimers,
            branding=branding,
            patient_metadata=patient_metadata or result.patient_metadata or {},
            report_metadata=report_metadata,
            language=language,
        )

    @staticmethod
    def _collect_methodology_notes(result: ModuleResult) -> list[str]:
        """Extrait les notes méthodologiques uniques depuis les warnings."""
        notes: list[str] = []
        seen: set[str] = set()

        for w in result.global_warnings:
            if w not in seen:
                notes.append(w)
                seen.add(w)

        for r in result.gene_results:
            for w in r.warnings:
                if w not in seen:
                    notes.append(w)
                    seen.add(w)

        return notes

    @staticmethod
    def _generate_reference(result: ModuleResult) -> str:
        """Génère une référence par défaut si non fournie."""
        ts = (result.executed_at or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
        prefix = result.module_id.upper()[:6]
        return f"{prefix}-{ts}"
