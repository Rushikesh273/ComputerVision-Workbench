# Week 2 Documentation: Synthetic Dataset Generation Pipeline

This week we built a complete synthetic data generation system for industrial digital weight display images. The goal was to create a large, diverse, and realistic dataset for computer vision tasks.

## Work Completed This Week
- Trained an YOLO11m model using a dataset of 9000+ images with 150 epochs and patience of 30 
- Collected and organized base dataset of 150+ clean weight display images.
- Documented common real-world challenges (reflections, glare, low-contrast digits, motion blur, perspective distortion, lighting variations, etc.).
- Created `image_processing.py` with reusable OpenCV functions (resize, grayscale, brightness, contrast, blur types, noise types).
- Developed `synthetic_generator.py` for random combined augmentations.
- Built `automation_pipeline.py` — the main automated pipeline with error handling, progress tracking, and logging.
- Scaled the dataset up to ~1,000 synthetic images.
- Added full post-generation validation and updated project documentation.

## Augmentation Techniques

The pipeline randomly combines 3–6 techniques per image with randomized parameters:

| Technique                | What it does                              | Parameter Range                  | Real-world Relevance |
|--------------------------|-------------------------------------------|----------------------------------|----------------------|
| Rotation                 | Rotates image                             | -5° to +5°                       | Camera misalignment |
| Scaling                  | Zoom variation                            | 0.85x – 1.15x                    | Distance variation |
| Perspective Transform    | Simulates off-angle view                  | strength 0.02–0.08               | Camera angle |
| Brightness               | Lighting adjustment                       | -50 to +50                       | Lighting changes |
| Contrast                 | Contrast adjustment                       | 0.6 – 1.6                        | Display fading |
| Gaussian Blur            | Soft natural blur                         | kernel size 3–9                  | Out of focus |
| Motion Blur              | Directional smear                         | kernel 9–21, angle 0–179°        | Vibration |
| Gaussian Noise           | Random grainy noise                       | sigma 10–35                      | Sensor noise |

**Order**: Geometry → Lighting → Degradation.

## Folder Structure
ComputerVision-Workbench/
├── data/
│   ├── base_dataset/                  # Original clean images
│   └── synthetic_dataset/             # Auto-generated output
│       ├── images/                    # Generated images
│       ├── manifest.csv               # Augmentation log
│       ├── pipeline_log.txt
│       └── validation_report.txt
│
├── src/
│   ├── image_processing.py
│   ├── synthetic_generator.py
│   └── automation_pipeline.py
│
├── docs/
│   └── week2_documentation.md
│
├── models/
├── config/
├── requirements.txt
├── README.md
└── .gitignore
