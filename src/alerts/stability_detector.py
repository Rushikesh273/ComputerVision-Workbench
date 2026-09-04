"""
stability_detector.py
======================
Tracks a SEQUENCE of weight readings over time and determines whether the
scale is STABLE, UNSTABLE, or still settling (not yet confirmed either way).

HOW A "SEQUENCE" IS PROCESSED: this module does NOT take a list of
readings all at once. Instead, you create ONE StabilityDetector instance
(per scale/session) and call .update() once per new reading, as it
arrives -- in a live system that's once per camera frame / OCR cycle; in
a test or simulation, it's once per loop iteration over your simulated
data. The detector remembers everything it needs internally between
calls -- the caller just keeps feeding it one reading at a time:

    detector = StabilityDetector()
    for value, timestamp in incoming_readings:
        result = detector.update(value, timestamp)
        # result.state tells you STABLE / UNSTABLE / MONITORING right now

This is fundamentally different from weight_validator.py (Tuesday), which
is a stateless pure function -- one reading in, one status out, no memory.
StabilityDetector must have memory, because "is this stable" is a
question about a WINDOW of readings, not any single one.

Design per docs/alert_rules.md section 3:
    - stability_tolerance: max allowed peak-to-peak variation (max-min)
      within the recent window to be considered "stable"
    - stability_timeout: how long the reading may keep varying beyond
      tolerance before an UNSTABLE alert is warranted
    - min_stable_duration: how long readings must stay within tolerance
      before being confirmed STABLE (avoids flagging STABLE off one
      lucky reading)

Per alert_rules.md section 3, rule 5: "Invalid readings break the
stability window." Implemented here as fully clearing tracked history on
an invalid (None) reading -- a burst of OCR failures doesn't extend an
unstable streak or falsely preserve a stable one; tracking simply starts
over once valid readings resume.
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Tuple

STABLE = "STABLE"
UNSTABLE = "UNSTABLE"
MONITORING = "MONITORING"  # not yet confirmed STABLE or UNSTABLE -- still
                            # within the grace period either way


@dataclass
class StabilityConfig:
    """Defaults per docs/alert_rules.md sections 3 and 7."""
    stability_tolerance: float = 0.005   # kg
    stability_timeout: float = 2.0       # seconds
    min_stable_duration: float = 0.5     # seconds

    def __post_init__(self):
        if self.min_stable_duration > self.stability_timeout:
            raise ValueError(
                f"min_stable_duration ({self.min_stable_duration}) should not "
                f"exceed stability_timeout ({self.stability_timeout})"
            )


@dataclass
class StabilityResult:
    state: str                       # STABLE / UNSTABLE / MONITORING
    range_value: Optional[float]     # max-min of the current window (None if reset by an invalid reading)
    duration_in_state: float         # how long the current streak (stable or unstable) has lasted, in seconds
    reason: str


class StabilityDetector:
    """
    One instance per scale/session -- holds the rolling history of recent
    readings needed to judge stability over time. Create it once, call
    .update() repeatedly as new readings arrive.
    """

    def __init__(self, config: Optional[StabilityConfig] = None):
        self.config = config or StabilityConfig()
        self._history: Deque[Tuple[float, float]] = deque()  # (timestamp, value)
        # Tracks the CURRENT classification ("in_tolerance" / "out_of_tolerance")
        # and exactly when it started -- set only on an actual transition, not
        # re-derived from whatever happens to still be sitting in the window.
        # (An earlier version anchored duration to the oldest window
        # timestamp, which silently included leftover data from the PREVIOUS
        # state across a transition and overstated how long the current
        # state had actually been true -- fixed here.)
        self._current_class: Optional[str] = None
        self._class_since: Optional[float] = None

    def reset(self):
        """Fully clears tracked history -- used on invalid readings (see
        module docstring) or to explicitly restart tracking (e.g. a new
        item placed on the scale)."""
        self._history.clear()
        self._current_class = None
        self._class_since = None

    def update(self, value: Optional[float], timestamp: Optional[float] = None) -> StabilityResult:
        """
        Feed ONE new reading into the tracker. Call this once per reading,
        in order, as they arrive -- see module docstring for the loop pattern.

        value: a plain float (a valid Week 7 reading), or None for an
               invalid/missing reading.
        timestamp: seconds, monotonically increasing (e.g. time.monotonic()).
                   Pass this explicitly for deterministic, fast tests
                   instead of real sleeps. Defaults to time.monotonic().
        """
        now = timestamp if timestamp is not None else time.monotonic()

        if value is None:
            self.reset()
            return StabilityResult(
                state=MONITORING, range_value=None, duration_in_state=0.0,
                reason="Invalid reading -- stability window reset",
            )

        self._history.append((now, value))

        # Keep only readings within the last stability_timeout seconds --
        # the longest lookback the RANGE calculation needs. This window is
        # only used to compute range_value (recent variability) -- it is
        # NOT used to anchor duration tracking (see _current_class/_class_since above).
        cutoff = now - self.config.stability_timeout
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()

        values = [v for _, v in self._history]
        range_value = max(values) - min(values)
        in_tolerance = range_value <= self.config.stability_tolerance
        new_class = "in_tolerance" if in_tolerance else "out_of_tolerance"

        # Only reset the "since" timestamp on an actual transition (or the
        # very first reading) -- if the classification hasn't changed,
        # duration keeps accumulating from when it FIRST became true.
        if new_class != self._current_class:
            self._current_class = new_class
            self._class_since = now

        duration = now - self._class_since

        if in_tolerance:
            if duration >= self.config.min_stable_duration:
                return StabilityResult(
                    state=STABLE, range_value=range_value, duration_in_state=duration,
                    reason=f"Range {range_value:.4f} kg within tolerance "
                           f"{self.config.stability_tolerance} kg for {duration:.2f}s",
                )
            return StabilityResult(
                state=MONITORING, range_value=range_value, duration_in_state=duration,
                reason=f"Within tolerance but only stable for {duration:.2f}s "
                       f"(needs {self.config.min_stable_duration}s)",
            )

        if duration >= self.config.stability_timeout:
            return StabilityResult(
                state=UNSTABLE, range_value=range_value, duration_in_state=duration,
                reason=f"Range {range_value:.4f} kg exceeds tolerance "
                       f"{self.config.stability_tolerance} kg for {duration:.2f}s "
                       f"(timeout {self.config.stability_timeout}s)",
            )
        return StabilityResult(
            state=MONITORING, range_value=range_value, duration_in_state=duration,
            reason=f"Out of tolerance for {duration:.2f}s "
                   f"(timeout at {self.config.stability_timeout}s)",
        )


if __name__ == "__main__":
    # Demonstrates exactly how a SEQUENCE is processed: one detector
    # instance, one .update() call per reading, in a loop -- using
    # injected timestamps (not real sleeps) so this runs instantly.
    config = StabilityConfig(stability_tolerance=0.005, stability_timeout=2.0, min_stable_duration=0.5)
    detector = StabilityDetector(config)

    # Simulated stream: (timestamp_seconds, value_or_None)
    # Story: settles quickly, then gets bumped and stays unstable past
    # timeout, then settles again.
    simulated_readings = [
        (0.0, 1.000), (0.2, 1.001), (0.4, 0.999), (0.6, 1.000),  # settles by ~0.6s
        (1.0, 1.050), (1.3, 0.960), (1.6, 1.040), (1.9, 0.970),  # bumped, oscillating
        (2.3, 1.030), (2.7, 0.965), (3.1, 1.045),                # still oscillating
        (3.3, 1.001), (3.5, 1.000), (3.7, 1.002), (3.9, 1.001),  # NATURAL recovery, no reset --
                                                                   # oscillation just stops on its own
        (4.5, None),                                              # OCR failure -- resets tracking
        (4.7, 1.001), (4.9, 1.000), (5.1, 1.002), (5.4, 1.001),  # settles again after reset
    ]

    print(f"{'t (s)':<8} {'value':<8} {'state':<12} {'range':<8} {'duration':<10} reason")
    print("-" * 90)
    for t, v in simulated_readings:
        result = detector.update(v, timestamp=t)
        range_str = f"{result.range_value:.4f}" if result.range_value is not None else "-"
        print(f"{t:<8} {str(v):<8} {result.state:<12} {range_str:<8} "
              f"{result.duration_in_state:<10.2f} {result.reason}")
