"""Types centraux du SDK ClinVCF.

Ce module définit les enums et dataclasses que TOUS les modules tiers
(et les modules Fdevelopment) doivent utiliser pour exprimer leurs
résultats. C'est le contrat sémantique qui garantit qu'un clinicien
voit toujours la même grammaire, quel que soit le module qui a produit
le rapport.

Les 4 enums centraux :

* ``CallStatus``         : qu'est-ce que l'algorithme a produit pour ce gène/variant ?
* ``ConfidenceLevel``    : avec quelle fiabilité méthodologique ?
* ``CriticalityLevel``   : quel impact clinique potentiel ?
* ``ReportFormat``       : quel format de rendu ?

Et trois dataclasses :

* ``CoverageReport``     : décrit la couverture d'un panel pour un gène donné
* ``DataSourceRef``      : référence traçable vers une source scientifique
* ``GeneCallResult``     : résultat standardisé pour un gène
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class CallStatus(str, Enum):
    """Statut de l'appel d'un gène ou d'un variant.

    Cette grammaire est CRITIQUE pour la rigueur clinique : elle distingue
    entre "appelé avec confiance", "inféré par défaut", "non évaluable",
    et "bloqué techniquement". Un module qui ne respecterait pas cette
    distinction (par exemple en marquant comme NORMAL un gène dont les
    positions clés ne sont pas couvertes) serait scientifiquement trompeur.

    Valeurs :

    * ``CALLED`` : appelé avec haute confiance, toutes positions clés couvertes
      avec qualité suffisante. C'est le statut "normal" pour un panel
      pharmacogénomique correctement conçu.
    * ``CALLED_EXPERIMENTAL`` : appelé mais en mode expérimental opt-in.
      Le rapport DOIT afficher un avertissement permanent (ex. CYP2D6 depuis
      VCF, où les CNV/SV ne sont pas évalués).
    * ``INFERRED`` : inféré comme allèle de référence par défaut (aucun
      variant détecté aux positions surveillées). À distinguer de ``CALLED``
      car l'absence de variant peut être due à un drop-out de couverture.
    * ``LOW_CONFIDENCE`` : appel possible mais avec confiance dégradée
      (couverture incomplète, qualité limite, allèle ambigu).
    * ``NOT_EVALUABLE`` : techniquement non appelable depuis les inputs
      fournis (ex. HLA depuis VCF, CYP2D6 sans données structurales).
      Le module a refusé de produire un appel.
    * ``NOT_COVERED`` : positions pharmacogénomiques importantes absentes
      du panel utilisé. Le panel n'est pas conçu pour ce gène.
    * ``BLOCKED`` : le SDK ou le module a refusé l'évaluation par mesure
      de sécurité (ex. tentative d'imputer HLA depuis VCF — bloqué par
      principe en raison du risque clinique).

    En interface utilisateur, ``NOT_EVALUABLE``, ``NOT_COVERED`` et
    ``BLOCKED`` doivent être affichés visuellement EN GRIS, jamais en vert.
    Confondre l'absence de variant détecté avec la confirmation d'un
    génotype normal est l'erreur la plus dangereuse en pharmacogénomique.
    """

    CALLED = "called"
    CALLED_EXPERIMENTAL = "called_experimental"
    INFERRED = "inferred"
    LOW_CONFIDENCE = "low_confidence"
    NOT_EVALUABLE = "not_evaluable"
    NOT_COVERED = "not_covered"
    BLOCKED = "blocked"

    @property
    def is_actionable(self) -> bool:
        """True si le statut autorise la génération d'une recommandation clinique."""
        return self in (
            CallStatus.CALLED,
            CallStatus.CALLED_EXPERIMENTAL,
            CallStatus.INFERRED,
        )

    @property
    def requires_disclaimer(self) -> bool:
        """True si un avertissement spécifique doit accompagner ce statut."""
        return self in (
            CallStatus.CALLED_EXPERIMENTAL,
            CallStatus.LOW_CONFIDENCE,
            CallStatus.INFERRED,
        )


class ConfidenceLevel(str, Enum):
    """Niveau de confiance méthodologique pour un appel.

    À distinguer du ``CallStatus`` : le ``CallStatus`` dit *ce qui a été fait*,
    le ``ConfidenceLevel`` dit *à quel point on peut s'y fier*. Un appel
    ``CALLED`` peut avoir une confiance ``HIGH`` (panel adapté, couverture
    complète) ou ``MEDIUM`` (couverture partielle mais suffisante).

    Valeurs :

    * ``HIGH`` : variants couverts par le panel, méthodologie adaptée,
      qualité QV et profondeur supérieures aux seuils du module.
    * ``MEDIUM`` : couverture > 80% des positions critiques mais quelques
      positions manquantes ou de qualité limite.
    * ``LOW`` : méthodologie partielle ou inadéquate (ex. CYP2D6 depuis
      VCF SNV sans données CNV). Confiance affichée explicitement.
    * ``NOT_APPLICABLE`` : gène non évalué (statut ``NOT_EVALUABLE``,
      ``NOT_COVERED`` ou ``BLOCKED``).
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOT_APPLICABLE = "not_applicable"


class CriticalityLevel(str, Enum):
    """Niveau de criticité clinique d'un résultat.

    Cette échelle est ce qui apparaît dans le résumé exécutif du rapport.
    La distinction entre ``ABSOLUTE_CONTRAINDICATION`` et ``MAJOR_ALERT``
    est cruciale et juridiquement importante : on ne doit JAMAIS afficher
    "contre-indiqué" sur un médicament dont la guideline parle d'adaptation
    de dose. Un clinicien qui voit "contre-indiqué" peut renoncer à un
    traitement curatif.

    Valeurs :

    * ``ABSOLUTE_CONTRAINDICATION`` : guideline = "do not use", "avoid".
      Exemple : abacavir + HLA-B*57:01.
    * ``MAJOR_ALERT`` : adaptation impérative, risque toxicité sévère ou
      manque d'efficacité majeur. Exemple : DPYD IM + 5-FU (réduction
      de dose 50% recommandée).
    * ``PRECAUTION`` : adaptation conseillée. Exemple : CYP2C19 PM +
      clopidogrel (alternative à privilégier).
    * ``NORMAL`` : métabolisation standard, aucune adaptation indiquée
      pour les positions évaluées.
    * ``NOT_EVALUABLE`` : criticité non déterminable (typiquement quand
      ``CallStatus`` est ``NOT_EVALUABLE`` ou ``BLOCKED``). Affichage
      en gris dans le rapport, JAMAIS en vert.
    """

    ABSOLUTE_CONTRAINDICATION = "absolute_contraindication"
    MAJOR_ALERT = "major_alert"
    PRECAUTION = "precaution"
    NORMAL = "normal"
    NOT_EVALUABLE = "not_evaluable"

    @property
    def color_class(self) -> str:
        """Classe CSS standardisée pour le rendu HTML/PDF."""
        return {
            CriticalityLevel.ABSOLUTE_CONTRAINDICATION: "criticality-absolute",
            CriticalityLevel.MAJOR_ALERT: "criticality-major",
            CriticalityLevel.PRECAUTION: "criticality-precaution",
            CriticalityLevel.NORMAL: "criticality-normal",
            CriticalityLevel.NOT_EVALUABLE: "criticality-unknown",
        }[self]

    @property
    def label_fr(self) -> str:
        """Libellé en français pour affichage."""
        return {
            CriticalityLevel.ABSOLUTE_CONTRAINDICATION: "Contre-indication absolue",
            CriticalityLevel.MAJOR_ALERT: "Alerte majeure",
            CriticalityLevel.PRECAUTION: "Précaution",
            CriticalityLevel.NORMAL: "Normal",
            CriticalityLevel.NOT_EVALUABLE: "Non évaluable",
        }[self]

    @property
    def label_en(self) -> str:
        """English label for display."""
        return {
            CriticalityLevel.ABSOLUTE_CONTRAINDICATION: "Absolute contraindication",
            CriticalityLevel.MAJOR_ALERT: "Major alert",
            CriticalityLevel.PRECAUTION: "Precaution",
            CriticalityLevel.NORMAL: "Normal",
            CriticalityLevel.NOT_EVALUABLE: "Not evaluable",
        }[self]


class ReportFormat(str, Enum):
    """Formats de rendu pris en charge par le SDK.

    * ``HTML``, ``PDF``, ``JSON`` : formats binaires/texte sérialisés en
      ``bytes`` par ``ClinVCFModule.render_report``. Destinés à l'export
      vers le système de fichiers (téléchargement utilisateur).
    * ``QML_PAYLOAD`` : retourne un ``dict`` Python directement consommable
      par QML via ``QVariantMap``. Destiné à l'affichage in-app dans
      ClinVCF-OS, sans WebView. Voir ``ClinVCFModule.to_qml_payload``.
    """

    HTML = "html"
    PDF = "pdf"
    JSON = "json"
    QML_PAYLOAD = "qml_payload"


class GeneticReference(str, Enum):
    """Référence génomique du VCF analysé."""

    GRCH37 = "GRCh37"
    GRCH38 = "GRCh38"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class GenomicPosition:
    """Position génomique normalisée."""

    chromosome: str
    position: int
    reference: GeneticReference = GeneticReference.GRCH38

    def __str__(self) -> str:
        return f"{self.chromosome}:{self.position} ({self.reference.value})"


@dataclass(frozen=True, slots=True)
class DataSourceRef:
    """Référence traçable vers une source scientifique utilisée par le module.

    Tout résultat doit pouvoir être tracé jusqu'à sa source : guideline CPIC,
    table d'allèles PharmVar, recommandation DPWG, etc. Cette traçabilité
    est obligatoire dans les rapports cliniques.

    Exemple :
        DataSourceRef(
            name="CPIC",
            version="2026.1",
            snapshot_date=date(2026, 4, 15),
            url="https://cpicpgx.org/guidelines/guideline-for-fluoropyrimidines-and-dpyd/",
            guideline_id="CPIC-DPYD-FLUOROPYRIMIDINES-2017",
        )
    """

    name: str
    version: str
    snapshot_date: date
    url: str | None = None
    guideline_id: str | None = None
    citation: str | None = None


@dataclass(slots=True)
class CoveragePosition:
    """Statut de couverture d'une position pharmacogénomique précise."""

    position: GenomicPosition
    rsid: str | None
    allele_label: str | None
    is_covered: bool
    depth: int | None = None
    genotype_quality: int | None = None
    is_called: bool = False


@dataclass(slots=True)
class CoverageReport:
    """Description structurée de la couverture d'un panel pour un gène.

    Permet à un clinicien de savoir EXACTEMENT quelles positions ont été
    interrogées, lesquelles sont couvertes avec qualité suffisante, et
    lesquelles manquent. C'est ce qui transforme un "Normal" rassurant
    mais creux en "Normal sur les 5/5 positions critiques surveillées".

    Attributes:
        gene: Nom du gène (ex. "DPYD")
        total_positions_required: Nombre de positions clés du gène selon
            la définition de référence (PharmVar pour star alleles).
        positions: Liste détaillée du statut de chaque position.
        called_count: Nombre de positions effectivement appelées.
        missing_count: Nombre de positions absentes du VCF ou non couvertes.
        low_quality_count: Nombre de positions présentes mais de qualité
            insuffisante (DP/QV sous les seuils du module).
        special_features: Caractéristiques particulières détectées
            (ex. {"ta_repeat_detected": True} pour UGT1A1*28).
        notes: Messages explicatifs pour le rapport.
    """

    gene: str
    total_positions_required: int
    positions: list[CoveragePosition] = field(default_factory=list)
    called_count: int = 0
    missing_count: int = 0
    low_quality_count: int = 0
    special_features: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def coverage_ratio(self) -> float:
        """Ratio des positions correctement appelées sur le total requis."""
        if self.total_positions_required == 0:
            return 0.0
        return self.called_count / self.total_positions_required

    @property
    def is_complete(self) -> bool:
        """True si toutes les positions requises ont été appelées avec qualité."""
        return (
            self.missing_count == 0
            and self.low_quality_count == 0
            and self.called_count == self.total_positions_required
        )

    def summary_label(self) -> str:
        """Libellé compact pour le rapport (ex. ``5/5 pos.``, ``TA-rep ✓``)."""
        if self.special_features.get("ta_repeat_detected") is True:
            return "TA-rep ✓"
        if self.special_features.get("ta_repeat_detected") is False:
            return "TA-rep ✗"
        return f"{self.called_count}/{self.total_positions_required} pos."


@dataclass(slots=True)
class GeneCallResult:
    """Résultat standardisé pour un gène analysé par un module.

    C'est la structure de sortie centrale du SDK. Tout module qui produit
    des résultats par gène doit retourner une liste de ``GeneCallResult``.
    Cette uniformité permet à ClinVCF de présenter les résultats de
    n'importe quel module avec la même grammaire.

    Attributes:
        gene: Symbole HGNC du gène (ex. "DPYD", "CYP2C19").
        diplotype: Diplotype appelé (ex. "*1/*2A") ou None si non évaluable.
        activity_score: Score d'activité (CPIC). None si non applicable.
        phenotype: Phénotype dérivé (ex. "Intermediate Metabolizer", FR ou EN).

        status: Statut de l'appel (cf. CallStatus).
        confidence: Niveau de confiance méthodologique (cf. ConfidenceLevel).
        criticality: Criticité clinique du résultat (cf. CriticalityLevel).

        coverage: Détail structuré de la couverture du panel pour ce gène.
        warnings: Avertissements à afficher dans le rapport.
        recommendations: Recommandations cliniques liées (par médicament).
        data_sources: Sources scientifiques tracées utilisées pour ce résultat.

        raw_evidence: Données brutes pour audit (variants détectés, etc.).
    """

    gene: str
    diplotype: str | None
    activity_score: float | None
    phenotype: str | None

    status: CallStatus
    confidence: ConfidenceLevel
    criticality: CriticalityLevel

    coverage: CoverageReport
    warnings: list[str] = field(default_factory=list)
    recommendations: list["DrugRecommendation"] = field(default_factory=list)
    data_sources: list[DataSourceRef] = field(default_factory=list)

    raw_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DrugRecommendation:
    """Recommandation clinique liée à un médicament.

    Une recommandation est toujours rattachée à un gène (ou plusieurs) et
    à une guideline sourcée et versionnée. Si le module ne peut pas générer
    une recommandation fiable (statut ``NOT_EVALUABLE`` du gène), il doit
    explicitement créer une recommandation avec criticité ``NOT_EVALUABLE``
    plutôt que d'omettre silencieusement, pour que le clinicien voie
    l'absence d'analyse comme une information à part entière.

    Attributes:
        drug_name: Nom du médicament (ex. "5-Fluorouracile / Capécitabine").
        atc_code: Code ATC si disponible.
        related_genes: Gènes pharmacogénomiques en jeu.
        recommendation_text: Texte de la recommandation, en français par
            défaut, traduit dans la langue configurée du rapport.
        criticality: Niveau de criticité clinique (cf. CriticalityLevel).
        guideline_source: Référence vers la guideline applicable.
        action_required: Description courte de l'action attendue
            (ex. "Réduire dose 50%", "Privilégier alternative").
    """

    drug_name: str
    related_genes: list[str]
    recommendation_text: str
    criticality: CriticalityLevel
    guideline_source: DataSourceRef
    action_required: str | None = None
    atc_code: str | None = None


@dataclass(slots=True)
class ModuleResult:
    """Résultat global de l'exécution d'un module pour un patient.

    C'est ce que la méthode ``ClinVCFModule.run()`` retourne. ClinVCF
    consomme cette structure pour générer les rapports et l'archiver.

    Attributes:
        module_id: Identifiant du module (ex. "pharmgx").
        module_version: Version du module qui a produit le résultat.
        sdk_version: Version du SDK utilisée à l'exécution.
        executed_at: Horodatage UTC de l'exécution.

        gene_results: Liste des résultats par gène analysé.
        global_warnings: Avertissements applicables à tout le rapport.
        excluded_genes: Gènes désactivés par configuration ou non évaluables.
        execution_metadata: Méta-données d'exécution (durée, ressources).

        patient_metadata: Méta-données du patient si fournies (anonymisées).
    """

    module_id: str
    module_version: str
    sdk_version: str
    executed_at: datetime

    gene_results: list[GeneCallResult] = field(default_factory=list)
    global_warnings: list[str] = field(default_factory=list)
    excluded_genes: list[str] = field(default_factory=list)
    execution_metadata: dict[str, Any] = field(default_factory=dict)

    patient_metadata: dict[str, Any] | None = None

    def summary_counts(self) -> dict[CriticalityLevel, int]:
        """Compte les résultats par niveau de criticité (pour résumé exécutif)."""
        counts = dict.fromkeys(CriticalityLevel, 0)
        for r in self.gene_results:
            counts[r.criticality] += 1
        return counts


@dataclass(slots=True)
class ValidationResult:
    """Résultat de la validation des inputs avant exécution du module."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    inferred_metadata: dict[str, Any] = field(default_factory=dict)
