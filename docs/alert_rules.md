# Week 8 – Alert Rules Definition


**Based on:** Week 7 parser output (validated float readings + validity flags)

## 1. Review of Week 7 Parser Output

The Week 7 parser produces the following for each OCR reading:

| Field     | Description                                      | Example values                          |
|-----------|--------------------------------------------------|-----------------------------------------|
| Raw       | Original OCR string                              | `'38'`, `'12,50'`, `'9O'`, `'None'`    |
| Cleaned   | Normalised string after OCR correction           | `'38'`, `'12.50'`, `'90'`, `''`        |
| Value     | Parsed float (or `None` if invalid)              | `38.0`, `12.5`, `-8.0`, `None`         |
| Valid     | Boolean indicating successful parse + range check| `True` / `False`                       |
| Reason    | Explanation when `Valid == False`                | `"Empty string"`, `"Multiple decimal points"`, `"Value ... outside expected range [-1000.0, 1000.0]"` |

**Key observations from sample output:**
- Valid readings are floats in the range **[-1000.0, 1000.0]**.
- Invalid cases include: empty string, `None` input, multiple decimal points, values outside the ±1000 range.
- Negative values are accepted by the parser (e.g. `-8.0`).
- Comma-to-dot conversion and simple OCR character fixes (e.g. `O` → `0`) are already handled upstream.

The alert system **only receives the validated `Value` (float or `None`) and the `Valid` flag**. It does not re-parse raw OCR strings.

## 2. Packing Weight Limits (Configurable)

Default product target (example from brief): **1.000 kg**

| Parameter          | Default value | Description                                      | Notes |
|--------------------|---------------|--------------------------------------------------|-------|
| `target_weight`    | `1.000`       | Nominal / expected packed weight (kg)            | Product-specific |
| `min_weight`       | `0.980`       | Lower acceptance limit (kg)                      | = target − 0.020 |
| `max_weight`       | `1.020`       | Upper acceptance limit (kg)                      | = target + 0.020 |
| `tolerance`        | `0.020`       | Absolute tolerance used to derive min/max        | Can be absolute or percentage |

**Rules:**
- A reading is **NORMAL** when `min_weight ≤ value ≤ max_weight`.
- A reading is **UNDERWEIGHT** when `value < min_weight`.
- A reading is **OVERWEIGHT** when `value > max_weight`.
- Limits **must be configurable** (constructor / config file / environment). Hard-coding is forbidden.
- Units are kilograms (kg). All comparisons use the same unit.

**Examples (with defaults):**
- `1.005` → NORMAL  
- `1.035` → OVERWEIGHT  
- `0.950` → UNDERWEIGHT  

## 3. Scale Stability Definition

A reading is considered **stable** when successive weight values stay within a small variation window for a minimum duration.

| Parameter               | Default value | Description |
|-------------------------|---------------|-------------|
| `stability_tolerance`   | `0.005` kg    | Maximum allowed peak-to-peak variation between consecutive readings to be considered “stable” |
| `stability_timeout`     | `2.0` seconds | Maximum time the scale may remain unstable before an UNSTABLE alert is raised |
| `min_stable_duration`   | `0.5` seconds | Minimum time the reading must stay within tolerance before it is declared stable (optional hysteresis) |

**Stability rules:**
1. Maintain a short sliding window (or last N readings + timestamps).
2. Calculate the range (max − min) of the recent readings.
3. If `range ≤ stability_tolerance` **and** the window has been stable for ≥ `min_stable_duration` → state = **STABLE**.
4. If the reading keeps varying by more than `stability_tolerance` for longer than `stability_timeout` → raise **UNSTABLE**.
5. Stability is evaluated only on **valid** numeric readings. Invalid readings break the stability window.

**Example:**  
Readings oscillating between 0.992 kg and 1.015 kg for > 2 seconds → UNSTABLE.

## 4. Alert States

The system uses exactly four mutually exclusive states:

| State         | Meaning                                                                 | Trigger condition |
|---------------|-------------------------------------------------------------------------|-------------------|
| `NORMAL`      | Weight is inside limits **and** the scale is stable                     | `min ≤ value ≤ max` **and** stable |
| `UNDERWEIGHT` | Weight is below the minimum limit                                       | `value < min_weight` (valid reading) |
| `OVERWEIGHT`  | Weight is above the maximum limit                                       | `value > max_weight` (valid reading) |
| `UNSTABLE`    | Scale has been oscillating beyond tolerance longer than allowed         | Unstable duration > `stability_timeout` |

**Priority / combination rules:**
- Weight-limit checks (UNDERWEIGHT / OVERWEIGHT) take precedence over stability when a clear out-of-range value is present.
- If a reading is valid but the scale has been unstable for too long → **UNSTABLE** (even if the last value happens to be inside limits).
- Only one primary state is reported per evaluation cycle.

## 5. Handling of Invalid / Missing OCR Readings

| Situation                         | Parser output          | Alert system behaviour |
|-----------------------------------|------------------------|------------------------|
| Empty string / whitespace         | `Value=None`, `Valid=False` | Treat as **invalid**. Do **not** update weight or stability window. Optionally log “NO_READING”. |
| Literal `"None"` or `None` object | `Value=None`, `Valid=False` | Same as above. |
| Multiple decimal points / parse failure | `Value=None`, `Valid=False` | Same as above. |
| Value outside parser’s ±1000 range | `Value=None`, `Valid=False` | Same as above (parser already rejected it). |
| Negative weight (valid float)     | e.g. `-8.0`, `Valid=True`  | Accept the numeric value. It will almost always fall into **UNDERWEIGHT** (or be flagged by business rules if negative weights are physically impossible). |

**Design decisions:**
- Invalid readings **never** produce UNDERWEIGHT / OVERWEIGHT / UNSTABLE alerts by themselves.
- An invalid reading **resets** (or freezes) the stability tracking window so that a burst of OCR failures does not falsely trigger UNSTABLE.
- The alert engine should expose a secondary status / reason such as `"INVALID_READING"` or `"NO_DATA"` for logging and monitoring, but the primary alert state remains one of the four defined states (or a quiet “no-alert” when the previous state was NORMAL).
- Continuous invalid readings should **not** spam alerts; the same “no-duplicate” rule applied to continuous abnormal events also applies here.

## 6. Alert Generation Rules (High-level)

1. Every new validated reading is evaluated against the current limits **and** the stability detector.
2. An alert is emitted **only** when the state **changes** into an abnormal condition (UNDERWEIGHT, OVERWEIGHT or UNSTABLE).
3. While the same abnormal condition persists, **no additional alerts** are generated (debounce / edge-triggered).
4. When the reading returns to NORMAL (inside limits **and** stable), the system recovers and is ready to raise a new alert on the next transition.
5. Every alert record contains at minimum:
   - Timestamp (ISO-8601 or monotonic)
   - Weight value (or `None`)
   - Alert type / state
   - Human-readable reason
   - Optional processing latency (for real-time verification)

## 7. Configuration Summary (defaults used for implementation)

```python
DEFAULT_CONFIG = {
    "target_weight": 1.000,          # kg
    "min_weight": 0.980,             # kg
    "max_weight": 1.020,             # kg
    "stability_tolerance": 0.005,    # kg
    "stability_timeout": 2.0,        # seconds
    "min_stable_duration": 0.5,      # seconds
}
```

All values above are overridable at construction time or via a config file.

## 8. Acceptance Mapping

| Requirement                                      | Covered by section |
|--------------------------------------------------|--------------------|
| Accept validated readings from Week 7            | 1, 5             |
| Detect under/over weight with configurable limits| 2, 4             |
| Detect prolonged instability                     | 3, 4             |
| Clear alert with timestamp, weight, reason       | 6                 |
| No repeated alerts for continuous events         | 6                 |
| Correct recovery to NORMAL                       | 6                 |

---
