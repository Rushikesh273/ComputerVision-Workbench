"""
parser.py
=========
Combines cleaner.py + validator.py + range validation + float conversion
into one entry point: parse_weight().

Pipeline (matches the Week 7 spec exactly):
    Raw OCR -> Normalize -> Clean -> Apply Correction Rules
             -> Regex Validation -> Range Validation -> Final Float

The "Normalize / Clean / Apply Correction Rules" stages are all handled by
cleaner.clean() -- that module's five functions already ARE the predefined,
safe correction rules (letter-to-digit mapping, comma-to-period, disallowed-
character removal). This module does not invent any NEW correction rules
on top of that. Per the task instruction "apply only predefined correction
rules; do not blindly guess ambiguous values," anything not already
established as safe in docs/ocr_error_analysis.md is left for regex
validation to reject, never guessed at here.

IMPORTANT, INTENTIONAL LIMITATION: this parser does NOT insert a missing
decimal point. A raw reading like "38" is a perfectly valid-looking integer
by the rules defined in validator.py, so it parses to 38.0 -- even in cases
where the true display reading was actually 3.8 with a dropped decimal
point (a real, common failure mode documented in docs/ocr_error_analysis.md
and confirmed repeatedly in this project's own OCR testing). This is by
design, not a bug: from the string "38" alone, there is no reliable way to
tell "the decimal was dropped" apart from "this is genuinely the integer
38." Guessing which one it is would be exactly the kind of unsafe,
ambiguous correction Monday's analysis explicitly ruled out.
"""

from dataclasses import dataclass
from typing import Optional

from cleaner import clean
from validator import validate

# Plausible operating range for a weight reading. These are generic
# placeholder bounds, NOT derived from any real device specification --
# calibrate min_value/max_value to your actual scale's real operating
# range before relying on this for anything beyond testing.
DEFAULT_MIN_WEIGHT = -1000.0
DEFAULT_MAX_WEIGHT = 1000.0


@dataclass
class ParseResult:
    raw: Optional[str]
    cleaned: str
    value: Optional[float]
    is_valid: bool
    reason: str


def parse_weight(
    raw_text: Optional[str],
    min_value: float = DEFAULT_MIN_WEIGHT,
    max_value: float = DEFAULT_MAX_WEIGHT,
) -> ParseResult:
    """
    Runs the full pipeline on one raw OCR string:
        Normalize -> Clean -> Apply Correction Rules
        -> Regex Validation -> Range Validation -> Final Float

    Returns a ParseResult with the raw text, cleaned/corrected text, the
    parsed float (None if invalid), a validity flag, and a reason (empty
    string when valid).
    """
    if raw_text is None:
        return ParseResult(raw=None, cleaned="", value=None,
                            is_valid=False, reason="Input is None")

    # Normalize + Clean + Apply Correction Rules -- all three pipeline
    # stages live inside cleaner.clean(), since its functions already ARE
    # the predefined, safe correction rules.
    cleaned = clean(raw_text)

    # Regex Validation
    format_valid, reason = validate(cleaned)
    if not format_valid:
        return ParseResult(raw=raw_text, cleaned=cleaned, value=None,
                            is_valid=False, reason=reason)

    # Final Float conversion -- safe here because validate() already
    # guaranteed the string matches a well-formed integer/decimal shape.
    value = float(cleaned)

    # Range Validation
    if not (min_value <= value <= max_value):
        return ParseResult(
            raw=raw_text, cleaned=cleaned, value=None, is_valid=False,
            reason=f"Value {value} outside expected range [{min_value}, {max_value}]",
        )

    return ParseResult(raw=raw_text, cleaned=cleaned, value=value,
                        is_valid=True, reason="")


if __name__ == "__main__":
    # Standalone self-test -- plain strings only, no images or upstream
    # pipeline needed, same pattern as cleaner.py and validator.py's own tests.
    test_cases = [
        "38",         # missing decimal (real project data) -- parses as 38.0,
                      # NOT corrected to 3.8 -- see module docstring above
        "9O",         # letter confusion -> cleans to '90' -> valid integer
        "12,50",      # comma decimal -> cleans to '12.50' -> valid decimal
        "12.5.0",     # multiple decimals -> invalid, rejected by validator
        "hL",         # fully garbled -> cleans to '' -> invalid, empty
        "-8",         # valid negative integer
        "9999999",    # valid FORMAT, but fails range validation
        None,
        "",
    ]

    print(f"{'Raw':<12} {'Cleaned':<10} {'Value':<10} {'Valid':<6} Reason")
    print("-" * 75)
    for case in test_cases:
        result = parse_weight(case)
        print(f"{str(result.raw)!r:<12} {result.cleaned!r:<10} "
              f"{str(result.value):<10} {str(result.is_valid):<6} {result.reason}")
