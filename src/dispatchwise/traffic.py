"""Hour-of-day traffic multipliers."""

from __future__ import annotations

from typing import Dict, Optional

# Defaults loosely shaped like a Gulf city weekday: quiet nights, a morning
# school/commute peak and a heavier evening peak.
DEFAULT_PROFILE: Dict[int, float] = {
    0: 0.8, 1: 0.8, 2: 0.8, 3: 0.8, 4: 0.8, 5: 0.9,
    6: 1.1, 7: 1.5, 8: 1.6, 9: 1.3, 10: 1.0, 11: 1.0,
    12: 1.1, 13: 1.2, 14: 1.1, 15: 1.1, 16: 1.3, 17: 1.7,
    18: 1.8, 19: 1.6, 20: 1.3, 21: 1.1, 22: 1.0, 23: 0.9,
}  # fmt: skip


class TrafficProfile:
    """Maps an hour (0-23) to a travel-time multiplier (1.0 = free flow)."""

    def __init__(self, multipliers: Optional[Dict[int, float]] = None) -> None:
        profile = dict(DEFAULT_PROFILE)
        if multipliers:
            profile.update(multipliers)
        for hour, value in profile.items():
            if not 0 <= hour <= 23:
                raise ValueError(f"hour must be in 0..23, got {hour}")
            if value <= 0:
                raise ValueError(f"multiplier must be positive, got {value} at hour {hour}")
        self._profile = profile

    def multiplier(self, hour: int) -> float:
        return self._profile[hour % 24]

    def as_dict(self) -> Dict[int, float]:
        return dict(self._profile)
