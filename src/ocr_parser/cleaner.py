"""
cleaner.py
==========
Basic cleaning layer for raw OCR strings, applied BEFORE any validation.

This layer only performs corrections that have exactly one unambiguous
interpretation (see docs/ocr_error_analysis.md, "Safe to auto-correct").
It deliberately does NOT attempt to fix ambiguous problems -- inserting a
missing decimal point, guessing a missing negative sign, or reconstructing
a mostly-garbled string. Those require judgment calls a cleaning layer
shouldn't make silently; they belong to validation/rejection logic later
in the pipeline, not here.

Five cleaning steps, applied in order:
    1. Remove unnecessary whitespace (leading/trailing)
    2. Handle spaces between digits (collapse internal whitespace)
    3. Normalize known character confusions (O->0, I/l->1, S->5, B->8),
       safe only because the field is numeric-only
    4. Normalize decimal separators (comma -> period), only in the
       single well-defined comma-as-decimal pattern
    5. Remove characters not permitted by the expected weight format
       (anything outside 0-9, '.', '-')
"""

import re

# Letter -> digit substitutions that are only valid because the field is
# numeric-only. Case-insensitive: covers both upper and lower case.
CHARACTER_CONFUSION_MAP = {
    "O": "0", "o": "0",
    "I": "1", "l": "1", "i": "1",
    "S": "5", "s": "5",
    "B": "8", "b": "8",
}

# Everything allowed in a final weight reading: digits, one decimal point,
# one leading minus sign.
ALLOWED_CHARACTERS = set("0123456789.-")


def remove_unnecessary_whitespace(text: str) -> str:
    """Task 1: strip leading/trailing whitespace."""
    return text.strip()


def handle_spaces_between_digits(text: str) -> str:
    """Task 2: a single OCR reading of a display should never legitimately
    contain internal spaces (e.g. '1 2 . 5' or '12 .5') -- these are
    spacing artifacts from character-level detection, not meaningful
    separators. Collapse all internal whitespace."""
    return re.sub(r"\s+", "", text)


def normalize_character_confusions(text: str) -> str:
    """Task 3: map letters that are never valid in a numeric-only field
    to the digit they're almost always mistaken for. Safe only because
    the field is constrained to be numeric-only -- see
    docs/ocr_error_analysis.md for why this doesn't generalize to
    mixed alphanumeric text."""
    return "".join(CHARACTER_CONFUSION_MAP.get(ch, ch) for ch in text)


def normalize_decimal_separator(text: str) -> str:
    """Task 4: comma -> period, but ONLY in the narrow, well-defined
    pattern of exactly one comma followed by 1-2 digits before the string
    ends (e.g. '12,50' -> '12.50'). This deliberately does NOT touch
    strings with multiple commas or a comma not in a decimal position,
    since those could be a thousands separator or garbage -- guessing
    there would be an unsafe correction, not a safe one."""
    match = re.fullmatch(r"(-?\d+),(\d{1,2})", text)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return text


def remove_disallowed_characters(text: str) -> str:
    """Task 5: strip anything left over that isn't part of the expected
    weight format (digits, one decimal point, one leading minus). This
    runs LAST, after character-confusion normalization has already
    recovered any letters that were safely fixable -- so what's left
    over here is genuine noise, not a digit in disguise."""
    return "".join(ch for ch in text if ch in ALLOWED_CHARACTERS)


def clean(text: str) -> str:
    """Runs all five cleaning steps in order. Returns the cleaned string --
    NOT yet validated as a well-formed number (that's the next stage of
    the pipeline, not this file's job)."""
    if text is None:
        return ""

    result = text
    result = remove_unnecessary_whitespace(result)
    result = handle_spaces_between_digits(result)
    result = normalize_character_confusions(result)
    result = normalize_decimal_separator(result)
    result = remove_disallowed_characters(result)
    return result


if __name__ == "__main__":
    # Quick self-test using the examples from docs/ocr_error_analysis.md --
    # no images or OCR pipeline needed, this file is fully standalone.
    test_cases = [
        "  38  ",           # whitespace
        "1 2 . 5",          # spaces between digits
        "9O",                # O -> 0 confusion
        "I2.5",              # I -> 1 confusion
        "5S.0",               # S -> 5 confusion (mid-string)
        "12,50",             # comma decimal separator
        "12,500",            # comma NOT in decimal position -- not converted
                              # to a period, but still stripped as a
                              # disallowed character by the final step
                              # (task 5), leaving '12500'
        "8E",                 # leftover junk letter, no known mapping
        "hL",                 # fully garbled, nothing recoverable
        "-12.5",              # already clean
    ]

    print(f"{'Raw':<12} -> {'Cleaned':<12}")
    print("-" * 28)
    for raw in test_cases:
        print(f"{raw!r:<12} -> {clean(raw)!r}")
