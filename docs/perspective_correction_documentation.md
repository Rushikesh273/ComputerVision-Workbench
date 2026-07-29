# Documentation: Perspective Correction Pipeline

## Objective Recap
Correct camera angle distortion and isolate the display region, using classical computer vision (contours and geometry) rather than a trained model.

## The Transformation Process, Step by Step

### 1. Contour Detection
The image is converted to grayscale, blurred slightly (to reduce noise that would otherwise create tiny false edges), then run through Canny edge detection to find all outlines in the frame. A small dilation step closes tiny gaps in these outlines so they form continuous, connected shapes rather than broken fragments.

### 2. Largest Rectangle Detection
Every outline found is a candidate — most are irrelevant (shadows, table edges, reflections). Each contour is checked, largest-first, using `cv2.approxPolyDP`, which simplifies a wiggly outline down to its dominant corner points. The first contour that simplifies down to **exactly 4 points** and is a reasonable size is treated as the display's edge.

### 3. Corner Detection
The 4 points found aren't returned in a predictable order (top-left could come out anywhere in the list). They're sorted into a consistent order — top-left, top-right, bottom-right, bottom-left — using each point's coordinate sum and difference, which is what the perspective transform step needs to know which corner maps to which.

### 4. Perspective Transformation
With 4 ordered corners known, `cv2.getPerspectiveTransform` calculates the exact warp needed to map that (likely skewed/trapezoidal) quadrilateral onto a flat rectangle, and `cv2.warpPerspective` applies it. The output rectangle's size is calculated from the actual distances between the detected corners, so the result keeps a realistic aspect ratio instead of an arbitrary one.

### 5. Image Cropping / ROI Extraction
The warped result already *is* the cropped display — but the pipeline also includes a simpler, separate ROI extraction path (`cv2.boundingRect` + array slicing) used as a fallback when perspective transform isn't possible (see below).

## Honest Results on Real Images

Tested on 4 real photos from this project's own dataset — 2 from earlier CCTV/challenge documentation, 2 from the original weighing-scale photos.

| Sample | Method actually used | Output size |
|---|---|---|
| angled_display_1 | Bounding-box fallback | 64×139 |
| angled_display_2 | Bounding-box fallback | 65×140 |
| angled_scale_photo | **Full perspective transform** | 291×171 |
| angled_scale_photo2 | **Full perspective transform** | 481×69 |

**Only half the samples found a clean 4-cornered contour.** This wasn't hidden or worked around — it's the real, honest result of running classical contour detection on real photos, and it's worth understanding *why*, since it's a genuinely useful finding for this project.

### A bug found and fixed during testing
The first version of this script found a rectangle on only 1 of the 4 images. Investigating `angled_scale_photo2` specifically: the code was stopping its search as soon as it hit *any* contour below a minimum size — but a large, irrelevant contour (a shadow, at ~1.9% of the frame) happened to sit right above a genuinely rectangular one (the actual display, at ~1.6%). The search was ending before it ever reached the real match. Fixing this (checking all top candidates instead of stopping early) raised the success rate to 2 of 4 and is a good reminder that "the biggest shape in the image" and "the shape we actually want" are not the same thing.

### Why the other 2 still fall back
Checking `angled_display_1`'s actual contours directly: its top candidates simplified down to **7–14 corner points**, never exactly 4. This happens when the display's real edge isn't a clean sharp rectangle in the photo — a curved/rounded plastic bezel, a reflection breaking up part of the boundary, or JPEG compression noise along the edge all produce a jagged outline that `approxPolyDP` can't cleanly simplify to 4 points. In these cases, the fallback (a simple bounding-box crop, no angle correction) still produces a usable crop — just without straightening the angle.

## Practical Conclusion

This is the same conclusion this project's thresholding research reached, now confirmed again from a different angle: **classical, rule-based computer vision (contours, corner-counting) is a real and useful technique, but it is not fully reliable on messy real-world photos.** It works well when the display's edge is genuinely clean and rectangular, and degrades gracefully (via the bounding-box fallback) rather than failing outright when it isn't — but roughly half of this small real test set didn't get the full angle correction.

For production reliability, this reinforces the case (again) for the two-stage detector + OCR pipeline decided on earlier in the project: a trained object detection model can learn to find a display's boundary even when its edge is rounded, partially reflective, or otherwise not a textbook rectangle — something a fixed geometric rule fundamentally cannot adapt to.

## Fallback Behavior Summary

| Situation | What happens |
|---|---|
| A clean 4-cornered contour is found | Full perspective correction — angle is straightened |
| No 4-cornered contour, but a large contour exists | Bounding-box crop only — no angle correction, but still usable |
| No contours at all | Original image returned unchanged (should not normally occur) |

This graceful degradation was a deliberate design choice — a failed rectangle search should not mean the pipeline produces nothing.
