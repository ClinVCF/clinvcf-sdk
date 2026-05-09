"""Helpers de génération de rapports cliniques.

Fournit :

* ``ClinicalDisclaimer`` — disclaimers cliniques standardisés (RUO, médical,
  méthodologique). Le SDK refuse de rendre un rapport sans disclaimer en
  mode ``clinical``.
* ``ExecutiveSummary`` — calcul du résumé exécutif (nombre de gènes par
  niveau de criticité) à partir d'un ``ModuleResult``.
* ``ReportContext`` — contexte unifié passé aux templates Jinja2.

Usage :

    from clinvcf_sdk.reporting import ClinicalDisclaimer, ExecutiveSummary

    summary = ExecutiveSummary.from_result(result)
    disclaimer = ClinicalDisclaimer.for_report(language="fr")
"""

from clinvcf_sdk.reporting.context import ReportContext
from clinvcf_sdk.reporting.disclaimer import ClinicalDisclaimer
from clinvcf_sdk.reporting.qml_payload import to_qml_payload
from clinvcf_sdk.reporting.summary import ExecutiveSummary

__all__ = [
    "ClinicalDisclaimer",
    "ExecutiveSummary",
    "ReportContext",
    "to_qml_payload",
]
