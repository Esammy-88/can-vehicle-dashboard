"""Sensor models between the physical plant and the ECUs.

ECUs never read plant state directly; they read a sensor, which adds a small
amount of Gaussian noise the way a real ADC reading would. A seeded RNG keeps
simulations reproducible.
"""

from __future__ import annotations

import random
from collections.abc import Callable


class Sensor:
    def __init__(
        self,
        source: Callable[[], float],
        noise_std: float = 0.0,
        rng: random.Random | None = None,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> None:
        self._source = source
        self._noise_std = noise_std
        self._rng = rng or random.Random(0)
        self._min = minimum
        self._max = maximum

    def read(self) -> float:
        value = self._source()
        if self._noise_std:
            value += self._rng.gauss(0.0, self._noise_std)
        if self._min is not None:
            value = max(self._min, value)
        if self._max is not None:
            value = min(self._max, value)
        return value
