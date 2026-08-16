# Failure Analysis — Display Detector

## Method

`data/detection/labels/test/` currently has no ground-truth `.txt` files, so this pass is the label-free, heuristic evaluation the pipeline was built for — not a substitute for the Precision/Recall/mAP/IoU numbers in `training_results.md`, but the right tool for the "unseen images, no labels yet" situation described in the objective.

```bash
python src/display_detector.py infer --source data/detection/images/test
python src/crop_display.py --source data/detection/images/test   # + contact sheet for manual review
```

10 sample factory photos were used — different meter units, lighting, framing/position, and backgrounds. None were used in training.

## Results summary

| File | Reading | Confidence | Flag(s) |
|---|---|---|---|
| factory_image_001.jpg | 3.8 | 0.854 | OK |
| factory_image_002.jpg | 7.4 | 0.763 | Duplicate Detection (loose secondary box) |
| factory_image_003.jpg | 9.5 | 0.844 | OK |
| factory_image_004.jpg | 11.4 | 0.817 | Partial Detection |
| factory_image_005.jpg | 10.0 | 0.848 | OK |
| factory_image_006.jpg | 1.3 | 0.829 | Partial Detection |
| factory_image_007.jpg | 1.4 | 0.767 | Duplicate Detection + Partial Detection |
| factory_image_008.jpg | 0.0 | 0.809 | OK |
| factory_image_009.jpg | 9.0 | 0.769 | Partial Detection |
| factory_image_010.jpg | 9.7 | 0.805 | OK |

**5/10 clean, 5/10 flagged.** No false negatives, no discarded (sub-0.5-confidence) detections, no degenerate/empty crops in this sample.

## Failure categories found

### False Negative — none observed
All 10 images produced a usable detection. Sample size is small (10 images), so this isn't a guarantee against false negatives on more extreme conditions (e.g. heavy motion blur, very dark exposure) that weren't well represented in this batch — worth targeted testing once more field photos are available.

### False Positive vs. Duplicate Detection — 2 images (002, 007), and this needed re-labelling
Both images produced two overlapping boxes. Visually inspecting the contact sheet: in both cases, the second box isn't a spurious detection somewhere else in the frame — it's a **looser box around the same display**, driven by the light-coloured metal bezel that these two units share. The tighter, higher-confidence box (the one the pipeline keeps) correctly hugs the black LED unit; the looser one also grabs part of the silver mounting plate.

This is why `display_detector.py` was changed to distinguish the two cases by IoU between the candidate boxes, rather than lumping any `num_detections > 1` into "possible false positive":
- IoU between the two boxes ≥ 0.5 → **Duplicate Detection** (same object, informational — the best-confidence box is already the good one, so downstream cropping isn't affected)
- IoU < 0.5 → **Possible False Positive** (genuinely separate candidate elsewhere in frame — this is the case that actually needs review)

Neither 002 nor 007 hit the second case in this sample. Recommended follow-up: add a few more examples of the silver-bezel unit type to training data, and/or tighten NMS IoU during training, so the secondary box stops appearing at all rather than being merely flagged.

### Partial Detection — 4 images (004, 006, 007, 009), but only 1 is a real problem
This flag fires when the box sits close to the image border. On manual review of the actual crops:
- **004** is a genuine partial detection — the photo frames the meter tight against its right edge, and a small icon on the right side of the display is visibly clipped in the crop.
- **006, 007, 009** are false alarms — the crops are visually complete; the box is simply close to the border because the source photo itself is tightly framed around the meter, not because anything is cut off.

Root cause: the edge-margin check is a blunt proxy for "is content missing," and these images are small (100–114 px tall), so even a well-placed box sits within a few percent of the border just from natural framing. The fixed 5px margin from the original script has been changed to a **fraction of image size** (3%) rather than a constant pixel count, since these test images range from 175–283 px wide — a fixed px margin was inconsistent across that range. This reduces but doesn't eliminate the false-alarm rate; it remains a soft, review-me flag rather than a hard failure. A more reliable fix would be to only hard-fail when the box coordinate touches the literal canvas edge (`x0 == 0` or `x1 == width`), and treat "close to the edge" purely as a prioritisation hint for manual review, not a defect count.

### Loose Bounding Box — related to, but distinct from, Duplicate Detection above
Area-ratio of crop to full frame ranged from 23.9% (008) to 60.0% (006) — a wide spread, expected given the photos aren't all taken from the same distance. Visually, 005, 006, and 007 include a bit more surrounding bezel/button-panel than strictly necessary, without being wrong — the LED digits are always fully inside the crop with margin to spare. This isn't currently flagged automatically (it's a matter of degree, not a clear pass/fail line), which is why `crop_display.py`'s contact sheet exists — task 3 ("is unnecessary background included") is inherently a visual judgement call, not one to force into a heuristic threshold.

### Low Confidence — none on the reported (best) box
Every image's top detection stayed above the 0.65 review threshold (range 0.763–0.854). The only sub-threshold confidences seen were on the *secondary* duplicate boxes in 002/007 (0.424, 0.499), which are discarded anyway since only the best box per image is used downstream.

### Incorrect Crop — none observed
No degenerate (zero-area) or suspiciously-small (<2% of frame) boxes in this sample.

## Does the crop work for the Week 3 preprocessing pipeline?

Crops range roughly **121×42 px to 169×64 px**. That's small — worth explicitly checking against whatever the Week 3 preprocessing step needs as a minimum input resolution (e.g. if it does digit OCR/segmentation), and adding an upscaling step beforehand if not. This wasn't verified here since the Week 3 pipeline code isn't in scope of this pass.

## Summary table (objective's required categories)

| Category | Observed? | Count | Root cause | Action |
|---|---|---|---|---|
| False Positive | No (in this sample) | 0 | — | Keep monitoring; IoU-based split from Duplicate Detection now isolates true FPs if they occur |
| False Negative | No | 0 | — | Retest on harder conditions (heavy blur/low light) when available |
| Partial Detection | Yes | 4 (1 genuine, 3 false-alarm) | Fixed-px edge margin too sensitive for small/tightly-framed images | Switched to % of frame; consider hard-fail only at literal edge (0 / width) |
| Loose Bounding Box | Yes (mild) | ~3 | Natural variation in photo distance; bezel ambiguity | No auto-fix; use contact sheet for manual QC per batch |
| Low Confidence | No (on best box) | 0 | — | None needed |
| Incorrect Crop | No | 0 | — | None needed |
| Duplicate Detection (new category) | Yes | 2 | Light-coloured bezel creates two plausible box interpretations | Add bezel-type examples to training data; tighten NMS |

## Next steps

1. Label `data/detection/images/test/` (or a larger held-out set) so `evaluate` mode can report real Precision/Recall/mAP/IoU instead of the training-time val numbers.
2. Add a handful of training examples of the light/silver-bezel unit type to reduce the duplicate-box behaviour at the source rather than filtering it downstream.
3. Confirm minimum crop resolution needed by the Week 3 preprocessing step and add upscaling if the ~120–170 px wide crops are too small.
4. Re-run this same `infer` + `crop_display` pass periodically as more field photos come in, since 10 images is a useful smoke test but not a statistically solid failure-rate estimate.
