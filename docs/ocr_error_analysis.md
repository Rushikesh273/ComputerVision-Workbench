# OCR Error Analysis — Understanding Common Mistakes

## 1. Common Character-Level Confusion

These are the classic confusions OCR engines make between visually similar characters:

| Confused Pair | Why it happens |
|---|---|
| `0` / `O` | Nearly identical shape in most fonts and rendering styles |
| `1` / `I` / `l` | A thin vertical stroke with little distinguishing detail |
| `5` / `S` | Similar curve structure, especially at low resolution |
| `8` / `B` | Both have two stacked loops |

In a numeric-only field (a display that only ever shows digits, a decimal
point, and a minus sign), none of the letter forms above are ever
legitimately correct — their appearance in the output is always an error,
never a valid reading.

A closely related problem is digit-to-digit confusion driven by shape
similarity rather than letter-vs-digit confusion — most notably **2 vs 5**,
which can look alike depending on which segments are lit and how sharp the
image is. This is the same underlying category of mistake (visual
similarity causing misclassification) but harder to resolve from the
character alone, since both are valid digits.

## 2. Missing/Extra Decimal Points, Spacing, and Sign Errors

Across real testing on this project's own display images, this category is
by far the most common source of error — more common than any letter/digit
substitution.

### Missing decimal point (the dominant failure pattern)

Numbers like `3.8`, `7.4`, `9.5`, `9.7`, `1.3`, `9.0` were repeatedly read
back as `38`, `74`, `95`, `97`, `13`, `90` — the digits themselves were read
correctly, but the decimal point (visually the smallest, dimmest mark on
the display) was simply never detected. The result looks like a valid
number, which makes this error especially dangerous: nothing about the
output `38` looks obviously wrong on its own.

### Total reading failure

In some cases, no usable reading was produced at all — an empty result, or
a bare `-` or `-.` with no digits recovered. This is different from a
malformed-but-recoverable reading: there's no partial signal to work with,
just an absence.

### Missing negative sign

A leading `-` is the same kind of small, easy-to-miss mark as a decimal
point, and is vulnerable to the same failure: `12.5` read back instead of
`-12.5`, with the sign silently dropped. Unlike a missing decimal point,
there is no way to recover a dropped sign from the digits alone — a
positive 12.5 and a negative 12.5 that lost its sign produce the exact same
remaining text.

### Duplicate characters

Occasionally a single digit gets read twice in a row — e.g. `112.50`
instead of `12.50` — typically because the same character was picked up as
two overlapping detections rather than one. This produces a
plausible-looking but wrong-length number.

### Comma vs. decimal point (locale differences)

In some locales, a comma is used where a period would normally mark the
decimal — `12,50` meaning `12.50`. Left unhandled, this either produces an
unparseable value or, worse, gets misread as a thousands separator.

## 3. Fifteen Realistic OCR Error Examples

| # | Raw OCR Output | Likely Ground Truth | Error Type |
|---|---|---|---|
| 1 | `38` | `3.8` | Missing decimal |
| 2 | `74` | `7.4` | Missing decimal |
| 3 | `95` | `9.5` | Missing decimal |
| 4 | `13` | `1.3` | Missing decimal |
| 5 | `90` | `9.0` | Missing decimal |
| 6 | `97` | `9.7` | Missing decimal |
| 7 | `184` | `11.4` | Missing decimal + digit drop |
| 8 | *(empty)* | `1.4` | Total detection failure |
| 9 | `-` | `7.4` | Total detection failure |
| 10 | `-.` | `0.0` | Total detection failure |
| 11 | `8E` | `3.8` | Letter hallucinated next to a real digit |
| 12 | `hL` | `7.4` | Full hallucination, no real digit recovered |
| 13 | `12,50` | `12.50` | Locale comma-as-decimal |
| 14 | `12.5` | `-12.5` | Missing negative sign |
| 15 | `112.50` | `12.50` | Duplicate character |

## 4. Safe vs. Reject: Correction Rules

The core design question: **when is it safe to automatically correct a raw
OCR reading, and when should it be rejected and flagged for manual review
instead?** A wrong "corrected" value is more dangerous than an admitted
failure, because it looks just as confident as a right one.

### Safe to auto-correct

These corrections have exactly one reasonable interpretation given the
constraint that the field is numeric-only:

- Stripping leading/trailing whitespace — never changes meaning.
- Mapping `O`→`0`, `I`/`l`→`1`, `S`→`5`, `B`→`8` **only within a field
  known to be numeric-only** — in that context these letters are never
  valid, so the substitution is unambiguous.
- Converting a comma to a decimal point, **only when exactly one comma is
  present and it's followed by one or two digits before the string ends**
  (e.g. `12,50` → `12.50`) — a narrow, well-defined pattern, not a general
  rule.
- Collapsing internal spacing within a number (e.g. `1 2 . 5` → `12.5`) —
  spacing artifacts don't change which digits were actually read.

### Reject / flag for manual review

These involve a genuine fork where more than one original reading could
have produced the same broken output — correcting them means guessing, not
fixing:

- **Inserting a missing decimal point** (e.g. `38` → `3.8`). This is the
  single most common real error found, and it is *not* safely fixable from
  the text alone — `38` could genuinely be the integer 38. Without external
  context (a known expected format, or a fresh re-read), this should be
  flagged, not silently corrected.
- **Inserting a missing negative sign.** There's no way to tell "the sign
  was dropped" from "the value is genuinely positive." Guessing here risks
  silently flipping the sign of a real reading.
- **Reconstructing a number from a mostly-garbled result** (e.g. `hL`,
  or a result with more junk characters than digits). Too little signal to
  work with — attempting to extract "the real number" here is guessing
  dressed up as correction. Reject outright.
- **"Fixing" an empty or near-empty result** (bare `-`, bare `-.`). There is
  no partial reading to salvage — this should be treated as a failed
  capture needing a re-read, not a malformed string needing a patch.
- **Resolving digit-shape confusion** (e.g. 2 vs 5) from the text alone.
  Both are valid digits; nothing in the character itself indicates which
  one was actually shown. This needs to be resolved by looking at the
  actual image again, not guessed from the output string.
- **Removing suspected duplicate characters** (e.g. `112.50` → `12.50`).
  From the text alone, there's no way to distinguish a genuine 3-digit
  reading from a duplication artifact — this needs to be resolved before
  the text is produced, not guessed afterward.

### The dividing principle

Every "safe" rule above has exactly one unambiguous correct interpretation
once the constraints of the field are known. Every "reject" rule involves a
genuine fork — multiple different original readings could plausibly explain
the same broken output — and choosing one of them without more information
is a guess, not a correction.
