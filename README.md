# Computer Vision with YOLO and OCR

## Project Objective

This project explores the fundamentals of Computer Vision through practical implementations of YOLO (You Only Look Once) and Optical Character Recognition (OCR). The objective is to understand how object detection and text recognition work by building and experimenting with real-world applications — specifically, reading digital displays (weighing scales, temperature, and pressure gauges) from camera footage.

## Project Structure

```
ComputerVision-Workbench/
├── config/                          # project configuration files
├── data/
│   ├── base_dataset/                # curated clean dataset of real display images
│   ├── input_images/                # source images for synthetic generation
│   └── synthetic_dataset/           # generated synthetic dataset (images + manifest + logs)
├── docs/                            # research notes and documentation
│   ├── weight_display_types.md
│   ├── weight_display_challenges.md
│   ├── cv_pipeline.md
│   ├── architecture_diagram.drawio / .png
│   └── week2_documentation.md
├── models/                          # trained model weights (populated in later weeks)
├── src/
│   ├── image_processing.py          # core OpenCV image manipulation functions
│   ├── synthetic_generator.py       # single-image synthetic variation generator
│   └── automation_pipeline.py       # final automated batch generation + validation pipeline
└── README.md
```

## Week 1 Summary

| Day | Focus |
|---|---|
| **Tue** | Computer vision pipeline theory, YOLO, OCR types (Simple/OMR/ICR/IWR), OpenCV, CNNs, repo setup |
| **Wed** | Python environment setup (venv, dependencies, requirements.txt) |
| **Thu** | Documented real-world display-reading challenges: reflections, glare, low-contrast digits, motion blur, perspective distortion, display flickering |
| **Fri** | Pipeline component documentation, high-level architecture diagram, model training research |

## Week 2 Summary

| Day | Focus |
|---|---|
| **Mon** | Base dataset collection — 150 clean sample images of weight displays, organized dataset folder structure |
| **Tue** | `image_processing.py` — individual OpenCV functions (resize, grayscale, brightness, contrast, blur types, noise types), tested against multiple real sample images |
| **Wed** | `synthetic_generator.py` — random combined augmentation pipeline, 200 synthetic variations from a single source image |
| **Thu** | `automation_pipeline.py` — automated the process across an entire folder, with graceful handling of corrupted/invalid files, live progress display, and logging |
| **Fri** | Final review, refactor, and scale-up: ~1,000-image synthetic dataset with full post-generation validation (duplicates, naming, folder structure), documentation, and README update |

## Getting Started

### 1. Set up the environment
```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate the synthetic dataset
```bash
python src/automation_pipeline.py --input data/input_images --output data/synthetic_dataset --total 1000
```

See `docs/week2_documentation.md` for full details on the augmentation techniques used, all script options, and the validation checks performed on every run.

## Key Deliverables

- **Base dataset**: 150 curated clean display images (`data/base_dataset/`)
- **Synthetic dataset**: 1,000 generated variations with full manifest, logs, and validation report (`data/synthetic_dataset/`)
- **Scripts**: standalone, documented, individually-tested OpenCV processing functions (`src/`)
- **Documentation**: challenge research, pipeline architecture, and technique documentation (`docs/`)

## Contributors

See repository contributors.
