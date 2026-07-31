# 7-Segment Display Preprocessing Pipeline — Test Results

**Project:** Preprocessing Pipeline for 7-Segment LED/LCD Displays  
**Goal:** Produce solid black digits on white background (digits only), ready for OCR  
**Date:** 31 July 2026  

---

## 1. Overview

The pipeline processes photos of 7-segment displays through these stages:

1. Resize  
2. Numbers ROI extraction  
3. Grayscale  
4. Noise reduction  
5. Contrast enhancement  
6. Thresholding + polarity detection  
7. Morphological operations  
8. Connected-component cleaning + OCR prep  

**Target output:** black digits on white, no frame, no background noise.

---

## 2. Success Criteria

A sample is counted as a **success** when all of the following are true:

- Digits are black on a white background  
- All expected digits are present and readable  
- Digits are not merged into one blob  
- No display frame or heavy background noise remains  
- The image is suitable for seven-segment OCR (e.g. ssocr)

Anything that fails polarity (white on black), keeps a black frame, or loses digits is a **failure**.

---

## 3. Test Results Summary

Twenty sample outputs were reviewed visually against the success criteria above.

**Overall score**

- Success: **14 out of 20 (70%)**  
- Failure: **6 out of 20 (30%)**

**Success samples**
(Image file name → Digits in image)
- 0010_9562 → 9562  
- 0022_7485 → 7485  
- 0027_2045 → 2045  
- 0029_4088 → 4088  
- 0032_2664 → 2664  
- 0043_2949 → 2949  
- 0059_8213 → 8213  
- 0072_6224 → 6224  
- 0103_9408 → 9408  
- 0116_6149 → 6149  
- 0140_4957 → 4957  
- 0149_4222 → 4222  
- 0176_7659 → 7659  
- 0205_2604 → 2604 (minor streak above the digits; still counted as success)

**Failure samples**

- 0060_4272 → 4272 (white digits on black frame)  
- 0105_6784 → 6784 (white digits on black frame)  
- 0127_1791 → 1791 (white digits on black frame)  
- 0137_3513 → 3513 (white digits on black frame)  
- 0145_8355 → 8355 (white digits on black frame)  
- 0193_4800 → 4800 (white digits on black frame)  

---

## 4. Success Cases

These outputs meet the pipeline goal: solid black digits, white background, no frame.

**0010_9562** — Clean, separable digits.  
**0022_7485** — Clean, separable digits.  
**0027_2045** — Clean, separable digits.  
**0029_4088** — Clean, separable digits.  
**0032_2664** — Clean, separable digits.  
**0043_2949** — Clean, separable digits.  
**0059_8213** — Clean, separable digits.  
**0072_6224** — Clean, separable digits; strong reference example of the target output.  
**0103_9408** — Clean, separable digits.  
**0116_6149** — Clean, separable digits.  
**0140_4957** — Clean, separable digits.  
**0149_4222** — Clean, separable digits.  
**0176_7659** — Clean, separable digits.  
**0205_2604** — Digits correct and black on white; a thin streak remains above the `2` (minor noise only).

---

## 5. Failure Cases

### Case A — Wrong polarity (white on black + frame)

**Samples:** 0060_4272, 0105_6784, 0127_1791, 0137_3513, 0145_8355, 0193_4800  

**Symptom**  
Digits appear white on a black rectangular panel. The display bezel or frame is kept in the final image.

**Root cause**  
Stage 6 polarity detection treats the ROI as a bright background (LCD-style) and inverts incorrectly, or the threshold keeps the dark panel as foreground.

**Impact**  
Does not meet “black digits on white, digits only”. OCR may still work with inverted settings, but the pipeline target is not met.

**Status**  
Open  

**Suggested fix**  
Prefer a red-channel or red-mask path for LED samples before intensity-based polarity. Tighten corner and background sampling so dark LED panels are not classified as bright background.

---

### Case B — Minor leftover artifact

**Sample:** 0205_2604  

**Symptom**  
A thin diagonal or horizontal streak survives above the digits.

**Root cause**  
A bright reflection or bezel edge passes the Stage 8 area and height filters.

**Impact**  
Still counted as success for readability. May confuse OCR slightly (e.g. an extra character).

**Status**  
Open (low priority)  

**Suggested fix**  
Add an aspect-ratio filter in Stage 8 to reject long, thin, low-height components, or restrict components to the main digit-row vertical band.

---

## 6. Notes on Scoring Methodology

- **Visual pipeline quality** (this document): black-on-white, digits only, complete and separable.  
- **Generic Tesseract** is a poor scorer for seven-segment shapes and often fails on correct outputs. Prefer **ssocr** or a seven-segment-trained model for automated OCR accuracy.  
- The success rate above is **visual / preprocessing quality**, not OCR exact-match rate.

---

## 7. Priority Improvements

1. **Fix polarity for dark LED panels** (Case A) — largest failure group (6 of 20).  
2. **Aspect-ratio / streak filter in Stage 8** (Case B) — small change for cleaner success cases.  
3. **Horizontal padding / digit spacing** — if ssocr merges digits, increase horizontal-only ROI padding or add explicit digit splitting.  
4. **Decimal-point handling** — verify once decimal-bearing samples are available.  
5. **Perspective / deskew** — still needed for strongly angled real-world photos.

---

## 8. Conclusion

The pipeline produces correct, OCR-oriented output on about **70% of the tested samples** under visual success criteria.

The main remaining gap is **polarity and frame retention** on a subset of LED images (white-on-black with a black box). Fixing that should raise the success rate further without harming the cases that already work.

**Recommended next step:** Harden Stage 6 polarity (and optionally the Stage 8 aspect filter), then re-run the same set and update this report.
