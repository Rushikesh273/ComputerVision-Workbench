# Week 6 Documentation: Unified OCR Pipeline & Digit Detection

This week was about one practical goal: take a **cropped industrial digital-display image** and turn it into a reliable raw reading such as `"125.50"`. Along the way we had to understand *why* ordinary OCR engines struggle on seven-segment / LED / LCD panels, measure that struggle with real factory photos, and build an alternative that treats each digit as an object instead of a line of text.

---

## Monday – Understanding OCR and Why Displays Break It

OCR (Optical Character Recognition) converts pixels that look like text into a string a computer can use. Almost every modern engine splits the job in two:

- **Detection** — “Where is the text?”  
  A network proposes boxes or polygons around regions that look like writing.
- **Recognition** — “What does that region say?”  
  Another network reads the cropped region and emits characters.

Tesseract, EasyOCR and PaddleOCR all follow this broad pattern, but with different building blocks:

| Engine | Detection idea | Recognition idea | Typical strength |
|--------|----------------|------------------|------------------|
| **Tesseract** | Classical page/line layout analysis | LSTM sequence model over a whole line | Clean scanned documents |
| **EasyOCR** | CRAFT (character-level region + affinity maps) | CRNN (CNN + BiLSTM + CTC) | Scene text, many languages |
| **PaddleOCR** | DBNet (differentiable binarization) + orientation classifier | SVTR (visual transformer) + CTC | Fast, production-friendly |

None of these systems were trained primarily on **seven-segment** glyphs. A printed “8” is a continuous curved stroke; a seven-segment “8” is seven straight bars. Decimal points and minus signs are often single tiny segments. Under blur, flicker, glare, low contrast or slight rotation — everyday conditions on a factory floor — a general OCR engine can easily:

- Drop the decimal point (`12.50` → `1250`)
- Flip one digit into another that shares most segments (`8` ↔ `6`, `5` ↔ `6`)
- Miss the whole region because contrast is too low for the detector
- Read glare as an extra “on” segment

That research is captured in `ocr_research.md` and sets up the rest of the week: we cannot assume any single off-the-shelf engine will be enough.

---

## Tuesday – Making Three Engines Speak the Same Language

The practical next step was to install EasyOCR, Tesseract and PaddleOCR and give them a **common interface**. Every engine is wrapped so that the same call:

```text
run_ocr(path_to_cropped_image) → "raw string"
```

produces a comparable result. This made side-by-side testing painless and later let the unified pipeline switch methods with a single flag.

---

## Wednesday – Measuring Real Performance

We evaluated the three engines on **10 real factory crops** whose ground-truth readings were:

```text
3.8, 7.4, 9.5, 11.4, 10.0, 1.3, 1.4, 0.0, 9.0, 9.7
```

(all decimal-valued — no pure integers in this set).

Two accuracy numbers matter:

- **Exact match** — prediction must equal ground truth character-for-character (including the decimal point).
- **Character accuracy** — based on edit distance (Levenshtein), so dropping a decimal or inserting a stray glyph is penalised fairly even when lengths differ.

Summary of what we measured:

| Engine | Exact match | Character accuracy | Avg. time | Dominant failure |
|--------|-------------|--------------------|-----------|------------------|
| EasyOCR | 0% | ~41% | ~0.16 s | Almost always drops the decimal point; empty on several images |
| Tesseract | 0% | ~12% | ~0.11 s | Effectively unusable on these 7-segment crops |
| PaddleOCR | **60%** | **~78%** | ~0.37 s | Best of the three; rare junk glyph and one severe misread |

PaddleOCR was the only engine that consistently kept the decimal point. EasyOCR often got the *digits* right but still scored 0% exact match because it stripped the `.`. Tesseract rarely produced a usable string at all. Full tables and timing analysis live in `ocr_benchmark.md`.

---

## Thursday – Treating Digits as Objects (YOLO Path)

Because line-level OCR is brittle on this domain, we built the alternative the project called for: **detect every digit and symbol as its own object**, then reconstruct the reading.

Classes used in training:

```text
-   .   0   1   2   3   4   5   6   7   8   9   screen
```

The detector returns a set of boxes. Order is not guaranteed — YOLO may return `5`, then `1`, then `.`, then `2`… — so the decoder **sorts strictly by horizontal centre (x-coordinate)** from left to right. After sorting we:

- Drop the non-character class `screen`
- Merge near-duplicate overlapping boxes (keep highest confidence)
- Discard a minus sign that is not in the leading position
- Optionally refine classic 2 ↔ 5 confusion with a simple pixel-segment check
- Concatenate the remaining class names into the final string

This path is implemented as `digit_detector.py` + `digit_decoder.py` and is driven by the trained weights `digit_detection.pt`.

On the same 10 factory images, YOLO was dramatically faster after the first load (typically 12–55 ms) and often matched or beat PaddleOCR on clean readings. Its main recurring weakness was the same one that hurts general OCR: **occasionally missing the decimal point**, turning `9.5` into `95` or `1.3` into `13`.

---

## Friday – One Script, One Reading

Everything was brought together into a single pipeline:

```text
Cropped Display Image
          │
          ▼
    Preprocessing (optional)
          │
     ┌────┴─────┐
     │          │
     ▼          ▼
Standard OCR   YOLO Digit Detection
     │          │
     ▼          ▼
 Raw String   Sorted Digits
     │          │
     └────┬─────┘
          ▼
     Raw Reading
```

The entry point accepts a single image or a whole folder of crops and can run any one method or all of them. Output is always the raw string plus method name and processing time, for example:

```text
OCR Result: 3.8
Method: YOLO Digit Detection
Processing Time: 42 ms
```

A light optional preprocess (CLAHE contrast + bilateral filter) is available for crops that suffer from glare or low contrast. Raw engine output is also cleaned so only the characters `0-9`, `.` and `-` remain — this removes occasional junk glyphs that PaddleOCR sometimes appended.

---

## Final Comparison (All Four Approaches)

| Method | Accuracy on this set | Speed | Strength | Weakness |
|--------|----------------------|-------|----------|----------|
| **EasyOCR** | Medium digits, low exact match | Slow | Easy to try, no custom training | Drops decimals systematically |
| **Tesseract** | Very low | Fast | Lightweight | Poor match for seven-segment shapes |
| **PaddleOCR** | **Best overall** | Medium | Keeps decimals; strongest general engine here | Heavier; rare junk / occasional severe misread |
| **YOLO Digit Detection** | High | **Fastest** | Domain-specific, stable order, very low latency | Still misses some decimals; needs trained weights |

**Practical recommendation:** use YOLO when speed and domain fit matter; keep PaddleOCR as a strong fallback or ensemble partner when the YOLO string looks suspiciously integer-only on a display that should contain a decimal.

---

## Failure Cases We Actually Saw (and How the Pipeline Handles Them)

- **Decimal point missed** — most common remaining error for both EasyOCR and YOLO. The pipeline cannot invent a missing detection, but cleaning and future confidence-based re-checks can help.
- **Leading digit dropped** — thin leading `1`s are easy to under-detect; more varied training examples are the real fix.
- **Shape confusion (2 ↔ 5, 8 ↔ 3, etc.)** — partially addressed for 2/5 by a small pixel-segment refinement step in the decoder.
- **Reflections / glare read as extra digits** — mitigated by optional preprocessing and confidence thresholds.
- **Junk characters from general OCR** — stripped by a simple allow-list cleaner.
- **Empty or near-empty Tesseract output** — expected on this domain; the unified runner reports it cleanly instead of crashing.
- **Duplicate overlapping boxes** — merged by IoU + horizontal proximity, keeping the higher-confidence box.

---

## Key Takeaways

1. General-purpose OCR assumes continuous strokes and document-like text. Seven-segment industrial displays violate that assumption in everyday factory conditions.
2. Among off-the-shelf engines, **PaddleOCR** is clearly the strongest on our crops and is the only one that reliably preserves decimal points.
3. A **purpose-trained YOLO digit detector** is both accurate and much faster once loaded; sorting by X-coordinate and light post-processing turn raw boxes into a usable reading.
4. The hardest remaining shared problem is the **tiny decimal point** — easy to lose under blur, low contrast or marginal confidence.
5. One unified script now turns any cropped display into a raw string and lets us compare every approach on the same images in a single run.

Week 6 therefore closes the loop from “why OCR fails on these displays” to a working, measurable, multi-method pipeline that produces the raw reading the rest of the system needs.
