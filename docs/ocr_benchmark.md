# OCR Engine Benchmark — 7-Segment Display Digits

**Engines tested:** EasyOCR, Tesseract, PaddleOCR
**Test images:** 10 cropped display photos (`factory_image_001_crop.jpg` – `010_crop.jpg`), output of `display_detector.py` → `crop_display.py`
**Source data:** `results.csv` (actual engine outputs, not simulated)

---

## 1. Methodology

**Character accuracy** is computed as:

```
character_accuracy = (total_ground_truth_chars − edit_distance(ground_truth, prediction)) / total_ground_truth_chars × 100
```

Edit distance (Levenshtein) is used rather than a naive position-by-position comparison, because predictions and ground truth are often different lengths (e.g. `EasyOCR` drops the decimal point: `3.8` → `38`). Position-by-position comparison would misalign every character after the first drop/insert and produce a meaningless score. This also means insertions (extra trailing characters, e.g. PaddleOCR's stray `口` glyph) are penalized as errors even though they don't corrupt the digits that *are* correct — worth keeping in mind when reading the per-image numbers below, since it can look harsher than "eyeballing" the result would suggest.

**Exact match accuracy** = predictions identical to ground truth, character-for-character (including decimal point), divided by total images.

**Processing time** — measured via the timing-instrumented `compare_engines.py` (per-call `time.perf_counter()`, with a warm-up call per engine before timing starts so model-loading isn't counted as processing time for image 1). No cold-start outlier showed up on image 1 for any engine, so the average below is a plain mean across all 10 images.

---

## 2. Results

| Engine | Exact Match Accuracy | Character Accuracy | Avg. Time | Major Failure |
|---|---|---|---|---|
| EasyOCR | 0% (0/10) | 40.6% | 0.156 s | Consistently drops the decimal point (`3.8`→`38`) on every reading; 3/10 images return nothing at all |
| Tesseract | 0% (0/10) | 12.5% | 0.113 s | Effectively non-functional on this input — wrong digits, empty, or single stray characters on 10/10 images |
| PaddleOCR | 60% (6/10) | 78.1% | 0.370 s | One severe misread (9.0 → 110) and a recurring stray `口` glyph appended to 2 results — both of which are also its two slowest calls (see §4) |

Character accuracy above is micro-averaged (total correct characters ÷ total ground-truth characters across all 10 images), which weights every character equally rather than every image equally. Macro-averaged (mean of each image's own percentage) gives EasyOCR 41.7%, Tesseract 12.5%, PaddleOCR 76.7% — close enough to the micro numbers that the choice of averaging isn't hiding anything here.

---

## 3. Timing detail

| Engine | Min | Max | Avg | Notes |
|---|---|---|---|---|
| Tesseract | 0.105 s | 0.127 s | 0.113 s | Fastest and most consistent — narrow spread across all 10 images |
| EasyOCR | 0.098 s | 0.211 s | 0.156 s | Roughly 2x slower than Tesseract, moderate spread |
| PaddleOCR | 0.282 s | 0.660 s | 0.370 s | Slowest on average, and the only engine with a clear bimodal split (see below) |

PaddleOCR isn't just slower on average — it's slower in a specific, meaningful pattern. Eight of ten images cluster tightly between 0.282–0.332 s, but images 008 and 009 take 0.660 s and 0.608 s — roughly double. **Those are the exact same two images where PaddleOCR produced the stray `口` glyph and, in 009's case, the severe misread.** That's not a coincidence worth ignoring: it suggests the extra time is going toward the model doing more internal work when it's uncertain (e.g. re-scoring candidate regions, running de-orientation/detection passes that a clean, unambiguous crop wouldn't trigger), which means processing time itself is a usable weak signal for "this result might be wrong" — worth considering as a downstream confidence proxy alongside PaddleOCR's own reported confidence scores if that's exposed.

## 4. Per-image detail

Ground truth values: 3.8, 7.4, 9.5, 11.4, 10.0, 1.3, 1.4, 0.0, 9.0, 9.7 (all decimal-valued — no integer-only readings in this set, see coverage note in §5).

| Image | Truth | EasyOCR | Tesseract | PaddleOCR |
|---|---|---|---|---|
| 001 | 3.8 | 38 (66.7%) | 37 (33.3%) | 3.8 (100%, exact) |
| 002 | 7.4 | 74 (66.7%) | – (0%) | 74 (66.7%) |
| 003 | 9.5 | 95 (66.7%) | 35 (33.3%) | 9.5 (100%, exact) |
| 004 | 11.4 | *(empty)* (0%) | – (0%) | 11.4 (100%, exact) |
| 005 | 10.0 | 10o (50%) | 0 (25%) | 10.0 (100%, exact) |
| 006 | 1.3 | 13 (66.7%) | *(empty)* (0%) | 1.3 (100%, exact) |
| 007 | 1.4 | *(empty)* (0%) | *(empty)* (0%) | 1.4 (100%, exact) |
| 008 | 0.0 | 80 (33.3%) | -. (33.3%) | 0.0 口 (33.3%) |
| 009 | 9.0 | *(empty)* (0%) | *(empty)* (0%) | 110 口 (0%) |
| 010 | 9.7 | 97 (66.7%) | *(empty)* (0%) | 97 (66.7%) |

---

## 5. Failure case analysis

**EasyOCR** — systematically strips the decimal point on every single reading (this alone accounts for its 0% exact-match score even where the digits themselves are correct on 6/10 images). Fails completely (empty output) on 3/10 images (004, 007, 009). One genuine misread rather than an omission: image 008 (`0.0` → `80`), which looks like a different failure mode than the decimal-dropping pattern — worth a closer look at that specific crop.

**Tesseract** — not viable for this input in its current configuration. 0/10 exact, 12.5% character accuracy, mostly empty or single-character garbage output (`-`, `-.`, blank). Consistent with the same conclusion already reached in the Week 3 preprocessing report: Tesseract's LSTM line recognizer isn't a good match for seven-segment glyph shapes.

**PaddleOCR** — best of the three by a wide margin, and the only engine that reliably preserves the decimal point. Two distinct failure patterns:
- A trailing `口` (CJK placeholder) glyph appended to 2/10 results (008, 009) — looks like a residual-uncertainty artifact rather than random noise, since it always appears *after* an otherwise-plausible reading rather than replacing digits. Both cases also took roughly 2x longer to process than a typical clean image (§3) — the timing anomaly and the output anomaly point at the same two images.
- One severe misread on image 009 (`9.0` → `110`) — this isn't a small digit confusion, it's reading a different shape entirely, which suggests something specific to that crop (angle, occlusion, contrast) rather than a general engine weakness. Worth inspecting that image directly.

---

## 6. Test dataset coverage — gap to flag

The objective specifies a test set spanning: clear display, low brightness, high brightness, noise, motion blur, different display angles, reflections, different digit values, and decimal values.

The current 10-image set was originally built for the object-detection stage (Week 5), not assembled as a controlled OCR test matrix, so actual coverage is uneven:

- **Covered:** different digit values (10 distinct readings) and decimal values (all 10 samples have a decimal point).
- **Present but not labeled/controlled:** the samples do vary naturally in ambient brightness and framing angle, since they're real factory photos — but there's no per-image record of which condition each one represents, so no per-condition breakdown is possible from this set as-is.
- **Not represented:** no images specifically captured for motion blur, reflections/glare, or deliberately extreme high/low brightness (over/under-exposed) as isolated variables.

Before this benchmark can claim to answer "how does each engine perform under X condition," the test set needs images captured (or at least tagged) per condition — right now the 60%/40.6%/12.5% figures describe performance on *these ten photos*, not a validated per-condition breakdown.

---

