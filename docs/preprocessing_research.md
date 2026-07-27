# Preprocessing Research: Why Preprocessing Is Essential Before OCR

## 1. Why Preprocessing Matters

An OCR model doesn't "see" an image the way a person does — it was trained on a specific distribution of input: a certain contrast range, a certain sharpness, a certain lighting consistency. A raw camera frame almost never matches that distribution exactly. Preprocessing is the step that closes that gap — cleaning, standardizing, and correcting a raw image *before* it reaches the OCR model, so the model is reading something closer to what it was actually trained to expect.

This matters for two concrete reasons, both directly relevant to this project's displays:

1. **Garbage in, garbage out.** If a display is dim, noisy, or unevenly lit, the OCR model isn't failing because it's a bad model — it's failing because the input genuinely doesn't contain clean, legible digit shapes. No amount of model quality fixes a problem that exists in the input data itself.
2. **Consistency across conditions.** A camera watching an industrial display sees it under changing light, at different times of day, with different amounts of dust/reflection over time. Preprocessing is what makes a 9am reading and a 9pm reading of the *same* display look similar enough that one model can read both reliably.

## 2. Common Image Quality Issues

### Noise
Random pixel-level variation that doesn't represent real image content — a grainy, speckled texture, usually from a camera sensor working in low light and amplifying a weak signal. Noise adds false detail that can confuse edge-based digit detection.

### Uneven Lighting
Different parts of the same image are lit to different degrees — one side of a display bright, the other dim, or a gradient across the frame. Unlike overall darkness, this can't be fixed by a single global brightness adjustment, since "correct" brightness is different in different regions of the same image.

### Shadows
A specific, localized case of uneven lighting — a hard-edged dark region cast by something blocking the light source (a cable, a mounting bracket, a person's arm reaching into frame). Shadows are harder to correct than general uneven lighting because the transition can be sharp rather than gradual.

### Motion Blur
Directional smearing caused by the camera or the display moving during capture — documented at length in this project's earlier challenges research, particularly relevant to displays mounted on or near vibrating equipment (e.g. the ammonia pressure gauge on a compressor).

### Low Contrast
Digits that don't stand out clearly enough from their background — either because the display technology is naturally low-contrast (aging LCDs), or because of environmental dulling (dust, fading). Also documented in this project's earlier work.

### Perspective Distortion
The display appears skewed or trapezoidal because the camera isn't viewing it straight-on — also previously documented, and the reason a rectangular display can skew into a trapezoid while a circular dial skews into an oval instead.

## 3. Preprocessing Techniques Overview

Six techniques were studied and tested (see `technique_selection_guide.md` for the detailed "when to use which" breakdown, backed by measurements on real sample images):

Grayscale Conversion (Format): Converts the image to grayscale by retaining only intensity information. This is the standard first preprocessing step for many image processing tasks.
Histogram Equalization (Contrast Enhancement): Improves the overall (global) contrast of an image by redistributing pixel intensity values across the full range.
CLAHE (Contrast Limited Adaptive Histogram Equalization) (Contrast Enhancement): Enhances local contrast within small image regions while preventing excessive amplification of noise.
Gaussian Blur (Smoothing): Reduces general image noise and fine-grained texture by applying a Gaussian filter.
Median Blur (Smoothing): Removes salt-and-pepper (impulse) noise while preserving edges more effectively than Gaussian blur.
Bilateral Filter (Edge-Preserving Smoothing): Reduces noise while maintaining sharp edges by considering both spatial proximity and pixel intensity differences.

## 4. Method

Each technique was applied individually (not chained together) to 4 real sample images from this project's own dataset, deliberately chosen to represent different real problems rather than testing only on a clean baseline:

- `sample_clean.jpg` — a legible, well-lit baseline for comparison
- `sample_low_contrast.jpg` — a genuinely dim, hard-to-read display
- `sample_motion_blur.jpg` — a display with visible directional smearing
- `sample_uneven_lighting.jpg` — a display with an inconsistent lighting gradient across the frame

Outputs for every technique on every sample are saved under `outputs/<sample_name>/`, numbered in the order they appear in this document, so results can be compared side by side against the original.
