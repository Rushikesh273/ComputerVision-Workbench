"""
weight_validator.py
====================
Compares a validated weight reading (a float from Week 7's parser, or None
for an invalid/missing reading) against configurable minimum/maximum
packing limits, and returns a clear status for every reading.

This module does NOT know about stability or time -- it evaluates exactly
one reading at a time, with no memory of previous readings. Stability
(readings over time) is stability_detector.py's job ; combining
this with stability into the final NORMAL/UNDERWEIGHT/OVERWEIGHT/UNSTABLE
alert state is alert_engine.py's job .

Input contract: this module expects a plain float (or None), matching what
you get from Week 7's ParseResult.value when ParseResult.is_valid is True.
It does not import or depend on parser.py directly -- pass
`parse_result.value if parse_result.is_valid else None` when wiring this
up to the real Week 7 output.

Defaults match the decisions recorded in docs/alert_rules.md
(target 1.000 kg, allowed range 0.980 - 1.020 kg).
"""

from dataclasses import dataclass
from typing import Optional

# Status constants – plain strings to stay consistent with the simple
# string-based style used in the Week 7 parser modules.
# NOTE: "INVALID_READING" is local to this module. The four official
# system-wide alert states (NORMAL / UNDERWEIGHT / OVERWEIGHT / UNSTABLE)
# are decided by alert_engine.py according to the rules in
# docs/alert_rules.md sections 4 and 5.
NORMAL = "NORMAL"
UNDERWEIGHT = "UNDERWEIGHT"
OVERWEIGHT = "OVERWEIGHT"
INVALID_READING = "INVALID_READING"

# Defaults taken from docs/alert_rules.md sections 2 and 7
DEFAULT_TARGET_WEIGHT = 1.000
DEFAULT_MIN_WEIGHT = 0.980
DEFAULT_MAX_WEIGHT = 1.020


@dataclass
class WeightLimits:
    """
    Configurable packing limits - create one of these per product
    rather than hard-coding limits into the validation function itself.

    Attributes
    ----------
    min_weight : float
        Lower acceptance limit (kg, inclusive).
    max_weight : float
        Upper acceptance limit (kg, inclusive).
    target_weight : float
        Nominal / expected packed weight (kg). Kept for logging and
        documentation; not used in the comparison itself.
    """
    min_weight: float = DEFAULT_MIN_WEIGHT
    max_weight: float = DEFAULT_MAX_WEIGHT
    target_weight: float = DEFAULT_TARGET_WEIGHT

    def __post_init__(self):
        if self.min_weight > self.max_weight:
            raise ValueError(
                f"min_weight ({self.min_weight}) cannot be greater than "
                f"max_weight ({self.max_weight})"
            )


@dataclass
class WeightCheckResult:
    """Result of a single weight validation."""
    value: Optional[float]
    status: str
    reason: str

    def __str__(self) -> str:
        if self.value is None:
            return f"{self.status}: {self.reason}"
        return f"{self.status}: {self.value:.3f} kg - {self.reason}"


# Module-level default instance (matches alert_rules.md)
DEFAULT_LIMITS = WeightLimits(
    min_weight=DEFAULT_MIN_WEIGHT,
    max_weight=DEFAULT_MAX_WEIGHT,
    target_weight=DEFAULT_TARGET_WEIGHT,
)


def validate_weight(
    value: Optional[float],
    limits: WeightLimits = DEFAULT_LIMITS,
) -> WeightCheckResult:
    """
    Compares one weight reading against the given limits.

    Parameters
    ----------
    value : float | None
        A plain float (from Week 7's ParseResult.value when is_valid is True),
        or None for an invalid/missing reading.
    limits : WeightLimits
        Always pass your own configured limits in real use.
        The module-level default exists only so the function is directly
        callable/testable without setup.

    Returns
    -------
    WeightCheckResult
        Contains the original value, a status string
        (NORMAL / UNDERWEIGHT / OVERWEIGHT / INVALID_READING),
        and a human-readable reason.
    """
    # --- Invalid / missing reading (docs/alert_rules.md section 5) ---
    if value is None:
        return WeightCheckResult(
            value=None,
            status=INVALID_READING,
            reason="No valid weight reading available (invalid or missing OCR input)",
        )

    # Defensive type check (Week 7 should already guarantee float)
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return WeightCheckResult(
            value=None,
            status=INVALID_READING,
            reason=f"Cannot convert value to float: {value!r}",
        )

    # --- Limit comparison (docs/alert_rules.md section 2) ---
    if weight < limits.min_weight:
        return WeightCheckResult(
            value=weight,
            status=UNDERWEIGHT,
            reason=f"{weight:.3f} kg is below the minimum limit of {limits.min_weight:.3f} kg",
        )

    if weight > limits.max_weight:
        return WeightCheckResult(
            value=weight,
            status=OVERWEIGHT,
            reason=f"{weight:.3f} kg is above the maximum limit of {limits.max_weight:.3f} kg",
        )

    # Inside the allowed window (inclusive boundaries)
    return WeightCheckResult(
        value=weight,
        status=NORMAL,
        reason=(
            f"{weight:.3f} kg is within the allowed range "
            f"[{limits.min_weight:.3f}, {limits.max_weight:.3f}] kg"
        ),
    )


# ----------------------------------------------------------------------
# Standalone self-test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    limits = WeightLimits(min_weight=0.980, max_weight=1.020, target_weight=1.000)

    test_cases = [
        1.005,   # NORMAL
        1.035,   # OVERWEIGHT
        0.950,   # UNDERWEIGHT
        0.980,   # exact lower bound
        1.020,   # exact upper bound
        None,    # INVALID_READING
        -8.0,    # UNDERWEIGHT
        12.5,    # OVERWEIGHT
    ]

    print(f"Limits: min={limits.min_weight}, max={limits.max_weight}, "
          f"target={limits.target_weight}\n")
    print(f"{'Value':<10} {'Status':<16} Reason")
    print("-" * 75)

    for value in test_cases:
        result = validate_weight(value, limits)
        print(f"{str(result.value):<10} {result.status:<16} {result.reason}")       
