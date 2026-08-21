# Digit Detection – Method Comparison & Failure Cases

## 1. Pipeline Overview

```
Cropped Display Image
          │
          ▼
    Preprocessing (optional)
          │
     ┌────┴─────┐
     │          │
     ▼          ▼
Standard OCR   YOLO Digit Detection
(EasyOCR /     (digit_detection.pt
 Tesseract /    → sort by x-center
 PaddleOCR)     → merge dups
     │          → fix minus / 2↔5)
     ▼          │
 Raw String     Sorted Digits
     │          │
     └────┬─────┘
          ▼
     Raw Reading
```

**Entry point:** `python ocr_pipeline.py`  
**Model:** `digit_detection.pt` (classes: `- . 0 1 2 3 4 5 6 7 8 9 screen`)

---

## 2. Method Comparison

Based on the 10 factory crop images run on 21 Aug 2026.

| Method                  | Accuracy (on this set) | Speed (after load) | Strength                                      | Weakness                                              |
|-------------------------|------------------------|--------------------|-----------------------------------------------|-------------------------------------------------------|
| **EasyOCR**             | Medium                 | Slow (100–6000 ms) | Works without custom training; sometimes gets clean integers | Crashes on some crops (fixed); often misses decimals; slow first load |
| **Tesseract**           | Low                    | Fast (110–520 ms)  | Lightweight; whitelist helps                  | Frequently empty or returns only `-` / `-.` on these LCD crops |
| **PaddleOCR**           | **Highest**            | Medium (260–4000 ms) | Best overall readings; keeps decimals well   | Slow first load; occasional junk characters (cleaned); larger dependency |
| **YOLO Digit Detection**| High                   | **Fastest** (12–55 ms) | Domain-specific; very fast after load; left-to-right order reliable | Sometimes drops decimal point (`9.5`→`95`, `1.3`→`13`); occasional missed leading digit |

### Per-image snapshot (key disagreements)

| Image | EasyOCR | Tesseract | PaddleOCR | YOLO | Likely truth |
|-------|---------|-----------|-----------|------|--------------|
| 001 | 38 | 37 | **3.8** | **3.8** | 3.8 |
| 002 | 74 | - | **74** | **74** | 74 |
| 003 | 95 | 35 | **9.5** | 95 | 9.5 (YOLO missed `.`) |
| 004 | empty | - | **11.4** | 1 | 11.4 |
| 005 | 10 | 0 | **10.0** | 1.0 | 10.0 or 1.0 |
| 006 | 13 | empty | **1.3** | 13 | 1.3 (YOLO missed `.`) |
| 007 | empty | empty | **1.4** | **1.4** | 1.4 |
| 008 | 80 | -. | **0.0** | 00 | 0.0 |
| 009 | empty | empty | **110** | 90 | uncertain |
| 010 | 9 | empty | **97** | **97** | 97 |

**Recommendation**
- Best accuracy → **PaddleOCR**
- Best speed + good accuracy → **YOLO Digit Detection**
- Production combo → run YOLO first; fall back to Paddle when confidence is low or decimal looks missing

---

## 3. Documented Failure Cases

| Failure Mode | Example from this run | Typical Cause | Which methods | Mitigation already in pipeline |
|--------------|----------------------|---------------|---------------|--------------------------------|
| **Decimal point missed** | YOLO: `9.5` → `95`, `1.3` → `13` | Small/faint dot; low conf or not detected | YOLO, EasyOCR, Tesseract | YOLO has `.` class; still drops it sometimes. Consider lowering conf threshold for `.` only |
| **8 detected as 3** (or similar shape confusion) | Not strongly observed in this batch | Partial occlusion / low contrast on 7-seg | Any | YOLO 2↔5 pixel refinement exists; extend if 8↔3 appears |
| **Two digits merged** | Not strongly observed | Insufficient spacing / blur | Standard OCR more than YOLO | YOLO per-digit boxes prevent most merges |
| **Digit in wrong order** | Not observed | Multi-line / layout assumptions | Standard OCR | YOLO sorts strictly by `x_center` |
| **Reflections as digits** | Possible on 008/009 | Glare on glass | All | `--preprocess` (CLAHE + bilateral); YOLO conf filter |
| **Low-confidence detection** | Partial readings (YOLO `1` on 004) | Blur, angle, low light | YOLO (silent), others empty | Decoder can flag low conf; currently not printed in final string |
| **Leading digit dropped** | YOLO `1` vs Paddle `11.4` | Detection miss on left side | YOLO | Check conf threshold / more training examples of leading 1 |
| **Junk characters** | Paddle previously returned `口` | Model hallucination | PaddleOCR | `clean_reading()` strips everything except `0-9 . -` |
| **Empty / only minus** | Tesseract often `-` or empty | Whitelist + poor contrast | Tesseract | Not primary method for this data |
| **Duplicate boxes** | Not observed in final strings | Overlapping detections | YOLO | `_merge_duplicates()` keeps highest conf |

### Notes on YOLO class mapping (from training `data.yaml`)

```yaml
names: ['-', '.', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'screen']
```

Pipeline mapping is correct:

```python
CLASS_TO_CHAR = {
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    ".": ".", "-": "-",
}
NON_CHAR_CLASSES = {"screen"}
```

---


