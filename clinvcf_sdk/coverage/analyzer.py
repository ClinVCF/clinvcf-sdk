"""Analyse de couverture d'un VCF pour un gène donné.

Le ``CoverageAnalyzer`` ouvre un VCF et inspecte la couverture aux positions
pharmacogénomiques spécifiées. Il produit un ``CoverageReport`` qui décrit
exactement quelles positions sont couvertes, lesquelles manquent, lesquelles
sont de qualité insuffisante.

L'analyseur est volontairement *séparé* du caller : il ne fait pas d'appel
de génotype, il décrit juste ce que le VCF contient. Le caller du module
utilise ensuite ce rapport pour décider du ``CallStatus`` et de la
``ConfidenceLevel``.

L'analyseur supporte deux modes :

* **Mode ``cyvcf2``** (recommandé) — utilise la lib cyvcf2 si installée,
  rapide sur de gros VCF, supporte les VCF compressés .vcf.gz
* **Mode ``parser``** (fallback) — parser Python pur, sans dépendance,
  fonctionne sur des VCF plain text de petite/moyenne taille
"""
from __future__ import annotations

import gzip
import logging
from pathlib import Path
from typing import Iterable

from clinvcf_sdk.exceptions import VCFParsingError
from clinvcf_sdk.types import (
    CoveragePosition,
    CoverageReport,
    GenomicPosition,
    GeneticReference,
)

logger = logging.getLogger(__name__)


class CoverageAnalyzer:
    """Analyseur de couverture pour un fichier VCF.

    Args:
        vcf_path: Chemin du fichier VCF (texte ou gz).
        min_depth: Profondeur minimale (DP) pour considérer une position
            comme correctement couverte.
        min_genotype_quality: Qualité de génotypage minimale (GQ).
        reference: Référence génomique attendue (GRCh37 ou GRCh38).
        backend: "cyvcf2" (auto-détecté), "parser" (fallback Python pur),
            ou "auto" pour choisir automatiquement.
    """

    def __init__(
        self,
        vcf_path: str | Path,
        *,
        min_depth: int = 10,
        min_genotype_quality: int = 20,
        reference: GeneticReference = GeneticReference.GRCH38,
        backend: str = "auto",
    ) -> None:
        self.vcf_path = Path(vcf_path)
        if not self.vcf_path.exists():
            raise VCFParsingError(
                f"Fichier VCF introuvable : {self.vcf_path}",
                code="vcf_not_found",
                details={"path": str(self.vcf_path)},
            )

        self.min_depth = min_depth
        self.min_genotype_quality = min_genotype_quality
        self.reference = reference
        self.backend = self._resolve_backend(backend)
        self._records_cache: list[dict] | None = None

        logger.debug(
            "CoverageAnalyzer initialized for %s (backend=%s, ref=%s)",
            self.vcf_path,
            self.backend,
            self.reference.value,
        )

    @staticmethod
    def _resolve_backend(backend: str) -> str:
        if backend == "auto":
            try:
                import cyvcf2  # noqa: F401
                return "cyvcf2"
            except ImportError:
                return "parser"
        return backend

    def analyze_gene(
        self,
        gene: str,
        required_positions: Iterable[GenomicPosition],
        *,
        position_metadata: dict[str, dict] | None = None,
    ) -> CoverageReport:
        """Analyse la couverture du VCF pour les positions clés d'un gène.

        Args:
            gene: Symbole HGNC du gène (ex. "DPYD").
            required_positions: Positions clés à inspecter pour ce gène.
            position_metadata: Méta-données optionnelles indexées par
                "{chrom}:{pos}", contenant par exemple {"rsid": "rs3918290",
                "allele_label": "*2A defining"}.

        Returns:
            ``CoverageReport`` décrivant l'état de chaque position.
        """
        required = list(required_positions)
        position_metadata = position_metadata or {}

        records_by_key = self._index_records(required)
        positions: list[CoveragePosition] = []

        for pos in required:
            key = f"{pos.chromosome}:{pos.position}"
            meta = position_metadata.get(key, {})
            record = records_by_key.get(key)

            if record is None:
                positions.append(
                    CoveragePosition(
                        position=pos,
                        rsid=meta.get("rsid"),
                        allele_label=meta.get("allele_label"),
                        is_covered=False,
                        is_called=False,
                    )
                )
                continue

            depth = record.get("DP")
            gq = record.get("GQ")
            genotype = record.get("GT")

            quality_ok = (
                (depth is None or depth >= self.min_depth)
                and (gq is None or gq >= self.min_genotype_quality)
            )
            is_called = genotype is not None and genotype != "./." and quality_ok

            positions.append(
                CoveragePosition(
                    position=pos,
                    rsid=meta.get("rsid"),
                    allele_label=meta.get("allele_label"),
                    is_covered=True,
                    depth=depth,
                    genotype_quality=gq,
                    is_called=is_called,
                )
            )

        called_count = sum(1 for p in positions if p.is_called)
        missing_count = sum(1 for p in positions if not p.is_covered)
        low_quality_count = sum(
            1 for p in positions if p.is_covered and not p.is_called
        )

        return CoverageReport(
            gene=gene,
            total_positions_required=len(required),
            positions=positions,
            called_count=called_count,
            missing_count=missing_count,
            low_quality_count=low_quality_count,
        )

    def detect_indel_at(
        self,
        chromosome: str,
        position: int,
        *,
        min_size: int = 1,
    ) -> bool:
        """Détecte la présence d'un INDEL à une position donnée.

        Utile notamment pour UGT1A1*28 (TA-repeat) et d'autres allèles
        définis par un indel plutôt qu'un SNV simple.
        """
        records = self._index_records(
            [GenomicPosition(chromosome, position, self.reference)]
        )
        record = records.get(f"{chromosome}:{position}")
        if record is None:
            return False

        ref = record.get("REF", "")
        alts = record.get("ALT", [])
        for alt in alts:
            size_diff = abs(len(alt) - len(ref))
            if size_diff >= min_size:
                return True
        return False

    def _index_records(
        self, positions: list[GenomicPosition]
    ) -> dict[str, dict]:
        """Indexe les records VCF par "{chrom}:{pos}" (cached)."""
        if self._records_cache is None:
            self._records_cache = list(self._iter_records())

        wanted_keys = {f"{p.chromosome}:{p.position}" for p in positions}
        return {
            f"{r['CHROM']}:{r['POS']}": r
            for r in self._records_cache
            if f"{r['CHROM']}:{r['POS']}" in wanted_keys
        }

    def _iter_records(self):
        """Itère les records du VCF, agnostic du backend."""
        if self.backend == "cyvcf2":
            yield from self._iter_cyvcf2()
        else:
            yield from self._iter_parser()

    def _iter_cyvcf2(self):
        try:
            from cyvcf2 import VCF
        except ImportError as e:
            raise VCFParsingError(
                "cyvcf2 backend requested but library is not installed. "
                "Install with: pip install 'clinvcf-sdk[vcf]'",
                code="backend_unavailable",
            ) from e

        try:
            for v in VCF(str(self.vcf_path)):
                fmt = (v.FORMAT or [])[0] if v.FORMAT else None
                gt_string = (
                    v.gt_bases[0] if hasattr(v, "gt_bases") and len(v.gt_bases) else None
                )
                yield {
                    "CHROM": str(v.CHROM),
                    "POS": int(v.POS),
                    "REF": v.REF,
                    "ALT": list(v.ALT) if v.ALT else [],
                    "DP": int(v.INFO.get("DP")) if v.INFO.get("DP") is not None else None,
                    "GQ": int(v.gt_quals[0]) if hasattr(v, "gt_quals") and len(v.gt_quals) and v.gt_quals[0] >= 0 else None,
                    "GT": gt_string,
                    "FORMAT": fmt,
                }
        except Exception as e:
            raise VCFParsingError(
                f"Erreur de parsing cyvcf2 : {e}",
                code="cyvcf2_parsing_error",
                details={"path": str(self.vcf_path)},
            ) from e

    def _iter_parser(self):
        opener = gzip.open if self.vcf_path.suffix == ".gz" else open
        try:
            with opener(self.vcf_path, "rt", encoding="utf-8") as f:
                header_format_idx: list[str] | None = None
                for line in f:
                    if line.startswith("#"):
                        continue
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 8:
                        continue

                    record = {
                        "CHROM": parts[0],
                        "POS": int(parts[1]),
                        "REF": parts[3],
                        "ALT": parts[4].split(","),
                    }

                    info = self._parse_info(parts[7])
                    record["DP"] = (
                        int(info["DP"]) if "DP" in info and info["DP"].isdigit() else None
                    )

                    if len(parts) >= 10:
                        format_keys = parts[8].split(":")
                        sample_values = parts[9].split(":")
                        sample = dict(zip(format_keys, sample_values))
                        record["GT"] = sample.get("GT")
                        gq = sample.get("GQ")
                        record["GQ"] = int(gq) if gq and gq.isdigit() else None
                        if record["DP"] is None and "DP" in sample:
                            record["DP"] = int(sample["DP"]) if sample["DP"].isdigit() else None
                    else:
                        record["GT"] = None
                        record["GQ"] = None

                    yield record
        except (OSError, ValueError) as e:
            raise VCFParsingError(
                f"Erreur de parsing VCF (parser pur) : {e}",
                code="parser_error",
                details={"path": str(self.vcf_path)},
            ) from e

    @staticmethod
    def _parse_info(info_str: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for entry in info_str.split(";"):
            if "=" in entry:
                k, v = entry.split("=", 1)
                result[k] = v
            else:
                result[entry] = "1"
        return result
