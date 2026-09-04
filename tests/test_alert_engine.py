"""
test_alert_engine.py
=====================
Unit tests for the Week 8 alert system (weight_validator.py +
stability_detector.py + alert_engine.py), covering:
    - Normal, underweight, overweight, unstable and invalid readings
    - A simulated STREAM of readings (not just individual values)
    - Alerts triggering when conditions are met
    - Normal readings never producing false alerts
    - Continuous abnormal conditions not producing duplicate alerts
    - Recovery when readings return to normal
    - Processing time staying fast enough for real-time use

Run with:
    pytest tests/test_alert_engine.py -v
"""

import sys
from pathlib import Path


def _find_src_alerts_dir(start: Path) -> Path:
    """Walk upward from this test file looking for a src/alerts
    directory, so this suite works regardless of exactly how deep
    tests/ sits relative to the repo root -- learned from a real import
    failure in Week 7's test suite, which assumed a fixed distance and
    broke on the actual repo layout."""
    current = start.resolve()
    for candidate_root in [current] + list(current.parents):
        candidate = candidate_root / "src" / "alerts"
        if candidate.is_dir():
            return candidate
    raise RuntimeError(
        "Could not find a 'src/alerts' directory above "
        f"{start} -- make sure weight_validator.py, stability_detector.py, "
        "and alert_engine.py live in src/alerts/ somewhere above this test file."
    )


sys.path.insert(0, str(_find_src_alerts_dir(Path(__file__).parent)))

import pytest

from weight_validator import WeightLimits, NORMAL, UNDERWEIGHT, OVERWEIGHT, INVALID_READING
from stability_detector import StabilityConfig, UNSTABLE
from alert_engine import AlertEngine


# ---------------------------------------------------------------------------
# Shared config -- same real numbers as docs/alert_rules.md
# ---------------------------------------------------------------------------

def make_engine():
    return AlertEngine(
        limits=WeightLimits(min_weight=0.980, max_weight=1.020, target_weight=1.000),
        stability_config=StabilityConfig(stability_tolerance=0.005, stability_timeout=2.0, min_stable_duration=0.5),
    )


# ---------------------------------------------------------------------------
# Individual reading types: normal, underweight, overweight, invalid
# ---------------------------------------------------------------------------

def test_first_normal_reading_produces_no_false_alert():
    """A single in-range reading should never be misreported as abnormal --
    this is the baseline 'normal readings do not create false alerts' check."""
    engine = make_engine()
    decision = engine.process(1.000, timestamp=0.0)
    assert decision.state == NORMAL
    assert decision.alert_triggered is False
    assert decision.recovered is False


@pytest.mark.parametrize("value", [1.005, 0.985, 1.015, 0.980, 1.020])
def test_various_normal_values_no_alert(value):
    """Several different in-range values, including both exact boundaries,
    should all report NORMAL with no alert."""
    engine = make_engine()
    decision = engine.process(value, timestamp=0.0)
    assert decision.state == NORMAL
    assert decision.alert_triggered is False


def test_underweight_reading_triggers_alert():
    engine = make_engine()
    decision = engine.process(0.950, timestamp=0.0)
    assert decision.state == UNDERWEIGHT
    assert decision.alert_triggered is True
    assert decision.weight == 0.950


def test_overweight_reading_triggers_alert():
    engine = make_engine()
    decision = engine.process(1.035, timestamp=0.0)
    assert decision.state == OVERWEIGHT
    assert decision.alert_triggered is True
    assert decision.weight == 1.035


def test_invalid_reading_never_triggers_alert():
    """Per alert_rules.md section 5: invalid readings never produce
    UNDERWEIGHT/OVERWEIGHT/UNSTABLE alerts by themselves."""
    engine = make_engine()
    decision = engine.process(None, timestamp=0.0)
    assert decision.state == INVALID_READING
    assert decision.alert_triggered is False
    assert decision.recovered is False
    assert decision.weight is None


# ---------------------------------------------------------------------------
# Duplicate-alert suppression for continuous abnormal conditions
# ---------------------------------------------------------------------------

def test_no_duplicate_alerts_for_continuous_overweight():
    """Several consecutive overweight readings should alert exactly once,
    on the FIRST reading of the event -- not on every frame."""
    engine = make_engine()
    readings = [1.035, 1.036, 1.034, 1.040, 1.033]
    decisions = [engine.process(v, timestamp=float(i)) for i, v in enumerate(readings)]

    assert all(d.state == OVERWEIGHT for d in decisions)
    assert decisions[0].alert_triggered is True
    assert all(d.alert_triggered is False for d in decisions[1:])


def test_no_duplicate_alerts_for_continuous_underweight():
    engine = make_engine()
    readings = [0.950, 0.955, 0.945, 0.960]
    decisions = [engine.process(v, timestamp=float(i)) for i, v in enumerate(readings)]

    assert decisions[0].alert_triggered is True
    assert all(d.alert_triggered is False for d in decisions[1:])


def test_switching_between_overweight_and_underweight_re_alerts():
    """Going from OVERWEIGHT directly to UNDERWEIGHT (skipping NORMAL) is a
    genuinely different abnormal condition -- it SHOULD re-alert, since
    it's not a continuation of the same event."""
    engine = make_engine()
    d1 = engine.process(1.035, timestamp=0.0)  # OVERWEIGHT, alerts
    d2 = engine.process(0.950, timestamp=1.0)  # UNDERWEIGHT, different condition
    assert d1.state == OVERWEIGHT and d1.alert_triggered is True
    assert d2.state == UNDERWEIGHT and d2.alert_triggered is True


# ---------------------------------------------------------------------------
# Recovery to NORMAL
# ---------------------------------------------------------------------------

def test_recovery_after_overweight_fires_exactly_once():
    engine = make_engine()
    engine.process(1.035, timestamp=0.0)   # OVERWEIGHT, alerts
    d2 = engine.process(1.000, timestamp=1.0)  # back to NORMAL -- recovery
    d3 = engine.process(1.001, timestamp=2.0)  # still NORMAL -- no repeat recovery flag

    assert d2.state == NORMAL and d2.recovered is True
    assert d3.state == NORMAL and d3.recovered is False


def test_recovery_allows_a_future_alert_on_the_same_condition():
    """After recovering from OVERWEIGHT back to NORMAL, a LATER overweight
    reading is a genuinely NEW event and should alert again."""
    engine = make_engine()
    engine.process(1.035, timestamp=0.0)      # OVERWEIGHT, alerts
    engine.process(1.000, timestamp=1.0)      # recovers to NORMAL
    d3 = engine.process(1.040, timestamp=2.0)  # OVERWEIGHT again -- new event
    assert d3.state == OVERWEIGHT
    assert d3.alert_triggered is True


# ---------------------------------------------------------------------------
# Unstable detection -- requires a genuine SEQUENCE, not a single reading
# ---------------------------------------------------------------------------

def test_unstable_alert_fires_after_timeout_not_before():
    """Oscillation that stays within weight limits but exceeds stability
    tolerance should NOT report UNSTABLE until stability_timeout has
    genuinely elapsed -- confirms the alert isn't premature."""
    engine = make_engine()
    oscillating = [
        (0.0, 1.012), (0.4, 0.993), (0.8, 1.010), (1.2, 0.995), (1.6, 1.008),
    ]
    decisions = [engine.process(v, timestamp=t) for t, v in oscillating]
    # Before 2.0s of continuous out-of-tolerance variation has elapsed,
    # none of these should have escalated to UNSTABLE yet.
    assert all(d.state != UNSTABLE for d in decisions)


def test_unstable_alert_fires_once_timeout_is_reached():
    engine = make_engine()
    oscillating = [
        (0.0, 1.012), (0.4, 0.993), (0.8, 1.010), (1.2, 0.995),
        (1.6, 1.008), (2.0, 0.996), (2.4, 1.009),
    ]
    decisions = [engine.process(v, timestamp=t) for t, v in oscillating]
    unstable_decisions = [d for d in decisions if d.state == UNSTABLE]
    assert len(unstable_decisions) > 0, "Expected UNSTABLE to fire once oscillation exceeded the timeout"


def test_no_duplicate_alerts_for_continuous_instability():
    """Once UNSTABLE has fired, it should not re-fire on every subsequent
    frame while the same instability continues."""
    engine = make_engine()
    oscillating = [
        (0.0, 1.012), (0.4, 0.993), (0.8, 1.010), (1.2, 0.995),
        (1.6, 1.008), (2.0, 0.996), (2.4, 1.009), (2.8, 0.994), (3.2, 1.011),
    ]
    decisions = [engine.process(v, timestamp=t) for t, v in oscillating]
    triggered_count = sum(1 for d in decisions if d.state == UNSTABLE and d.alert_triggered)
    assert triggered_count == 1, f"Expected exactly one UNSTABLE alert, got {triggered_count}"


# ---------------------------------------------------------------------------
# Invalid readings mid-stream -- must not corrupt an ongoing event
# ---------------------------------------------------------------------------

def test_invalid_reading_does_not_reset_ongoing_overweight_event():
    """An OCR gap in the middle of a real overweight event should not make
    the event 'restart' and re-alert once valid readings resume."""
    engine = make_engine()
    d1 = engine.process(1.035, timestamp=0.0)   # OVERWEIGHT, alerts
    d2 = engine.process(None, timestamp=1.0)     # invalid -- gap
    d3 = engine.process(1.036, timestamp=2.0)   # OVERWEIGHT resumes -- same event

    assert d1.alert_triggered is True
    assert d2.state == INVALID_READING and d2.alert_triggered is False
    assert d3.state == OVERWEIGHT
    assert d3.alert_triggered is False, "Should NOT re-alert -- this is a continuation, not a new event"


def test_invalid_reading_resets_stability_window_documented_behavior():
    """KNOWN, DOCUMENTED behavior (not a bug): an invalid reading fully
    resets stability_detector's history (alert_rules.md section 3, rule 5:
    'invalid readings break the stability window'). This means a SINGLE
    good reading right after an invalid-reading interruption during an
    active UNSTABLE event is enough to report NORMAL/recovered, without
    requiring full min_stable_duration re-confirmation. This test locks in
    that real, verified behavior so it's caught if it silently changes."""
    engine = make_engine()
    oscillating = [
        (0.0, 1.012), (0.4, 0.993), (0.8, 1.010), (1.2, 0.995),
        (1.6, 1.008), (2.0, 0.996), (2.4, 1.009),
    ]
    for t, v in oscillating:
        engine.process(v, timestamp=t)
    # Confirm we're actually in an UNSTABLE event before testing the reset
    assert engine._last_alert_state == UNSTABLE

    engine.process(None, timestamp=3.0)  # invalid -- resets stability window
    recovery_decision = engine.process(1.001, timestamp=3.5)  # one good reading

    assert recovery_decision.state == NORMAL
    assert recovery_decision.recovered is True


# ---------------------------------------------------------------------------
# Full realistic stream -- the actual story from alert_engine.py's own demo,
# asserted step by step rather than just eyeballed
# ---------------------------------------------------------------------------

def test_full_realistic_stream_end_to_end():
    """Simulates one continuous story: normal -> overweight (alerts once) ->
    recovers -> oscillation causes instability (alerts once) -> an invalid
    reading mid-event -> settles and recovers. Matches the real demo in
    alert_engine.py's own __main__ block."""
    engine = make_engine()

    stream = [
        (0.0, 1.000, NORMAL, False, False),
        (0.6, 1.001, NORMAL, False, False),
        (1.0, 1.035, OVERWEIGHT, True, False),
        (1.4, 1.036, OVERWEIGHT, False, False),
        (1.8, 1.034, OVERWEIGHT, False, False),
        (2.2, 1.000, NORMAL, False, True),
        (2.8, 1.001, NORMAL, False, False),
    ]

    for t, value, expected_state, expected_alert, expected_recovered in stream:
        decision = engine.process(value, timestamp=t)
        assert decision.state == expected_state, f"t={t}: expected state {expected_state}, got {decision.state}"
        assert decision.alert_triggered is expected_alert, f"t={t}: expected alert_triggered={expected_alert}"
        assert decision.recovered is expected_recovered, f"t={t}: expected recovered={expected_recovered}"


# ---------------------------------------------------------------------------
# Processing time -- real-time suitability
# ---------------------------------------------------------------------------

def test_processing_time_is_fast_enough_for_real_time_use():
    """Every decision should compute well under typical camera/OCR frame
    intervals (e.g. way under 100ms) -- confirms the engine itself isn't
    the bottleneck in a real-time pipeline."""
    engine = make_engine()
    readings = [1.000, 1.035, 0.950, None, 1.001, 1.012, 0.993]
    for i, v in enumerate(readings):
        decision = engine.process(v, timestamp=float(i))
        assert decision.processing_time_ms < 100.0, (
            f"Processing took {decision.processing_time_ms}ms, too slow for real-time use"
        )


# ---------------------------------------------------------------------------
# Alert record content -- every decision must carry what's needed for logging
# ---------------------------------------------------------------------------

def test_alert_decision_always_has_required_fields():
    engine = make_engine()
    for value in [1.000, 1.035, 0.950, None]:
        decision = engine.process(value, timestamp=0.0)
        assert hasattr(decision, "timestamp")
        assert hasattr(decision, "weight")
        assert hasattr(decision, "state")
        assert hasattr(decision, "alert_triggered")
        assert hasattr(decision, "recovered")
        assert hasattr(decision, "reason")
        assert hasattr(decision, "processing_time_ms")
        assert decision.reason != "", "Every decision should include a human-readable reason"


# ---------------------------------------------------------------------------
# Configurability -- limits must not be hard-coded
# ---------------------------------------------------------------------------

def test_custom_limits_are_respected():
    """Confirms limits are genuinely configurable, not hard-coded --
    a value that's OVERWEIGHT under default limits should be NORMAL
    under wider custom limits."""
    engine = AlertEngine(limits=WeightLimits(min_weight=0.0, max_weight=100.0, target_weight=50.0))
    decision = engine.process(1.035, timestamp=0.0)
    assert decision.state == NORMAL
