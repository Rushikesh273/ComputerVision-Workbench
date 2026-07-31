# Computer Vision with YOLO and OCR

## Project Objective

This project explores the fundamentals of Computer Vision through practical implementations of YOLO (You Only Look Once) and Optical Character Recognition (OCR). The objective is to understand how object detection and text recognition work by building and experimenting with real-world applications — specifically, reading digital displays (weighing scales, temperature, and pressure gauges) from camera footage.

## Project Structure

` ` `text ComputerVision-Workbench/
├── config/                          # project configuration files
├── data/
│   └── base_dataset/                # curated clean dataset of real display images
├── docs/                            # research notes and documentation
│   ├── Preprocessing_pipeline_Results.md
│   ├── Thresholding_Morphology_result.md
│   ├── architecture_diagram.png
│   ├── assumptions.md
│   ├── component_responsibilities.md
│   ├── cv_pipeline.md
│   ├── data_flow_diagram.png
│   ├── perspective_correction_documentation.md
│   ├── pipeline_components.md
│   ├── preprocessing_research.md
│   └── week2_documentation.md
├── models/                          # trained model weights (populated in later weeks)
├── src/                             # source code
│   ├── Preprocessing_pipeline.py    
│   ├── automation_pipeline.py       
│   ├── image_processing.py          
│   ├── morphology.py                
│   ├── perspective_correction.py    
│   ├── preprocessing_demo.py        
│   ├── synthetic_generator.py       
│   └── thresholding.py              
├── .gitignore
└── README.md
` ` `

## Week 1 Summary

| Day | Focus |
|---|---|
| **Mon** |Research on Computer Vision, YOLO, and OCR types. Created GitHub repository, defined project folder structure (src, docs, data, models, configs, etc.), initialized Git with .gitignore, README.md, and license. |
| **Tue** | Researched common challenges in industrial display detection (reflections, glare, low-contrast digits, motion blur, perspective distortion, display flickering). Set up Python development environment (virtual environment, installed dependencies, created requirements.txt).|
| **Wed** | Studied Computer Vision Pipeline & System Architecture. Documented pipeline stages, components, created high-level architecture diagram, data flow diagram, and component responsibility table. |
| **Thu** | Created detailed documentation files in docs/ folder: cv_pipeline.md, pipeline_components.md, architecture_diagram.png, data_flow_diagram.png, component_responsibilities.md, and assumptions.md.|
| **Fri** | Researched AI model training process, steps involved in training a model, and related concepts.|

## Week 2 Summary

| Day | Focus |
|---|---|
| **Mon** |Documented challenges (reflection, glare, blur, lighting, angles, contrast), and initial YOLO model exploration for carton boxes. |
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


