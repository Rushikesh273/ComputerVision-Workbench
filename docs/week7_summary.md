# Week 7 Summary — OCR Parsing & Error Correction

## Final Pipeline

```
Raw OCR text → cleaner.clean() → validator.validate() → range check → float()
```

Three modules, each with one clearly bounded job:

- **`cleaner.py`** — text in, text out. Strips whitespace, safely normalizes known letter confusions (`O`→`0`, `I`/`l`→`1`, `S`→`5`, `B`→`8`), converts a narrow comma-decimal pattern to a period, strips anything left outside `0-9.-`. Never judges validity, never produces a number.
- **`validator.py`** — checks *shape* only. Anchored regex confirms the cleaned string looks like a well-formed integer or decimal. Never changes the string, never checks whether the *value* is plausible.
- **`parser.py`** — ties it together via `parse_weight()`. Calls `cleaner.clean()`, then `validator.validate()`, adds a **range check** (neither earlier module does this — a structurally valid number can still be an implausible reading), and is the only place the string finally becomes a Python `float`.

Every call returns a `ParseResult(raw, cleaned, value, is_valid, reason)` — callers always get the full story, whether the input was valid or not.

## Testing Summary

`tests/test_ocr_parser.py` — 39 tests, all passing, covering:

- Correct readings (integers, decimals, negatives) parsing straight through
- Known-safe corrections (letter confusions, comma separators, whitespace)
- Structurally invalid input correctly rejected (multiple decimals, misplaced minus signs, decimal points missing a side)
- Edge cases: `None`, empty strings, whitespace-only strings, out-of-range values, custom range bounds
- Real raw OCR outputs logged during this project (`"38"`, `"74"`, `"97"` from EasyOCR) confirmed to parse without crashing

## Known Limitation, Found During Testing 

Writing the invalid-input tests surfaced a real gap, not a test-writing mistake:

**`cleaner.py`'s final step (strip disallowed characters) doesn't check how much of the original string was junk before stripping it.** This means:

| Input | Cleaned | Result | Is this okay? |
|---|---|---|---|
| `"12a.5"` | `"12.5"` | `12.5`, valid | Yes — one stray junk letter next to an otherwise clean number, safely dropped |
| `"+12"` | `"12"` | `12.0`, valid | Yes — a leading `+` is a reasonable strip on an otherwise clean number |
| `"abc"` | `"8"` | `8.0`, valid | **No** — the whole string is noise; `8` only appears because `b` happens to map to `8` via the letter-confusion table |
| `"N 06 0 口 ai"` (a real garbled PaddleOCR output from this project) | `"0601"` | `601.0`, valid | **No** — same problem, confident-looking number manufactured from mostly noise |

This directly violates the principle established in Monday's `docs/ocr_error_analysis.md`: a mostly-garbled result should be **rejected outright**, not partially parsed into something that looks confident. The pipeline currently can't distinguish "one incidental junk character" from "this string is mostly junk" — both just lose their non-numeric characters the same way.

This is documented explicitly as a **known gap**, with a dedicated test (`test_mostly_garbled_strings_currently_pass_validation_KNOWN_GAP`) that asserts *current* behavior rather than desired behavior — so if `cleaner.py` or `parser.py` changes in a way that affects this, the test starts failing immediately instead of the gap silently persisting unnoticed.


## Design Principle Followed Throughout

The same rule from Monday's analysis governed every day's work:

> A wrong "corrected" value is more dangerous than an admitted failure, because it looks just as confident as a right one.

Two deliberate, intentional limitations reflect this, both covered by tests:

- **Missing decimal points are never inserted** (`"38"` parses to `38.0`, not guessed as `3.8`), even though this is the single most common real error found in this project's own OCR testing — there's no way to tell "decimal was dropped" apart from "this is genuinely the integer 38" from the string alone.
- **Duplicate-detection artifacts are never removed** (`"112.50"` parses to `112.5` as-is) — resolving whether a digit was genuinely repeated or double-detected needs to happen at the image/bounding-box level, not guessed from text.

The garbage-string gap found today is the one place this project's actual behavior currently falls short of that stated principle — worth fixing before this pipeline is trusted on live data.
