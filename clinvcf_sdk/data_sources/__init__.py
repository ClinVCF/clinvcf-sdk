"""Helpers pour le pattern hybride embedded + remote des données scientifiques.

Pattern :

* Le module embarque un **snapshot** des données scientifiques (PharmVar,
  CPIC, ClinVar, etc.) à un instant T, dans son répertoire ``data/``.
* Optionnellement, le module peut être configuré pour rafraîchir ces
  données depuis l'API officielle de la source (``mode: "remote"`` ou
  ``"hybrid"``).
* En mode ``hybrid`` (recommandé), le module utilise le snapshot embarqué
  par défaut, et tente un refresh périodique en arrière-plan. Si le refresh
  échoue, il bascule sur l'embarqué. Les données fraîches sont mises en
  cache local.

Usage :

    from clinvcf_sdk.data_sources import HybridDataSource

    source = HybridDataSource(
        name="cpic_guidelines",
        embedded_dir=module_dir / "data" / "cpic_v2026.1",
        remote_url="https://api.cpicpgx.org/v1/guidelines",
        cache_dir=Path("~/.clinvcf/cache/cpic").expanduser(),
        mode="hybrid",
        refresh_interval_days=30,
    )

    data = source.load()  # dict du JSON, soit embarqué soit rafraîchi
"""

from clinvcf_sdk.data_sources.hybrid import HybridDataSource, DataSourceMode

__all__ = ["HybridDataSource", "DataSourceMode"]
