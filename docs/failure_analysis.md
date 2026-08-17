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

**Reading this:** Precision/Recall/mAP@50 are essentially saturated — on the val split, the model almost never misses the display and almost never invents one. mAP@50-95 (0.886) is meaningfully lower than mAP@50 (0.995), which is the expected pattern for this task: the model reliably finds the display (loose IoU ≥0.5 threshold), but box tightness varies more at stricter IoU thresholds (0.5→0.95). That gap is the quantitative signature of the edge-margin and multi-box behaviour documented in `failure_analysis.md`.

Training curve, at a glance:
- `train/box_loss` fell from 2.25 → 0.54 over 80 epochs, still trending down slightly at the end (more epochs likely helps localisation a bit further).
- `metrics/mAP50` reached ~0.995 by epoch 10 and stayed flat — classification/detection was solved early.
- `metrics/mAP50-95` kept oscillating between ~0.75 and ~0.89 through the back half of training rather than monotonically improving — consistent with box-tightness being the harder, still-noisy part of the objective, not the presence/absence of a detection.

## 3. ⚠️ Important scope note — this is not a Week 5 test-set number

The table above is Ultralytics' internal **val**-split metric from training time, not an independent **test**-split metric (`data/detection/images/test` + `data/detection/labels/test`) computed from scratch. Those are meant to be different data cuts.

At the time of writing, `data/detection/labels/test/` has no `.txt` label files — only unlabeled sample photos (the 10 `factory_image_*.jpg` files) are available. **No script in this repo currently computes Precision/Recall/mAP@50/mAP@50-95/IoU against a labeled test set** — `display_detector.py` and `crop_display.py` are both label-free by design (they're meant to run on new, unlabeled field photos). So instead of approximating test-set numbers, `docs/failure_analysis.md` covers what *can* be assessed without ground truth (confidence, qualitative crop quality via the `crop_display.py` contact sheet, heuristic failure flags), and this file reports what training already measured legitimately.

**Not yet done — flagged as a next step, not implemented:** once ground-truth boxes exist for `data/detection/images/test`, a proper quantitative evaluation script (Precision/Recall/mAP@50/mAP@50-95/IoU against those labels, e.g. via `model.val(data="data.yaml", split="test")`) still needs to be written. It doesn't exist yet in this repo.

## 4. Confidence on unseen sample images

Running `display_detector.py` on the 10 sample factory photos in `input/` (different units, lighting, framing, backgrounds — none used in training) gave:

| | |
|---|---|
| Images tested | 10 |
| Detections | 10/10 (no false negatives in this sample) |
| Confidence range | 0.763 – 0.854 |
| Mean confidence | 0.810 |
| Images below discard threshold (0.5) | 0 |
| Images below review threshold (0.65) | 0 (on the best/reported box) |

No image dropped below the review threshold on its primary detection, which is a good sign for the confidence side of generalisation. See `failure_analysis.md` for the localisation-quality issues (edge-touching boxes, multi-box detections) found on this same sample — this is exactly where the mAP@50 vs mAP@50-95 gap above shows up in practice.

## 5. Model finalisation

Only one trained candidate exists at this point (`display_detector.pt`, epoch auto-selected by Ultralytics' best-fitness checkpointing during the 80-epoch run — fitness = mAP@50-95 = 0.886). It currently sits alongside `display_detector.py` and `crop_display.py` and is loaded via the local `MODEL_PATH = "best.pt"` setting in `display_detector.py`.

**Not yet done:** moving it into a dedicated `models/display_detector.pt` path (and updating `MODEL_PATH` in both scripts to point there) is a pending repo-layout cleanup, not something already reflected in the current scripts.

If a second training run (e.g. more epochs, added augmentation for perspective/blur, or a bigger dataset) is done later, re-run this comparison and update this table before swapping the model file.

## 6. Reproduction

```bash
# Run detection + crop + heuristic QA flags on everything in input/
python display_detector.py

# Build a single contact-sheet image from output/*_crop.jpg for fast manual review
python crop_display.py
```

Both scripts are flat (no CLI subcommands/flags) — settings like `MODEL_PATH`, `INPUT_DIR`, `OUTPUT_DIR`, and the flag thresholds are constants at the top of each file.
