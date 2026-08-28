"""
test_ocr_parser.py
===================
Unit tests for the OCR parsing pipeline (cleaner.py + validator.py +
parser.py), covering:
    - Correct readings that should parse straight through
    - Common OCR errors that should be safely corrected
    - Invalid inputs that should be rejected, not guessed at
    - Edge cases: empty strings, None, unexpected characters, malformed numbers

Run with:
    pytest tests/test_ocr_parser.py -v
"""

import sys
from pathlib import Path


def _find_ocr_parser_dir(start: Path) -> Path:
    """Walk upward from this test file looking for a src/ocr_parser
    directory, so this test suite works regardless of exactly how deep
    tests/ sits relative to the repo root -- rather than assuming a
    fixed 'tests/../src/ocr_parser' distance, which breaks the moment
    the actual folder layout differs even slightly."""
    current = start.resolve()
    for candidate_root in [current] + list(current.parents):
        candidate = candidate_root / "src" / "ocr_parser"
        if candidate.is_dir():
            return candidate
    raise RuntimeError(
        "Could not find a 'src/ocr_parser' directory above "
        f"{start} -- make sure cleaner.py, validator.py, and parser.py "
        "live in src/ocr_parser/ somewhere above this test file."
    )


# Make src/ocr_parser importable directly (flat module imports, matching
# how cleaner.py/validator.py/parser.py import each other) without
# requiring the project to be pip-installed as a package.
sys.path.insert(0, str(_find_ocr_parser_dir(Path(__file__).parent)))

import pytest

from cleaner import clean
from validator import validate
from parser import parse_weight


# ---------------------------------------------------------------------------
# Correct readings -- should parse straight through unchanged
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected_value", [
    ("125", 125.0),
    ("0", 0.0),
    ("-8", -8.0),
    ("12.50", 12.5),
    ("9.5", 9.5),
    ("-0.0", -0.0),
    ("3.8", 3.8),
])
def test_correct_readings_parse_successfully(raw, expected_value):
    result = parse_weight(raw)
    assert result.is_valid is True
    assert result.value == expected_value
    assert result.reason == ""


# ---------------------------------------------------------------------------
# Common OCR errors -- should be safely corrected, per docs/ocr_error_analysis.md
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected_cleaned, expected_value", [
    ("9O", "90", 90.0),        # letter O -> 0
    ("I2", "12", 12.0),        # letter I -> 1
    ("5S.0", "55.0", 55.0),    # letter S -> 5 (mid-string)
    ("12,50", "12.50", 12.5),  # comma decimal separator -> period
    ("  38  ", "38", 38.0),    # surrounding whitespace stripped
    ("1 2 . 5", "12.5", 12.5), # internal spacing collapsed
])
def test_known_errors_are_corrected_correctly(raw, expected_cleaned, expected_value):
    result = parse_weight(raw)
    assert result.cleaned == expected_cleaned
    assert result.is_valid is True
    assert result.value == expected_value


def test_known_correction_functions_match_parser_behavior():
    """Sanity check that parser.py's cleaning step gives the exact same
    result as calling cleaner.clean() directly -- parser.py should not be
    silently doing anything different from the dedicated cleaning module."""
    for raw in ["9O", "12,50", "  38  ", "5S.0"]:
        assert parse_weight(raw).cleaned == clean(raw)


# ---------------------------------------------------------------------------
# Invalid inputs -- should be rejected, never guessed at or force-converted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected_reason_contains", [
    ("12.5.0", "decimal"),
    ("--12.5", "minus"),
    ("12-5", "minus"),
    ("12.5-", "minus"),
    (".5", "decimal"),
    ("5.", "decimal"),
    (".", "digits"),
    ("hL", "Empty"),  # cleans to '' -- fully garbled, nothing recoverable
])
def test_invalid_readings_are_rejected_not_converted(raw, expected_reason_contains):
    result = parse_weight(raw)
    assert result.is_valid is False
    assert result.value is None
    assert expected_reason_contains.lower() in result.reason.lower()


@pytest.mark.parametrize("raw, expected_value", [
    ("12a.5", 12.5),   # one stray junk letter next to an otherwise clean
                       # number -- stripping it safely recovers the reading
    ("+12", 12.0),     # a leading '+' on an otherwise clean number is a
                       # reasonable strip, not a guess
])
def test_single_stray_junk_character_is_safely_stripped(raw, expected_value):
    result = parse_weight(raw)
    assert result.is_valid is True
    assert result.value == expected_value


def test_missing_decimal_point_is_not_guessed():
    """Documents an INTENTIONAL limitation, not a bug: '38' is a valid-
    looking integer by the defined rules, even though we know from real
    project testing that this is often actually '3.8' with a dropped
    decimal point. The parser must NOT guess this -- see parser.py's
    module docstring and docs/ocr_error_analysis.md for the reasoning."""
    result = parse_weight("38")
    assert result.is_valid is True
    assert result.value == 38.0  # NOT 3.8 -- guessing would be unsafe


def test_duplicate_character_artifact_is_not_fixed():
    """Similarly intentional: '112.50' (a plausible duplicate-detection
    artifact of '12.50') is well-formed by the regex rules, so it parses
    successfully as 112.5 rather than being rejected or silently
    'de-duplicated' -- resolving this ambiguity is out of scope for a
    text-only parser (see docs/ocr_error_analysis.md)."""
    result = parse_weight("112.50")
    assert result.is_valid is True
    assert result.value == 112.5


def test_out_of_range_value_is_rejected():
    """A structurally valid number can still be an implausible reading --
    range validation catches what regex validation can't."""
    result = parse_weight("9999999")
    assert result.is_valid is False
    assert result.value is None
    assert "range" in result.reason.lower()


def test_custom_range_bounds_are_respected():
    result = parse_weight("500", min_value=0.0, max_value=100.0)
    assert result.is_valid is False
    assert "range" in result.reason.lower()

    result = parse_weight("50", min_value=0.0, max_value=100.0)
    assert result.is_valid is True
    assert result.value == 50.0


# ---------------------------------------------------------------------------
# Edge cases: empty strings, None, unexpected characters, malformed numbers
# ---------------------------------------------------------------------------

def test_none_input_is_rejected():
    result = parse_weight(None)
    assert result.is_valid is False
    assert result.value is None
    assert result.raw is None
    assert "None" in result.reason


def test_empty_string_is_rejected():
    result = parse_weight("")
    assert result.is_valid is False
    assert result.value is None
    assert "empty" in result.reason.lower()


def test_whitespace_only_string_is_rejected():
    result = parse_weight("   ")
    assert result.is_valid is False
    assert result.value is None


@pytest.mark.parametrize("raw", [
    "-",               # bare minus, no digits
    "-.",              # bare minus + decimal, no digits
])
def test_bare_sign_with_no_digits_is_rejected(raw):
    result = parse_weight(raw)
    assert result.is_valid is False
    assert result.value is None


@pytest.mark.parametrize("raw, produces_value", [
    # KNOWN LIMITATION, documented here rather than hidden: cleaner.py's
    # final "strip disallowed characters" step doesn't check how MUCH of
    # the string was junk before stripping it -- so a string that's
    # almost entirely noise can still produce a confident-looking,
    # structurally valid number. This is a real gap against Monday's own
    # rule ("reconstructing a number from a mostly-garbled result...
    # reject outright") -- a junk-ratio check in cleaner.py or parser.py
    # would close it, but is not yet implemented as of this test.
    ("abc", 8.0),                # only 'b' -> '8' via confusion map;
                                  # 'a'/'c' silently dropped as noise
    ("N 06 0 口 ai", 601.0),      # real garbled PaddleOCR output from
                                  # this project -- reduces to '0601'
])
def test_mostly_garbled_strings_currently_pass_validation_KNOWN_GAP(raw, produces_value):
    result = parse_weight(raw)
    # This asserts CURRENT behavior, not desired behavior -- it exists so
    # this gap is caught immediately (test starts failing) if cleaner.py
    # or parser.py changes in a way that affects it, rather than the gap
    # silently persisting unnoticed.
    assert result.is_valid is True
    assert result.value == produces_value


def test_result_always_has_all_expected_fields():
    """Every ParseResult, valid or not, should expose the same fields --
    raw text, cleaned text, parsed value, validity, and reason -- so
    callers never have to special-case which fields exist."""
    for raw in ["12.5", "invalid!!", None, ""]:
        result = parse_weight(raw)
        assert hasattr(result, "raw")
        assert hasattr(result, "cleaned")
        assert hasattr(result, "value")
        assert hasattr(result, "is_valid")
        assert hasattr(result, "reason")


# ---------------------------------------------------------------------------
# Real project data -- every raw OCR string actually logged in this
# project's ocr_results.csv (Week 6's final pipeline run, EasyOCR/
# Tesseract/PaddleOCR only -- YOLO Digit Detection rows excluded, as this
# parser's scope is text output from general-purpose OCR engines).
#
# expected_valid/expected_value below are the VERIFIED actual outcomes
# from running each real string through parse_weight() -- this is a
# regression suite, not a target: it locks in current real-world
# behavior so any future change to cleaner.py/validator.py/parser.py
# that changes how these specific real readings are handled shows up
# immediately as a failing test, intentional or not.
# ---------------------------------------------------------------------------

REAL_OCR_RESULTS = [
    # (image, method, raw, expected_valid, expected_value)
    ("001", "EasyOCR",   "38",   True,  38.0),
    ("001", "Tesseract", "37",   True,  37.0),
    ("001", "PaddleOCR", "3.8",  True,  3.8),
    ("002", "EasyOCR",   "74",   True,  74.0),
    ("002", "Tesseract", "-",    False, None),
    ("002", "PaddleOCR", "74",   True,  74.0),
    ("003", "EasyOCR",   "95",   True,  95.0),
    ("003", "Tesseract", "35",   True,  35.0),
    ("003", "PaddleOCR", "9.5",  True,  9.5),
    ("004", "EasyOCR",   "",     False, None),
    ("004", "Tesseract", "-",    False, None),
    ("004", "PaddleOCR", "11.4", True,  11.4),
    ("005", "EasyOCR",   "10",   True,  10.0),
    ("005", "Tesseract", "0",    True,  0.0),
    ("005", "PaddleOCR", "10.0", True,  10.0),
    ("006", "EasyOCR",   "13",   True,  13.0),
    ("006", "Tesseract", "",     False, None),
    ("006", "PaddleOCR", "1.3",  True,  1.3),
    ("007", "EasyOCR",   "",     False, None),
    ("007", "Tesseract", "",     False, None),
    ("007", "PaddleOCR", "1.4",  True,  1.4),
    ("008", "EasyOCR",   "80",   True,  80.0),
    ("008", "Tesseract", "-.",   False, None),
    ("008", "PaddleOCR", "0.0",  True,  0.0),
    ("009", "EasyOCR",   "",     False, None),
    ("009", "Tesseract", "",     False, None),
    ("009", "PaddleOCR", "110",  True,  110.0),
    ("010", "EasyOCR",   "9",    True,  9.0),
    ("010", "Tesseract", "",     False, None),
    ("010", "PaddleOCR", "97",   True,  97.0),
]

# Ground truth per image, for the separate exact-match accuracy summary below.
REAL_GROUND_TRUTH = {
    "001": 3.8, "002": 7.4, "003": 9.5, "004": 11.4, "005": 10.0,
    "006": 1.3, "007": 1.4, "008": 0.0, "009": 9.0, "010": 9.7,
}


@pytest.mark.parametrize("image, method, raw, expected_valid, expected_value", REAL_OCR_RESULTS)
def test_real_project_ocr_outputs_match_verified_behavior(image, method, raw, expected_valid, expected_value):
    """Every raw string actually logged in this project's Week 6 pipeline
    run (ocr_results.csv), parsed through the real Week 7 pipeline. Locks
    in verified current behavior as a regression suite -- confirms the
    parser never crashes on real-world messy input, correctly rejects
    genuinely malformed readings (Tesseract's '-', '-.', empty strings)
    instead of force-converting them, and reflects the documented
    missing-decimal limitation consistently on real data, not just
    hand-picked examples."""
    result = parse_weight(raw)
    assert result.is_valid is expected_valid, (
        f"{image}/{method}: raw={raw!r} expected is_valid={expected_valid}, got {result.is_valid}"
    )
    assert result.value == expected_value, (
        f"{image}/{method}: raw={raw!r} expected value={expected_value}, got {result.value}"
    )


def test_real_project_exact_match_summary():
    """Not a per-case assertion -- computes overall exact-match accuracy
    per engine across the real dataset, matching what week7_summary.md
    and docs/ocr_pipeline_results.md report, so this number can never
    silently drift out of sync with the documentation without a test
    failure to catch it."""
    per_engine_matches = {"EasyOCR": 0, "Tesseract": 0, "PaddleOCR": 0}
    per_engine_total = {"EasyOCR": 0, "Tesseract": 0, "PaddleOCR": 0}

    for image, method, raw, _, _ in REAL_OCR_RESULTS:
        result = parse_weight(raw)
        per_engine_total[method] += 1
        gt = REAL_GROUND_TRUTH[image]
        if result.is_valid and result.value == gt:
            per_engine_matches[method] += 1

    # These are the verified real numbers from this project's actual run --
    # see docs/ocr_pipeline_results.md for the full breakdown and analysis.
    assert per_engine_matches["EasyOCR"] == 1     # 1/10 (005, exact by coincidence)
    assert per_engine_matches["Tesseract"] == 0   # 0/10
    assert per_engine_matches["PaddleOCR"] == 7   # 7/10

