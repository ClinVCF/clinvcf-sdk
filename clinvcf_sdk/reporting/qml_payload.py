"""Sérialisation d'un ``ModuleResult`` vers un dict consommable par QML.

Le SDK fournit ``to_qml_payload()`` comme implémentation par défaut pour
exposer un résultat de module à un client QML (typiquement ClinVCF-OS qui
fait ``QVariantMap = to_qml_payload(result)`` côté Python et bind le dict
sur la vue via ``moduleRunService.analysisComplete``).

Le payload produit suit la même structure que le rendu JSON existant
(`PharmGxModule._render_json` du module PharmGx) afin que les vues QML
puissent consommer indifféremment :

* le payload streamé en mémoire (chemin in-app, performant)
* le rapport JSON exporté sur disque (chemin archivage / partage)

Convention des types primitifs côté QML :

* str, int, float, bool, None
* list[primitif]
* dict[str, primitif]
* enums sérialisés via ``.value``
* datetime sérialisés via ``.isoformat()``

Toute classe non sérialisable lèvera ``TypeError`` à la conversion
``QVariantMap`` côté PySide6, ce qui rendrait la vue muette. La fonction
``to_qml_payload`` est donc défensive : elle convertit explicitement
tout ce qui doit l'être.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from clinvcf_sdk.types import (
    DrugRecommendation,
    ModuleResult,
)


def _safe(v: Any) -> Any:
    """Convertit récursivement en types JSON/QVariant-friendly.

    * datetime/date  → ISO 8601 string
    * Enum (str)     → .value
    * dict           → traite chaque valeur
    * list/tuple/set → liste avec valeurs traitées
    * primitifs      → tels quels
    * autres         → str(v) en dernier recours
    """
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if hasattr(v, "value") and isinstance(getattr(v, "value", None), (str, int)):
        # Enum : on prend .value (les CallStatus, CriticalityLevel etc.
        # héritent de str+Enum, donc isinstance(v, str) est déjà True
        # plus haut. Ce cas couvre les enums non-str.)
        return v.value
    if isinstance(v, dict):
        return {str(k): _safe(val) for k, val in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_safe(item) for item in v]
    return str(v)


def _gene_to_payload(gr: Any) -> dict[str, Any]:
    """Sérialise un GeneCallResult en dict QML-friendly."""
    raw_evidence = getattr(gr, "raw_evidence", None) or {}
    coverage = getattr(gr, "coverage", None)
    return {
        "gene": gr.gene,
        "diplotype": gr.diplotype,
        "phenotype": gr.phenotype,
        "phenotype_fr": raw_evidence.get("phenotype_fr") if isinstance(raw_evidence, dict) else None,
        "activity_score": gr.activity_score,
        "status": gr.status.value if hasattr(gr.status, "value") else str(gr.status),
        "confidence": gr.confidence.value if hasattr(gr.confidence, "value") else str(gr.confidence),
        "criticality": gr.criticality.value if hasattr(gr.criticality, "value") else str(gr.criticality),
        "coverage": {
            "called": getattr(coverage, "called_count", 0),
            "required": getattr(coverage, "total_positions_required", 0),
            "missing": getattr(coverage, "missing_count", 0),
            "low_quality": getattr(coverage, "low_quality_count", 0),
        } if coverage is not None else {"called": 0, "required": 0, "missing": 0, "low_quality": 0},
        "warnings": list(gr.warnings) if gr.warnings else [],
    }


def _recommendation_to_payload(r: DrugRecommendation) -> dict[str, Any]:
    """Sérialise une DrugRecommendation en dict QML-friendly."""
    guideline = r.guideline_source
    return {
        "drug": r.drug_name,
        "atc_code": r.atc_code,
        "related_genes": list(r.related_genes),
        "criticality": r.criticality.value if hasattr(r.criticality, "value") else str(r.criticality),
        "action_required": r.action_required,
        "recommendation_text": r.recommendation_text,
        "guideline": {
            "name": getattr(guideline, "name", ""),
            "version": getattr(guideline, "version", ""),
            "url": getattr(guideline, "url", None),
        },
    }


def to_qml_payload(
    result: ModuleResult,
    *,
    recommendations: list[DrugRecommendation] | None = None,
    executive_summary: list[dict[str, Any]] | None = None,
    disclaimers: list[dict[str, Any]] | None = None,
    report_reference: str | None = None,
    language: str = "fr",
) -> dict[str, Any]:
    """Construit un dict QML-friendly à partir d'un ``ModuleResult``.

    Args:
        result: Résultat ``ModuleResult`` à sérialiser.
        recommendations: Liste de recommandations triées (ex. par criticité
            décroissante). Si None, déduites des ``gene_results[i].recommendations``
            (avec déduplication par identité).
        executive_summary: Résumé exécutif pré-calculé sous forme de liste
            de dicts ``{label, criticality, count, related_genes}``. Si None,
            calculé depuis les ``gene_results``.
        disclaimers: Disclaimers déjà sérialisés ``{title, body, severity}``.
            Si None, le payload contient une liste vide (le module peut
            les ajouter dans ``ClinVCFModule.to_qml_payload`` overridé).
        report_reference: Référence textuelle du rapport (ex. PHARMG-...).
            Si None, calculée depuis l'horodatage et le module_id.
        language: Langue du rapport ("fr" ou "en").

    Returns:
        Dict QML-friendly avec la structure standardisée ClinVCF.
    """
    if recommendations is None:
        recommendations = []
        seen: set[int] = set()
        for gr in result.gene_results:
            for r in (gr.recommendations or []):
                if id(r) not in seen:
                    seen.add(id(r))
                    recommendations.append(r)

    if executive_summary is None:
        from clinvcf_sdk.reporting.summary import ExecutiveSummary

        es = ExecutiveSummary.from_result(result, language=language)
        executive_summary = [
            {
                "label": e.label,
                "criticality": e.criticality.value,
                "count": e.count,
                "related_genes": list(e.related_genes),
            }
            for e in es.entries
        ]

    if report_reference is None:
        ts = result.executed_at or datetime.utcnow()
        # Format aligné avec PharmGx : <ID en majuscules>-YYYYMMDD-HHMMSS
        token = result.module_id.upper().replace("-", "").replace("_", "")[:8]
        report_reference = f"{token}-{ts.strftime('%Y%m%d-%H%M%S')}"

    return {
        "module": {
            "id": result.module_id,
            "version": result.module_version,
            "sdk_version": result.sdk_version,
        },
        "report": {
            "reference": report_reference,
            "generated_at": result.executed_at.isoformat() if result.executed_at else None,
            "language": language,
        },
        "patient_metadata": _safe(result.patient_metadata) if result.patient_metadata else None,
        "executive_summary": executive_summary,
        "gene_results": [_gene_to_payload(gr) for gr in result.gene_results],
        "recommendations": [_recommendation_to_payload(r) for r in recommendations],
        "disclaimers": disclaimers if disclaimers is not None else [],
        "metadata": _safe(result.execution_metadata) if result.execution_metadata else {},
    }
