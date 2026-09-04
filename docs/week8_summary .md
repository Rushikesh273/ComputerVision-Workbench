# Week 8 Summary — Zero-Latency Trigger Logics

## What This Is

An alert system that watches weight readings and flags problems in real time — over/under-weight packages, and a scale that won't settle. It sits right after the OCR parsing stage: it takes the already-parsed weight value (a float, or `None` if that reading couldn't be trusted) and decides what to do about it.

## Pipeline

```
Parsed weight value -> weight_validator.validate_weight()
                     -> stability_detector.StabilityDetector.update()
                     -> alert_engine.AlertEngine.process()
                     -> AlertDecision (state, alert_triggered, recovered, reason, processing_time_ms)
```

Three modules, each with a clearly bounded job:

- **`weight_validator.py`** — stateless. One reading in, one status out (`NORMAL` / `UNDERWEIGHT` / `OVERWEIGHT` / `INVALID_READING`). Configurable `WeightLimits` (min/max/target), never hard-coded.
- **`stability_detector.py`** — stateful. One `StabilityDetector` instance per scale, called once per new reading via `.update()`. Tracks a rolling time-window of recent readings to judge `STABLE` / `UNSTABLE` / `MONITORING` (still settling, not yet confirmed either way).
- **`alert_engine.py`** — combines both into one final decision per reading via `AlertEngine.process()`. Applies the priority rule (weight-limit violations take precedence over stability), suppresses duplicate alerts for a continuous event, and detects recovery back to `NORMAL`.

## How a Sequence Is Actually Processed

Neither `StabilityDetector` nor `AlertEngine` takes a list of readings. You create **one instance** (per scale/session) and call `.update()` / `.process()` **once per new reading, as it arrives** — a live camera frame in production, or one loop iteration in a test/simulation. Each instance remembers what it needs internally between calls; the caller's only job is to keep feeding it one reading at a time, in order.

## Testing Summary

`tests/test_alert_engine.py` — 23 tests, all passing:

- Individual reading types: normal (including both exact boundary values), underweight, overweight, invalid
- A genuine simulated **stream** of readings (not just individual values) — a full realistic story asserts state/alert/recovery at every step of a multi-reading sequence
- Alerts firing when conditions are actually met, and **not** firing on normal readings
- Duplicate-alert suppression for continuous `OVERWEIGHT`, `UNDERWEIGHT`, and `UNSTABLE` conditions — each fires exactly once, not once per frame
- Recovery to `NORMAL` firing exactly once on the transition, and allowing a genuinely new alert on a later re-occurrence of the same condition
- An invalid reading mid-event **not** resetting an ongoing overweight/underweight alert (so a brief OCR gap doesn't cause a false re-alert)
- Processing time confirmed well under real-time budgets (sub-millisecond per decision in practice)

## Real, Documented Behavior Worth Knowing About (Not a Bug)

If an invalid reading interrupts an active `UNSTABLE` event, the very next single valid, in-range reading is enough for the system to report `NORMAL`/`recovered`, without requiring the usual settling time to re-confirm stability first. This happens because the invalid reading fully resets the stability tracker's history — the next reading has no prior evidence to judge against, so it's treated as freshly settling rather than freshly re-confirming.

This is locked in as a dedicated regression test — so if it ever silently changes, the test fails loudly instead of the behavior drifting unnoticed. Whether this is the *desired* behavior long-term is a product decision, not a code question — the system currently implements the literal wording of the existing rule that invalid readings "break the stability window."

## Real-Time Suitability

Every alert decision measures its own processing time. Across all tested scenarios, processing consistently completed in well under a millisecond — comfortably fast enough for real-time operation at any realistic camera/OCR frame rate. The bottleneck in a real deployment will be the camera → OCR → parsing stages upstream, not this alert layer.

## Design Principle

> A wrong "corrected" or silently-suppressed result is more dangerous than an admitted uncertainty, because it looks just as confident as a right one.

Reflected here in: invalid readings never manufacture a fake alert state, weight-limit violations always take priority over a stability judgment (a clearly out-of-range value is reported as such immediately, regardless of how "stable" it looks), and every decision — valid or not — always returns a complete, honest record rather than silently doing nothing.
