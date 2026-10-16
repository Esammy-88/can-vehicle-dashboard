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
        zero_below: float | None = None,
    ) -> None:
        self._source = source
        self._noise_std = noise_std
        self._rng = rng or random.Random(0)
        self._min = minimum
        self._max = maximum
        # Pulse-counting sensors (wheel speed, crank) read exactly zero when
        # nothing turns: there are no pulses for noise to ride on.
        self._zero_below = zero_below
        # Set by fault injection: the sensor reads this instead of the real value.
        self.fault_value: float | None = None

    def read(self) -> float:
        if self.fault_value is not None:
            return self.fault_value
        value = self._source()
        if self._zero_below is not None and abs(value) < self._zero_below:
            return 0.0
        if self._noise_std:
            value += self._rng.gauss(0.0, self._noise_std)
        if self._min is not None:
            value = max(self._min, value)
        if self._max is not None:
            value = min(self._max, value)
        return value
