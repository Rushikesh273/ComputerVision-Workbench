"""
alert_engine.py
================
Combines weight_validator.py  + stability_detector.py 
into a single real-time alert decision per reading.

Like StabilityDetector, this needs MEMORY across calls -- one AlertEngine
instance per scale/session, created once and called repeatedly via
.process(), one reading at a time (same usage pattern as
StabilityDetector.update() -- see that module's docstring).

Priority and duplicate-suppression rules, per docs/alert_rules.md:
    - Weight-limit checks (UNDERWEIGHT/OVERWEIGHT) take precedence over
      stability when a clear out-of-range value is present (section 4).
    - UNSTABLE only fires once stability_detector.py has actually
      confirmed it (not during the settling/MONITORING grace period) --
      section 4: "unstable for TOO LONG", not "currently varying."
    - An alert is only emitted on the FIRST reading of a NEW abnormal
      event -- while the same condition persists, no repeat alerts
      (section 6, rules 2-3).
    - Invalid readings never trigger an alert by themselves, and do NOT
      clear an in-progress abnormal event -- a brief OCR gap in the
      middle of a real overweight event should not make the event
      "restart" and re-alert once valid readings resume (section 5).
"""

import time
from dataclasses import dataclass
from typing import Optional

from weight_validator import validate_weight, WeightLimits, NORMAL, UNDERWEIGHT, OVERWEIGHT, INVALID_READING
from stability_detector import StabilityDetector, StabilityConfig, STABLE, UNSTABLE, MONITORING


@dataclass
class AlertDecision:
    timestamp: float
    weight: Optional[float]
    state: str              # NORMAL / UNDERWEIGHT / OVERWEIGHT / UNSTABLE / INVALID_READING
    alert_triggered: bool   # True ONLY on the first reading of a new abnormal event
    recovered: bool         # True ONLY on the first reading back to NORMAL after an abnormal event
    reason: str
    processing_time_ms: float


class AlertEngine:
    """
    One instance per scale/session. Combines weight limit validation and
    stability detection into a single alert decision per reading, with
    duplicate-alert suppression across a continuous abnormal event.

    Usage:
        engine = AlertEngine(limits=WeightLimits(), stability_config=StabilityConfig())
        for value, timestamp in incoming_readings:
            decision = engine.process(value, timestamp)
    """

    def __init__(self, limits: Optional[WeightLimits] = None,
                 stability_config: Optional[StabilityConfig] = None):
        self.limits = limits or WeightLimits()
        self.stability = StabilityDetector(stability_config)
        # The state an alert was last actually raised for -- None means
        # "no ongoing abnormal event" (never started, or already
        # recovered). Deliberately NOT cleared on an invalid reading --
        # see module docstring / alert_rules.md section 5.
        self._last_alert_state: Optional[str] = None

    def process(self, value: Optional[float], timestamp: Optional[float] = None) -> AlertDecision:
        """
        Evaluate ONE new reading and return the current alert decision.
        Call once per reading, in order, as they arrive.
        """
        start = time.perf_counter()
        now = timestamp if timestamp is not None else time.monotonic()

        weight_result = validate_weight(value, self.limits)
        # Stability tracking still needs to see every reading (including
        # None, which it uses to reset its own window) -- always call it.
        stability_result = self.stability.update(value, now)

        if weight_result.status == INVALID_READING:
            # Never alerts by itself, never clears an in-progress event.
            return AlertDecision(
                timestamp=now, weight=None, state=INVALID_READING,
                alert_triggered=False, recovered=False,
                reason=weight_result.reason,
                processing_time_ms=(time.perf_counter() - start) * 1000,
            )

        # Weight-limit checks take precedence over stability.
        if weight_result.status in (UNDERWEIGHT, OVERWEIGHT):
            final_state = weight_result.status
            reason = weight_result.reason
        elif stability_result.state == UNSTABLE:
            final_state = UNSTABLE
            reason = stability_result.reason
        else:
            # Weight is within limits, and stability is either STABLE or
            # still MONITORING (settling -- not yet confirmed either way,
            # not alert-worthy on its own).
            final_state = NORMAL
            reason = weight_result.reason

        is_new_abnormal_event = (
            final_state in (UNDERWEIGHT, OVERWEIGHT, UNSTABLE)
            and final_state != self._last_alert_state
        )
        is_recovery = final_state == NORMAL and self._last_alert_state is not None

        if is_new_abnormal_event:
            self._last_alert_state = final_state
        elif final_state == NORMAL:
            self._last_alert_state = None

        return AlertDecision(
            timestamp=now, weight=weight_result.value, state=final_state,
            alert_triggered=is_new_abnormal_event, recovered=is_recovery,
            reason=reason,
            processing_time_ms=(time.perf_counter() - start) * 1000,
        )


if __name__ == "__main__":
    # Demonstrates the full pipeline against a simulated stream, one
    # reading at a time -- same pattern as stability_detector.py's demo.
    # Story: normal -> overweight persists (alert once) -> recovers
    # (recovered once) -> a bump causing instability past timeout (alert
    # once) -> an invalid reading mid-event (should NOT reset it, no
    # alert) -> recovers to normal.
    engine = AlertEngine(
        limits=WeightLimits(min_weight=0.980, max_weight=1.020, target_weight=1.000),
        stability_config=StabilityConfig(stability_tolerance=0.005, stability_timeout=2.0, min_stable_duration=0.5),
    )

    simulated_readings = [
        (0.0, 1.000), (0.6, 1.001),                              # NORMAL, settled
        (1.0, 1.035), (1.4, 1.036), (1.8, 1.034),                # OVERWEIGHT starts, persists
        (2.2, 1.000), (2.8, 1.001),                              # recovers to NORMAL
        # Oscillation stays WITHIN weight limits [0.980, 1.020] but well
        # beyond stability_tolerance (0.005) -- this is what actually
        # exercises the UNSTABLE path, rather than every reading just
        # tripping OVERWEIGHT/UNDERWEIGHT on its own.
        (3.2, 1.012), (3.6, 0.993), (4.0, 1.010), (4.4, 0.995),
        (4.8, 1.008), (5.2, 0.996),                              # still oscillating -> UNSTABLE by ~5.2s
        (5.6, None),                                             # OCR failure mid-event -- should NOT reset/re-alert
        (6.0, 1.009),                                            # still unstable-range once resumed
        (6.5, 1.001), (6.9, 1.000), (7.3, 1.002), (7.7, 1.001),  # settles -> recovers to NORMAL
    ]

    print(f"{'t (s)':<8} {'value':<8} {'state':<16} {'alert?':<8} {'recov?':<8} {'ms':<8} reason")
    print("-" * 110)
    for t, v in simulated_readings:
        d = engine.process(v, timestamp=t)
        print(f"{t:<8} {str(v):<8} {d.state:<16} {str(d.alert_triggered):<8} "
              f"{str(d.recovered):<8} {d.processing_time_ms:<8.3f} {d.reason}")
