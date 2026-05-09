"""Vérification de licence runtime pour les modules ClinStore.

Mécanisme :

* Format JWT avec signature **Ed25519** (asymétrique moderne).
  ClinStore signe avec sa clé privée ; le SDK vérifie avec la clé publique
  de Fdevelopment embarquée dans le SDK.
* **Grace period offline configurable par module** (par défaut 30 jours).
  Pendant cette période, le module continue de fonctionner même sans
  contacter ClinStore.
* **Ping de vérification quotidien** : quand internet est disponible, le
  SDK contacte ClinStore une fois par jour pour rafraîchir la licence.
* Tolérant aux pannes : si ClinStore est inaccessible, on bascule sur le
  cache local. La licence n'est invalidée qu'au-delà de la grace period.

Usage typique dans un module :

    from clinvcf_sdk.licensing import LicenseChecker

    checker = LicenseChecker(
        module_id="pharmgx",
        license_token=user_provided_jwt,
        grace_period_days=30,
    )
    license_info = checker.verify()
    if not license_info.is_valid:
        raise LicenseInvalidError(license_info.reason)
    if license_info.quota_exceeded:
        raise QuotaExceededError(...)
"""

from clinvcf_sdk.licensing.checker import LicenseChecker, LicenseInfo
from clinvcf_sdk.licensing.tier import Tier
from clinvcf_sdk.licensing.quota import QuotaTracker

__all__ = [
    "LicenseChecker",
    "LicenseInfo",
    "Tier",
    "QuotaTracker",
]
