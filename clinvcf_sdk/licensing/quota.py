"""Suivi des quotas mensuels (tier Community).

Gère le décompte des rapports/analyses consommés par mois pour les tiers
qui ont une limite. Les tiers Pro/Team/Enterprise n'ont pas de quota.

Usage :

    tracker = QuotaTracker(
        module_id="pharmgx",
        cache_dir=Path("~/.clinvcf/quota").expanduser(),
        max_per_month=5,
    )

    if tracker.is_exceeded():
        raise QuotaExceededError(...)

    tracker.consume()  # à appeler à chaque exécution réussie
    print(f"Restants ce mois : {tracker.remaining()}")
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from clinvcf_sdk.exceptions import QuotaExceededError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class QuotaState:
    """État courant du quota mensuel."""

    period_key: str
    consumed: int
    last_consumption_at: datetime | None


class QuotaTracker:
    """Suit la consommation mensuelle d'un module pour un utilisateur."""

    def __init__(
        self,
        module_id: str,
        *,
        cache_dir: str | Path,
        max_per_month: int | None,
        clock_now=None,
    ) -> None:
        self.module_id = module_id
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_per_month = max_per_month
        self.clock_now = clock_now or (lambda: datetime.now(timezone.utc))

    @property
    def has_unlimited(self) -> bool:
        return self.max_per_month is None or self.max_per_month <= 0

    def is_exceeded(self) -> bool:
        if self.has_unlimited:
            return False
        return self.consumed_this_month() >= (self.max_per_month or 0)

    def remaining(self) -> int | None:
        if self.has_unlimited:
            return None
        return max(0, (self.max_per_month or 0) - self.consumed_this_month())

    def consumed_this_month(self) -> int:
        state = self._load_state()
        return state.consumed if state else 0

    def consume(self, amount: int = 1) -> None:
        if self.has_unlimited:
            return

        state = self._load_state() or QuotaState(
            period_key=self._current_period_key(),
            consumed=0,
            last_consumption_at=None,
        )

        if state.consumed + amount > (self.max_per_month or 0):
            raise QuotaExceededError(
                f"Quota mensuel atteint pour le module {self.module_id} : "
                f"{state.consumed}/{self.max_per_month} rapports.",
                details={
                    "module_id": self.module_id,
                    "consumed": state.consumed,
                    "max_per_month": self.max_per_month,
                    "period": state.period_key,
                },
            )

        state.consumed += amount
        state.last_consumption_at = self.clock_now()
        self._save_state(state)

    def _current_period_key(self) -> str:
        return self.clock_now().strftime("%Y-%m")

    def _state_path(self) -> Path:
        return self.cache_dir / f"{self.module_id}.quota.json"

    def _load_state(self) -> QuotaState | None:
        path = self._state_path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        period_key = data.get("period_key")
        current = self._current_period_key()
        if period_key != current:
            return QuotaState(period_key=current, consumed=0, last_consumption_at=None)

        last_str = data.get("last_consumption_at")
        last_dt: datetime | None = None
        if last_str:
            try:
                last_dt = datetime.fromisoformat(last_str)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                last_dt = None

        return QuotaState(
            period_key=period_key,
            consumed=int(data.get("consumed", 0)),
            last_consumption_at=last_dt,
        )

    def _save_state(self, state: QuotaState) -> None:
        path = self._state_path()
        try:
            path.write_text(
                json.dumps(
                    {
                        "period_key": state.period_key,
                        "consumed": state.consumed,
                        "last_consumption_at": (
                            state.last_consumption_at.isoformat()
                            if state.last_consumption_at
                            else None
                        ),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("Échec d'écriture du quota : %s", e)
