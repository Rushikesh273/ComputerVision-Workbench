# Documentation: Thresholding & Morphology for Display Region Extraction

## Objective Recap
Separate a display's digit segments (foreground) from everything else in the frame (background), using thresholding, then clean up the result using morphological operations.

## Method
Both scripts were tested against 3 real sample images from this project's own dataset:
- `sample_clean.jpg` — a **tight crop**, already containing mostly just the display (100×190px)
- `sample_low_contrast.jpg` — a **wide scene shot** (640×640px), display is small within a larger dim background
- `sample_uneven_lighting.jpg` — a **wide scene shot** (640×640px), display is small within a larger, unevenly lit background

This mix was deliberate — it turned out to be the single most important factor in the results (see finding below).

---

## Part 1: Thresholding Results

| Sample | Global | Adaptive Mean | Adaptive Gaussian | Otsu |
|---|---|---|---|---|
| sample_clean (tight crop) | 33.9% white | 57.6% white | 61.3% white | **46.7% white** |
| sample_low_contrast (wide scene) | 0.0% white | 92.1% white | 96.0% white | 86.5% white |
| sample_uneven_lighting (wide scene) | 84.9% white | 84.2% white | 88.1% white | 66.8% white |

*(% white = percentage of the image classified as "foreground" — for a seven-segment display, the real digit area should be a small fraction of the frame, so a very high percentage signals the threshold is picking up background, not just the digits.)*

### The main finding — and it wasn't the expected one

The initial assumption going in was that Otsu or Adaptive Gaussian would simply "win" as the best technique. The actual results show something more important: **which image type (tight crop vs. wide scene) mattered far more than which thresholding technique was used.**

- On the **tight-crop image**, Otsu gave the most plausible result (46.7% — consistent with roughly half the small frame being bright digit segments against a dark bezel).
- On **both wide-scene images**, every single technique — including Otsu and the adaptive methods — classified 66–96% of the frame as "foreground." That's not a usable digit extraction; it means the background wall was being classified as foreground almost as often as the actual display.

**Why:** on a wide-scene shot, the display is a small object within a much larger background. Thresholding — even adaptive thresholding — makes its decision based on *brightness*, not *location*. It has no concept of "the display is the interesting part here" — it just splits pixels into two brightness groups, and when the background itself varies in brightness (a wall isn't perfectly uniform), a large chunk of that background can end up on the "bright" side of the split right along with the digits.

**We also tested whether better preprocessing fixes this** (tying directly into the previous task): applying CLAHE contrast enhancement *before* Otsu thresholding on the low-contrast wide-scene image barely changed anything (86.5% → 89.6% — actually slightly worse). This confirms the problem isn't a lack of contrast — it's that thresholding has no way to know *where* the display is in a wide frame. Contrast enhancement can't fix a localization problem.

### Practical conclusion for this project

**Thresholding alone is not sufficient to extract the display region from a wide-scene camera shot.** This directly supports the two-stage pipeline design already decided on earlier in this project (Week 1 architecture): an **object detection step must run first** to locate and crop to the display's bounding box — only *after* that crop is thresholding actually able to cleanly separate the digit segments from the background, the same way it did on the already-cropped `sample_clean.jpg`.

### Which thresholding technique works best for seven-segment displays (once cropped to the display region)
Based on the tight-crop result: **Otsu Thresholding** is the best default choice. It automatically calculates the split point from the image's own histogram rather than requiring a manually guessed value (unlike Global Thresholding, which produced an unusable 0.0% on the low-contrast image — the fixed guess of 127 was simply wrong for that image's brightness range). The two Adaptive methods consistently classified *more* of the frame as foreground than Otsu across every sample, suggesting they're more prone to picking up noise/background texture at the block level — reasonable behavior for their intended use case (documents with uneven local lighting) but not the tightest fit here, where the goal is isolating a compact, high-contrast digit shape against a comparatively uniform dark bezel.

---

## Part 2: Morphological Operations Results

All 5 operations were applied to the **Otsu-thresholded** binary output of each sample (Otsu chosen as the input since it was identified above as the strongest thresholding method).

| Operation | Effect observed (sample_clean: 8,871 white px baseline) | Behavior confirmed |
|---|---|---|
| Erosion | 7,322 px (-17%) | Shrinks white regions — confirmed, removes small specks but also thins real shapes |
| Dilation | 10,545 px (+19%) | Grows white regions — confirmed, fills small gaps but also merges/thickens shapes |
| Opening | 8,696 px (-2%) | Close to baseline — confirmed as gentler than raw erosion, removes noise without much shape loss |
| Closing | 9,012 px (+2%) | Close to baseline — confirmed as gentler than raw dilation, fills small gaps without much growth |
| Morphological Gradient | 3,223 px (-64%) | Dramatically reduced — confirmed, leaves only the outline/edges of the digit segments |

### Which morphological operation is most useful for seven-segment displays

**Closing** is the most broadly useful for this project's specific case: seven-segment digits are made of separate bar-shaped segments, and a slightly noisy or partially-broken threshold result can leave small gaps within what should be a solid segment. Closing fills those small gaps back in without significantly distorting the overall digit shape (only +2% growth observed) — which matters, since over-growing (like plain Dilation, +19%) risks merging adjacent digits or segments together, which would break a downstream OCR read.

**Opening** is the right choice specifically when the thresholded image has small stray white noise specks scattered in the background (common on the wide-scene, high-foreground-percentage results from Part 1) — it's the gentler cleanup pass for exactly that problem.

**Morphological Gradient** isn't intended as a cleanup step at all — it's useful separately, for visualizing or extracting just the digit outlines, e.g. as an input to a corner/edge-based technique rather than a filled-shape-based one.

---

## Summary

1. **The image type (already cropped vs. wide scene) had a bigger effect on thresholding quality than the choice of thresholding technique.** This is the key finding, and it means the real fix for reliable display extraction is a detection/cropping step before thresholding, not a "better" thresholding algorithm.
2. **Otsu Thresholding** is the recommended default technique for seven-segment displays, once the image is already cropped to the display region.
3. **Closing** is the recommended default morphological cleanup step, to reconnect small gaps in digit segments without over-growing and risking merged/unreadable digits.
