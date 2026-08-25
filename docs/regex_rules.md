# Regex Rules — Weight Reading Validation

## 1. Regex Concepts Used

A quick reference for the building blocks used in `validator.py`, in plain terms:

| Concept | Symbol/Example | What it means |
|---|---|---|
| Character class | `\d` | Matches any single digit (0–9) |
| Character class | `[A-Za-z]` | Matches any single letter, upper or lower case |
| Quantifier | `+` | One or more of the thing before it — `\d+` means "one or more digits" |
| Quantifier | `*` | Zero or more of the thing before it |
| Optional | `?` | Zero or one of the thing before it — `-?` means "an optional minus sign" |
| Anchor | `^` | Matches the very start of the string |
| Anchor | `$` | Matches the very end of the string |
| Group | `(...)` | Groups part of a pattern together, e.g. to make a whole chunk optional |
| Literal `.` (escaped) | `\.` | Inside a character class or outside one, `.` normally means "any character" — to match a literal decimal point, it must be escaped as `\.` |

**Why anchors matter here specifically:** without `^` and `$`, a pattern like `\d+\.\d+` would happily match the *valid-looking part* of an invalid string — for example, it would find `12.5` sitting inside `12.5x` or `xx12.5`, and report a match even though the full string isn't a valid reading. Anchoring forces the *entire* string to match the pattern, not just some substring of it.

## 2. Valid Formats Defined

### Valid integer

```
^-?\d+$
```

- `^` — start of string
- `-?` — an optional leading minus sign
- `\d+` — one or more digits
- `$` — end of string

Matches: `125`, `-8`, `0`, `00`

### Valid decimal

```
^-?\d+\.\d+$
```

- `^-?\d+` — same optional minus + digits as the integer pattern
- `\.` — a literal decimal point
- `\d+$` — one or more digits, through to the end of the string

Matches: `12.50`, `-0.0`, `9.5`

Both sides of the decimal point are **required**. `.5` and `5.` are deliberately **not** valid — a real weight reading from these displays always shows a digit on both sides of the decimal point (e.g. `0.0`, never a bare `.0`), so requiring both sides is a correctness check, not just a style preference.

### Combined weight format

```
^-?\d+(\.\d+)?$
```

Same as the integer pattern, with `(\.\d+)?` added as an *optional group* — "a decimal point followed by digits, if present at all." This single pattern is what most callers actually want: "is this a valid weight reading, integer or decimal, I don't care which."

## 3. Invalid Formats — What Gets Rejected, and Why

| Invalid Input | Reason Given | Why it's rejected rather than fixed here |
|---|---|---|
| `12.5.0` | Multiple decimal points | Ambiguous which decimal point was intended — not this module's job to guess, and not safely fixable by a simple rule either (see `docs/ocr_error_analysis.md`) |
| `--12.5` | Repeated minus sign | Same reasoning — ambiguous, reject rather than guess which minus (if any) was real |
| `12-5` / `12.5-` | Minus sign not at the start | A minus sign only makes sense as a leading sign; anywhere else it's a misdetection, not a valid negative number |
| `12a.5` / `abc` | Contains alphabetic characters | By the time text reaches this module, it's already been through `cleaner.py`'s safe letter-to-digit normalization — any letters still present here have no known safe mapping and must not be guessed at this stage |
| `.5` / `5.` / `-.5` | Decimal point missing a digit on one side | Both sides of the decimal are required for a valid reading, per the format rule above |
| `+12` | Contains a `+` sign | Not a format these displays ever produce — treated as invalid rather than silently accepted |
| `""` / `None` | Empty string / Input is None | No signal to validate at all |

## 4. Reusable Validation Functions

| Function | Returns | Purpose |
|---|---|---|
| `is_valid_integer(text)` | `bool` | True only for the integer format |
| `is_valid_decimal(text)` | `bool` | True only for the decimal format |
| `is_valid_weight_format(text)` | `bool` | True for either format — the general-purpose check |
| `classify_format(text)` | `"integer"` / `"decimal"` / `"invalid"` | When the caller needs to know *which* valid shape matched |
| `validate(text)` | `(bool, reason)` | The main entry point — validity plus a human-readable diagnostic when invalid |

## 5. Boundary With `cleaner.py`

This module assumes its input has **already been through `cleaner.py`** — it does not strip whitespace, normalize letter confusions, or convert comma decimal separators itself. Feeding `validator.py` raw, uncleaned OCR text (e.g. `"  9O  "`) will correctly report it as invalid, but not because the underlying reading is bad — because that text hasn't been cleaned yet. The two modules are meant to run in sequence, not interchangeably.
