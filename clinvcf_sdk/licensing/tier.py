"""Tiers d'abonnement ClinVCF."""
from __future__ import annotations

from enum import Enum


class Tier(str, Enum):
    """Tier d'abonnement ClinVCF d'un utilisateur final.

    L'inclusion d'un module dans un tier est définie par le manifest
    (champ ``pricing.tier_inclusion``).
    """

    COMMUNITY = "community"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"

    @property
    def has_unlimited_quota(self) -> bool:
        """True si ce tier n'a pas de quota par défaut."""
        return self in (Tier.PRO, Tier.TEAM, Tier.ENTERPRISE)
