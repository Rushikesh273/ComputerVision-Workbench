# Training Results — Display Detector

## 1. Setup

| | |
|---|---|
| Base model | YOLOv8n (`yolov8n.pt`, pretrained) |
| Task | Single-class object detection — class `0: display` |
| Image size | 192×192 |
| Epochs | 80 (early-stop patience 30 — training ran the full 80 without triggering it) |
| Batch size | 8 |
| Optimizer | auto (SGD/AdamW selected by Ultralytics) |
| LR0 / LRF | 0.001 / 0.01 (cosine-free linear decay) |
| Augmentation | mosaic 1.0, fliplr 0.5, hsv-h/s/v 0.015/0.7/0.4, translate 0.1, scale 0.5 (no rotation, no perspective, no flipud) |
| Trained | 2026-08-12 |
| Framework | Ultralytics 8.4.118 |

This config and the metrics below are read directly out of the `best.pt` checkpoint's embedded training metadata (`train_args` / `train_metrics` / `train_results`), not retyped by hand.

## 2. Validation performance (best epoch, logged during training)

This is Ultralytics' own validation pass on the **val split held out during training** — it is the officially "best fitness" checkpoint that got saved as `best.pt`.

| Metric | Value |
|---|---|
| Precision | **0.997** |
| Recall | **1.000** |
| mAP@50 | **0.995** |
| mAP@50-95 | **0.886** |
| val box loss | 0.571 |
| val cls loss | 0.415 |
| val dfl loss | 0.880 |

**Reading this:** Precision/Recall/mAP@50 are essentially saturated — on the val split, the model almost never misses the display and almost never invents one. mAP@50-95 (0.886) is meaningfully lower than mAP@50 (0.995), which is the expected pattern for this task: the model reliably finds the display (loose IoU ≥0.5 threshold), but the box tightness varies more at stricter IoU thresholds (0.5→0.95). That gap is the quantitative signature of the loose/duplicate-box behaviour documented in `failure_analysis.md`.

Training curve, at a glance:
- `train/box_loss` fell from 2.25 → 0.54 over 80 epochs, still trending down slightly at the end (more epochs likely helps localisation a bit further).
- `metrics/mAP50` reached ~0.995 by epoch 10 and stayed flat — classification/detection was solved early.
- `metrics/mAP50-95` kept oscillating between ~0.75 and ~0.89 through the back half of training rather than monotonically improving — consistent with box-tightness being the harder, still-noisy part of the objective, not the presence/absence of a detection.

## 3. ⚠️ Important scope note — this is not the Week 5 test-set number

The table above is Ultralytics' internal **val** split metric from training time, not the independent **test** split called for in the Week 5 objective (`data/detection/images/test` + `data/detection/labels/test`). Those are meant to be different data cuts.

At the time of writing, `data/detection/labels/test/` has no `.txt` label files — only unlabeled sample photos (the 10 `factory_image_*.jpg` files) were available, so Precision / Recall / mAP@50 / mAP@50-95 / IoU **cannot be honestly computed on a true held-out test set yet**. Rather than approximate or infer numbers from the unlabeled photos, `docs/failure_analysis.md` covers what *can* be assessed without ground truth (confidence, qualitative crop quality, heuristic failure flags), and this file reports what training already measured legitimately.

To close the loop once ground-truth boxes exist for the test images:

```bash
python src/display_detector.py evaluate --split test
```

This runs Ultralytics' official validation against `data/detection/images/test` + `labels/test` (via `data.yaml`) for Precision/Recall/mAP@50/mAP@50-95, **and** a separate transparent per-image pass that computes IoU and confidence against each label file directly (`runs/detection/evaluate/test_metrics_per_image.csv` + `test_metrics_summary.json`). If labels are missing, the script now says so explicitly instead of silently reporting `0.0` (Ultralytics' default behaviour, which otherwise looks exactly like a broken model).

## 4. Confidence on unseen sample images

Running `infer` on the 10 sample factory photos (different units, lighting, framing, backgrounds — none used in training) gave:

| | |
|---|---|
| Images tested | 10 |
| Detections | 10/10 (no false negatives in this sample) |
| Confidence range | 0.763 – 0.854 |
| Mean confidence | 0.810 |
| Images below discard threshold (0.5) | 0 |
| Images below review threshold (0.65) | 0 (on the best/reported box) |

No image dropped below the review threshold on its primary detection, which is a good sign for the confidence side of generalisation. See `failure_analysis.md` for the localisation-quality issues (edge-touching boxes, duplicate secondary boxes) found on this same sample — this is exactly where the mAP@50 vs mAP@50-95 gap above shows up in practice.

## 5. Model finalisation

Only one trained candidate exists at this point (`best.pt`, epoch auto-selected by Ultralytics' best-fitness checkpointing during the 80-epoch run — fitness = mAP@50-95 = 0.886). It has been copied into the repo as:

```
models/display_detector.pt
```

This is the finalised model referenced by both `src/display_detector.py` and `src/crop_display.py`. If a second training run (e.g. more epochs, added augmentation for perspective/blur, or a bigger dataset) is done later, re-run the comparison and update this table before swapping `models/display_detector.pt`.

## 6. Reproduction

```bash
# Qualitative pass on new/unlabeled images (crops + heuristic QA flags)
python src/display_detector.py infer --source data/detection/images/test

# Quantitative pass once data/detection/labels/test/*.txt exist
python src/display_detector.py evaluate --split test

# Crops + a single contact-sheet image for fast manual review
python src/crop_display.py --source data/detection/images/test
```
