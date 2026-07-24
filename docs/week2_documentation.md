# Week 2 Documentation: Synthetic Dataset Generation Pipeline

## 1. Augmentation Techniques Used

The pipeline randomly combines a subset (3–6 out of 8) of the following techniques for every generated image, each with randomized parameters, so no two outputs are identical.

| Technique | What it does | Parameter range | Relevant to |
|---|---|---|---|
| **Rotation** | Rotates the image ±5° around its center | -5° to +5° | Camera not mounted perfectly straight |
| **Scaling** | Scales the image 0.85x–1.15x, then crops/pads back to original size | x0.85 – x1.15 | Distance/zoom variation |
| **Perspective transform** | Nudges the 4 corners randomly to simulate an off-angle view | strength 0.02–0.08 | Camera not viewing the display straight-on |
| **Brightness** | Shifts every pixel's intensity up or down | -50 to +50 | Lighting variation |
| **Contrast** | Scales pixel intensities around their midpoint | alpha 0.6–1.6 | Faded LCD vs. oversaturated LED displays |
| **Gaussian blur** | Soft, natural blur | kernel size 3–9 | Slightly out-of-focus camera |
| **Motion blur** | Directional smear at a random angle | kernel size 9–21, angle 0–179° | Vibration from nearby machinery |
| **Gaussian noise** | Random grainy noise | sigma 10–35 | Low-light sensor noise |

Techniques are applied in a fixed sensible order regardless of which subset is chosen — **geometry first** (rotation, scaling, perspective), **then lighting** (brightness, contrast), **then degradation** (blur, noise) — because a real camera would already be positioned and focused before lighting and sensor noise affect the final image.

## 2. Script Execution Steps

### Requirements
```bash
pip install numpy opencv-python
```

### Basic run (defaults: 1000 images, seed 42)
```bash
python src/automation_pipeline.py
```

### Custom run
```bash
python src/automation_pipeline.py --input data/input_images --output data/synthetic_dataset --total 1000 --seed 42
```

### All available options
| Flag | Default | Description |
|---|---|---|
| `--input` | `data/input_images` | Folder containing source images |
| `--output` | `data/synthetic_dataset` | Folder to write generated images + reports into |
| `--total` | `1000` | Total number of images to generate (spread across all valid source images) |
| `--min-ops` | `3` | Minimum number of augmentations applied per image |
| `--max-ops` | `6` | Maximum number of augmentations applied per image |
| `--seed` | `42` | Random seed — same seed always produces the same dataset (reproducible) |

### What happens when you run it
1. **Discovery** — scans `--input` folder, sorts every file into valid / corrupted / non-image (nothing is processed yet at this stage)
2. **Generation** — for each valid source image, generates its share of the total (spread as evenly as possible), with a live progress bar
3. **Validation** — automatically re-checks the *output* folder for duplicate images, correct naming, and correct folder structure, and writes `validation_report.txt`

## 3. Folder Structure

```
ComputerVision-Workbench/
├── src/
│   └── automation_pipeline.py       # the final, refactored generation + validation script
│
├── data/
│   ├── input_images/                # source images (put your images here)
│   └── synthetic_dataset/           # OUTPUT — created automatically when the script runs
│       ├── images/                  # all generated images
│       │   └── <source_stem>_var###.jpg   (e.g. 1236_263_var047.jpg)
│       ├── manifest.csv             # one row per image: filename, source, exact augmentations applied
│       ├── pipeline_log.txt         # full timestamped log of the run
│       └── validation_report.txt    # results of the post-generation validation checks
│
└── docs/
    └── week2_documentation.md       # this file
```

### Naming convention
Every generated file follows `<source_image_name>_var<3-digit index>.jpg` — e.g. an image generated from `0722_6410.jpg` will be named `0722_6410_var000.jpg`, `0722_6410_var001.jpg`, etc. This makes every output traceable back to its exact source image just by reading the filename, without needing to open the manifest.

## 4. Validation Performed

Every run automatically validates its own output (not just trusts the generation logic) and writes the results to `validation_report.txt`:

1. **No duplicate images** — computes an MD5 hash of each image's actual pixel content (not filename) and confirms no two generated images are pixel-identical.
2. **Proper file naming** — checks every output filename against the expected `<source>_var###.jpg` pattern.
3. **Correct folder organization** — confirms `images/` exists, `manifest.csv` exists, and the images folder isn't empty.
4. **Image quality** — flags any near-blank or degenerate images (very low pixel variance), as a basic sanity check that generation actually produced usable content.

Latest run result: **1000/1000 images generated, 0 duplicates, 0 naming issues, structure check passed.**
