"""Calcul du niveau de confiance par gène à partir de la couverture observée.

Reflète directement les retours scientifiques sur la fiabilité du calling
depuis VCF :

* DPYD, TPMT, NUDT15, CYP2C19, CYP2C9, VKORC1, SLCO1B1 → fiable si SNV+INDEL couverts
* UGT1A1 → fiabilité conditionnée à la détection de l'indel TA-repeat
* CYP2D6 → confiance LIMITÉE depuis VCF seul (CNV/SV non évalués)
* HLA-A/HLA-B → NON ÉVALUABLE depuis VCF, pipeline dédié requis

Le ``ConfidenceScorer`` combine :
1. Le profil théorique du gène (qu'est-ce qu'on peut au mieux faire ?)
2. La couverture observée du VCF (qu'est-ce qui est effectivement présent ?)
3. La méthodologie utilisée (SNV+INDEL ? CNV inclus ? Long-read ?)

→ Niveau de confiance final + warnings à afficher dans le rapport.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from clinvcf_sdk.types import (
    CallStatus,
    ConfidenceLevel,
    CoverageReport,
)


class CallingMethod(str, Enum):
    """Méthodologie utilisée pour appeler les variants pharmacogénomiques.

    Différentes méthodes ont des plafonds de confiance différents par gène.
    Par exemple, ``SNV_INDEL`` (le plus courant en NGS clinique) plafonne
    CYP2D6 à ``LOW`` car les CNV ne sont pas évaluables.
    """

    SNV_ONLY = "snv_only"
    SNV_INDEL = "snv_indel"
    SNV_INDEL_CNV = "snv_indel_cnv"
    LONG_READ = "long_read"
    DEDICATED_PIPELINE = "dedicated_pipeline"


@dataclass(frozen=True, slots=True)
class GeneConfidenceProfile:
    """Profil de fiabilité théorique d'un gène selon la méthodologie.

    Pour chaque gène, on définit :
    * Le plafond de confiance atteignable selon la méthodologie utilisée
    * Le ratio minimum de positions couvertes pour ne pas dégrader
    * Les avertissements à afficher systématiquement
    * Si le gène est ``BLOCKED`` à partir d'une certaine méthodologie
    """

    gene: str
    max_confidence_per_method: dict[CallingMethod, ConfidenceLevel]
    min_coverage_ratio_for_high: float = 1.0
    min_coverage_ratio_for_medium: float = 0.8
    persistent_warnings_per_method: dict[CallingMethod, tuple[str, ...]] = None  # type: ignore
    blocked_methods: frozenset[CallingMethod] = frozenset()

    def __post_init__(self) -> None:
        if self.persistent_warnings_per_method is None:
            object.__setattr__(self, "persistent_warnings_per_method", {})


# ============================================================================
# Profils de référence — embarqués dans le SDK pour usage par tous les modules
# ============================================================================

DEFAULT_PROFILES: dict[str, GeneConfidenceProfile] = {
    "DPYD": GeneConfidenceProfile(
        gene="DPYD",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.MEDIUM,
            CallingMethod.SNV_INDEL: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.HIGH,
            CallingMethod.LONG_READ: ConfidenceLevel.HIGH,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
    ),
    "TPMT": GeneConfidenceProfile(
        gene="TPMT",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.HIGH,
            CallingMethod.LONG_READ: ConfidenceLevel.HIGH,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
    ),
    "NUDT15": GeneConfidenceProfile(
        gene="NUDT15",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.HIGH,
            CallingMethod.LONG_READ: ConfidenceLevel.HIGH,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
    ),
    "CYP2C19": GeneConfidenceProfile(
        gene="CYP2C19",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.HIGH,
            CallingMethod.LONG_READ: ConfidenceLevel.HIGH,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
    ),
    "CYP2C9": GeneConfidenceProfile(
        gene="CYP2C9",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.HIGH,
            CallingMethod.LONG_READ: ConfidenceLevel.HIGH,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
    ),
    "VKORC1": GeneConfidenceProfile(
        gene="VKORC1",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.HIGH,
            CallingMethod.LONG_READ: ConfidenceLevel.HIGH,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
    ),
    "SLCO1B1": GeneConfidenceProfile(
        gene="SLCO1B1",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.HIGH,
            CallingMethod.LONG_READ: ConfidenceLevel.HIGH,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
    ),
    "UGT1A1": GeneConfidenceProfile(
        gene="UGT1A1",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.LOW,
            CallingMethod.SNV_INDEL: ConfidenceLevel.HIGH,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.HIGH,
            CallingMethod.LONG_READ: ConfidenceLevel.HIGH,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
        persistent_warnings_per_method={
            CallingMethod.SNV_ONLY: (
                "UGT1A1*28 (variant TA-repeat) ne peut être détecté avec une "
                "méthode SNV uniquement. La confiance est dégradée.",
            ),
        },
    ),
    "CYP2D6": GeneConfidenceProfile(
        gene="CYP2D6",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.LOW,
            CallingMethod.SNV_INDEL: ConfidenceLevel.LOW,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.MEDIUM,
            CallingMethod.LONG_READ: ConfidenceLevel.HIGH,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
        persistent_warnings_per_method={
            CallingMethod.SNV_ONLY: (
                "L'appel CYP2D6 depuis SNV uniquement est peu fiable : les "
                "duplications, délétions et réarrangements structuraux ne "
                "sont pas évalués. Outil dédié recommandé (Stargazer, Cyrius).",
            ),
            CallingMethod.SNV_INDEL: (
                "L'appel CYP2D6 depuis VCF (SNV+INDEL) ne détecte pas les "
                "CNV/SV qui représentent ~75% des allèles cliniquement "
                "pertinents. Outil dédié recommandé (Stargazer, Cyrius).",
            ),
            CallingMethod.SNV_INDEL_CNV: (
                "CYP2D6 reste complexe à appeler ; certains réarrangements "
                "rares peuvent ne pas être détectés.",
            ),
        },
    ),
    "HLA-A": GeneConfidenceProfile(
        gene="HLA-A",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.NOT_APPLICABLE,
            CallingMethod.SNV_INDEL: ConfidenceLevel.NOT_APPLICABLE,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.NOT_APPLICABLE,
            CallingMethod.LONG_READ: ConfidenceLevel.MEDIUM,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
        blocked_methods=frozenset(
            {
                CallingMethod.SNV_ONLY,
                CallingMethod.SNV_INDEL,
                CallingMethod.SNV_INDEL_CNV,
            }
        ),
        persistent_warnings_per_method={
            CallingMethod.SNV_ONLY: (
                "HLA-A ne peut être typé depuis un VCF SNV. Pipeline HLA "
                "dédié requis (PCR-SSO, PCR-SBT, ou typage NGS HLA spécialisé).",
            ),
            CallingMethod.SNV_INDEL: (
                "HLA-A ne peut être typé depuis un VCF. L'imputation HLA "
                "depuis VCF n'est pas considérée comme fiable cliniquement. "
                "Fournir un fichier de typage HLA dédié.",
            ),
            CallingMethod.SNV_INDEL_CNV: (
                "HLA-A ne peut être typé depuis un VCF, même avec CNV. "
                "Fournir un fichier de typage HLA dédié.",
            ),
        },
    ),
    "HLA-B": GeneConfidenceProfile(
        gene="HLA-B",
        max_confidence_per_method={
            CallingMethod.SNV_ONLY: ConfidenceLevel.NOT_APPLICABLE,
            CallingMethod.SNV_INDEL: ConfidenceLevel.NOT_APPLICABLE,
            CallingMethod.SNV_INDEL_CNV: ConfidenceLevel.NOT_APPLICABLE,
            CallingMethod.LONG_READ: ConfidenceLevel.MEDIUM,
            CallingMethod.DEDICATED_PIPELINE: ConfidenceLevel.HIGH,
        },
        blocked_methods=frozenset(
            {
                CallingMethod.SNV_ONLY,
                CallingMethod.SNV_INDEL,
                CallingMethod.SNV_INDEL_CNV,
            }
        ),
        persistent_warnings_per_method={
            CallingMethod.SNV_ONLY: (
                "HLA-B ne peut être typé depuis un VCF SNV. Risque clinique "
                "majeur : faux négatif sur HLA-B*57:01 (abacavir) ou "
                "HLA-B*15:02 (carbamazépine). Pipeline HLA dédié obligatoire.",
            ),
            CallingMethod.SNV_INDEL: (
                "HLA-B ne peut être typé depuis un VCF. L'imputation HLA "
                "depuis VCF n'est pas fiable cliniquement. Faux négatifs "
                "sur HLA-B*57:01 et HLA-B*15:02 = risque vital. Fournir "
                "un fichier de typage HLA dédié.",
            ),
            CallingMethod.SNV_INDEL_CNV: (
                "HLA-B ne peut être typé depuis un VCF, même avec CNV. "
                "Fournir un fichier de typage HLA dédié.",
            ),
        },
    ),
}


@dataclass(slots=True)
class ScoringResult:
    """Résultat du calcul de confiance pour un gène et une méthodologie."""

    confidence: ConfidenceLevel
    suggested_status: CallStatus
    warnings: list[str]


class ConfidenceScorer:
    """Calcule un niveau de confiance pour un gène à partir de la couverture.

    Args:
        profiles: Dictionnaire ``{gene: GeneConfidenceProfile}``. Par défaut,
            utilise les profils embarqués (DPYD, TPMT, CYP2D6, HLA, etc.).
            Les modules peuvent en ajouter ou en surcharger.
    """

    def __init__(
        self, profiles: dict[str, GeneConfidenceProfile] | None = None
    ) -> None:
        self.profiles = dict(DEFAULT_PROFILES)
        if profiles:
            self.profiles.update(profiles)

    def score(
        self,
        coverage: CoverageReport,
        method: CallingMethod = CallingMethod.SNV_INDEL,
    ) -> ScoringResult:
        """Calcule confiance et statut suggéré pour un gène.

        Returns:
            ``ScoringResult`` : niveau de confiance, statut suggéré (à
            appliquer si le caller arrive à matcher un diplotype), et
            avertissements à propager au rapport.
        """
        profile = self.profiles.get(coverage.gene)
        if profile is None:
            return self._score_unknown_gene(coverage)

        if method in profile.blocked_methods:
            warnings = list(
                profile.persistent_warnings_per_method.get(method, ())
            )
            return ScoringResult(
                confidence=ConfidenceLevel.NOT_APPLICABLE,
                suggested_status=CallStatus.BLOCKED,
                warnings=warnings,
            )

        max_conf = profile.max_confidence_per_method.get(
            method, ConfidenceLevel.NOT_APPLICABLE
        )

        if max_conf == ConfidenceLevel.NOT_APPLICABLE:
            warnings = list(
                profile.persistent_warnings_per_method.get(method, ())
            )
            return ScoringResult(
                confidence=ConfidenceLevel.NOT_APPLICABLE,
                suggested_status=CallStatus.NOT_EVALUABLE,
                warnings=warnings,
            )

        warnings = list(profile.persistent_warnings_per_method.get(method, ()))

        if coverage.total_positions_required == 0:
            return ScoringResult(
                confidence=ConfidenceLevel.NOT_APPLICABLE,
                suggested_status=CallStatus.NOT_COVERED,
                warnings=[
                    *warnings,
                    f"Aucune position de référence définie pour {coverage.gene}.",
                ],
            )

        ratio = coverage.coverage_ratio

        if ratio == 0.0:
            return ScoringResult(
                confidence=ConfidenceLevel.NOT_APPLICABLE,
                suggested_status=CallStatus.NOT_COVERED,
                warnings=[
                    *warnings,
                    f"{coverage.gene} : aucune position pharmacogénomique "
                    f"couverte par le panel ({coverage.total_positions_required} "
                    f"positions requises).",
                ],
            )

        if ratio >= profile.min_coverage_ratio_for_high:
            confidence = max_conf
            suggested_status = CallStatus.CALLED
        elif ratio >= profile.min_coverage_ratio_for_medium:
            confidence = self._cap(max_conf, ConfidenceLevel.MEDIUM)
            suggested_status = CallStatus.CALLED
            warnings.append(
                f"{coverage.gene} : couverture partielle "
                f"({coverage.called_count}/{coverage.total_positions_required} "
                "positions). Confiance dégradée."
            )
        else:
            confidence = ConfidenceLevel.LOW
            suggested_status = CallStatus.LOW_CONFIDENCE
            warnings.append(
                f"{coverage.gene} : couverture insuffisante "
                f"({coverage.called_count}/{coverage.total_positions_required} "
                "positions). Résultat à interpréter avec prudence."
            )

        if (
            coverage.gene == "UGT1A1"
            and coverage.special_features.get("ta_repeat_detected") is False
        ):
            confidence = self._cap(confidence, ConfidenceLevel.LOW)
            warnings.append(
                "UGT1A1 : indel TA-repeat (UGT1A1*28) non détecté dans le VCF. "
                "Cet allèle est fréquent et défini par un indel ; assurez-vous "
                "que le pipeline NGS a bien interrogé cette position."
            )

        if method in (CallingMethod.SNV_ONLY, CallingMethod.SNV_INDEL):
            if coverage.gene == "CYP2D6":
                suggested_status = CallStatus.CALLED_EXPERIMENTAL

        return ScoringResult(
            confidence=confidence,
            suggested_status=suggested_status,
            warnings=warnings,
        )

    @staticmethod
    def _cap(level: ConfidenceLevel, ceiling: ConfidenceLevel) -> ConfidenceLevel:
        """Plafonne ``level`` à ``ceiling`` (HIGH > MEDIUM > LOW > NA)."""
        order = {
            ConfidenceLevel.HIGH: 3,
            ConfidenceLevel.MEDIUM: 2,
            ConfidenceLevel.LOW: 1,
            ConfidenceLevel.NOT_APPLICABLE: 0,
        }
        return level if order[level] <= order[ceiling] else ceiling

    @staticmethod
    def _score_unknown_gene(coverage: CoverageReport) -> ScoringResult:
        ratio = coverage.coverage_ratio
        if ratio >= 0.8:
            return ScoringResult(
                confidence=ConfidenceLevel.MEDIUM,
                suggested_status=CallStatus.CALLED,
                warnings=[
                    f"Gène {coverage.gene} non profilé dans le SDK. "
                    "Confiance plafonnée à MEDIUM par sécurité.",
                ],
            )
        return ScoringResult(
            confidence=ConfidenceLevel.LOW,
            suggested_status=CallStatus.LOW_CONFIDENCE,
            warnings=[
                f"Gène {coverage.gene} non profilé dans le SDK et couverture "
                "insuffisante.",
            ],
        )
