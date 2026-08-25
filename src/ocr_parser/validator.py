"""
validator.py
=============
Regex-based validation of CLEANED OCR weight readings (i.e. text that has
already been through cleaner.py). This module answers one question per
input string: "is this a well-formed weight reading?" -- it does NOT try
to fix anything. A string either matches a valid format, or it's rejected
with a reason. Fixing ambiguous problems is cleaner.py's job (for the
narrow, safe cases) or simply not done at all (for ambiguous cases) --
see docs/ocr_error_analysis.md.

Valid formats:
    Integer:  optional leading '-', then one or more digits.
              e.g. '125', '-8', '0'
    Decimal:  optional leading '-', one or more digits, a single '.',
              then one or more digits. Both sides of the decimal point
              are required -- '.5' and '5.' are NOT valid on their own.
              e.g. '12.50', '-0.0', '9.5'

Explicitly invalid (each with its own diagnostic reason):
    - Multiple decimal points     ('12.5.0')
    - Repeated/misplaced minus    ('--12.5', '12-5', '12.5-')
    - Alphabetic characters       ('12a.5', 'abc')
    - Decimal point with a missing side  ('.5', '5.', '.')
    - Empty string / None
"""

import re

# One pattern per valid shape. Anchored with ^...$ so the ENTIRE string
# must match -- a regex without anchors would happily match a valid
# number sitting inside a longer invalid string (e.g. re.search would
# match '12.5' inside '12.5x', which is exactly the kind of false
# positive we don't want).
INTEGER_PATTERN = re.compile(r"^-?\d+$")
DECIMAL_PATTERN = re.compile(r"^-?\d+\.\d+$")

# Combined pattern covering both shapes in one regex, used when callers
# just want a yes/no rather than which shape it was.
WEIGHT_PATTERN = re.compile(r"^-?\d+(\.\d+)?$")


def is_valid_integer(text: str) -> bool:
    """True if text is a valid integer weight reading: optional leading
    '-', then one or more digits, nothing else."""
    if not text:
        return False
    return bool(INTEGER_PATTERN.match(text))


def is_valid_decimal(text: str) -> bool:
    """True if text is a valid decimal weight reading: optional leading
    '-', digits, a single '.', digits. Both sides of the decimal point
    are required."""
    if not text:
        return False
    return bool(DECIMAL_PATTERN.match(text))


def is_valid_weight_format(text: str) -> bool:
    """True if text is EITHER a valid integer or a valid decimal weight
    reading. This is the main reusable entry point most callers want."""
    if not text:
        return False
    return bool(WEIGHT_PATTERN.match(text))


def classify_format(text: str) -> str:
    """Returns 'integer', 'decimal', or 'invalid' -- useful when a caller
    needs to know WHICH valid shape matched, not just whether one did."""
    if is_valid_integer(text):
        return "integer"
    if is_valid_decimal(text):
        return "decimal"
    return "invalid"


def validate(text: str) -> tuple[bool, str]:
    """
    Main reusable validation function. Returns (is_valid, reason).

    reason is a human-readable explanation:
        - "" if valid
        - a specific diagnostic if invalid (used for logging/debugging,
          not for attempting any correction -- that's not this module's job)
    """
    if text is None:
        return False, "Input is None"
    if text == "":
        return False, "Empty string"

    if is_valid_weight_format(text):
        return True, ""

    # From here on, the string is invalid -- figure out WHY, for
    # diagnostic purposes only.
    if text.count(".") > 1:
        return False, "Multiple decimal points"
    if text.count("-") > 1:
        return False, "Repeated minus sign"
    if "-" in text and not text.startswith("-"):
        return False, "Minus sign not at the start"
    if re.search(r"[A-Za-z]", text):
        return False, "Contains alphabetic characters"
    if text in (".", "-", "-."):
        return False, "No digits present"
    if "+" in text:
        return False, "Contains a '+' sign (not a supported format)"
    if "." in text:
        # Strip an optional leading minus before checking each side of the
        # decimal point, so '-.5' is correctly caught here too (not just
        # '.5' and '5.').
        core = text[1:] if text.startswith("-") else text
        left, right = core.split(".", 1)
        if left == "" or right == "":
            return False, "Decimal point missing a digit on one side"

    return False, "Does not match a valid integer or decimal weight format"


if __name__ == "__main__":
    # Self-test, standalone -- no images or upstream pipeline needed,
    # just strings (matching how cleaner.py's own self-test works).
    test_cases = [
        "125",          # valid integer
        "-8",           # valid negative integer
        "12.50",        # valid decimal
        "-0.0",         # valid negative decimal
        "9.5",          # valid decimal
        "12.5.0",       # multiple decimal points
        "--12.5",       # repeated minus
        "12-5",         # misplaced minus
        "12.5-",        # trailing minus
        "12a.5",        # alphabetic
        "abc",          # fully alphabetic
        ".5",           # missing left side
        "5.",           # missing right side
        ".",            # just a decimal point
        "",             # empty string
        None,           # None
    ]

    print(f"{'Input':<12} {'Valid':<7} {'Reason'}")
    print("-" * 50)
    for case in test_cases:
        valid, reason = validate(case)
        print(f"{str(case)!r:<12} {str(valid):<7} {reason}")
