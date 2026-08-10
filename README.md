# Computer Vision

Practical exploration of **object detection** and **text recognition** for reading digital displays (weighing scales, temperature gauges, pressure gauges) from camera footage — extended with a **financial analytics module** that quantifies and monitors the cost of overfilling packaged product.

---

## Project Objective

Build and experiment with real-world computer vision pipelines that:

1. Detect digital displays in images (YOLO)
2. Preprocess challenging industrial imagery (glare, blur, perspective distortion, low contrast)
3. Extract and recognize 7-segment / digital characters (OCR)
4. Feed weight readings into a **material giveaway** cost model, monitored through an interactive dashboard

---

## Project Structure

```
ComputerVision-Workbench/
├── config/                                # Project configuration files
├── data/
│   └── base_dataset/                      # Curated clean real display images
├── docs/                                  # Research notes & documentation
│   ├── Preprocessing_pipeline_Results.md
│   ├── Thresholding_Morphology_result.md
│   ├── architecture_diagram.png
│   ├── assumptions.md                     # CV pipeline design assumptions
│   ├── component_responsibilities.md
│   ├── cv_pipeline.md
│   ├── data_flow_diagram.png
│   ├── financial_analytics.md             # Material giveaway formulas & examples
│   ├── perspective_correction_documentation.md
│   ├── pipeline_components.md
│   ├── preprocessing_research.md
│   └── week2_documentation.md
├── models/                                # Trained model weights (later weeks)
├── src/                                   # Source code
│   ├── Preprocessing_pipeline.py          # Unified modular OCR-prep pipeline
│   ├── automation_pipeline.py             # Batch generation + validation
│   ├── dashboard.py                       # Streamlit + Plotly giveaway dashboard
│   ├── data_processing.py                 # CSV → Weight Drift / Giveaway / Loss
│   ├── financial_calculator.py            # Core giveaway calculation functions
│   ├── image_processing.py                # Core OpenCV utilities
│   ├── morphology.py                      # Erosion, dilation, opening, closing
│   ├── perspective_correction.py          # Contour detection, ROI, deskew
│   ├── preprocessing_demo.py              # Demo / visualization of preprocessing steps
│   ├── synthetic_generator.py             # Single-image synthetic variations
│   ├── thresholding.py                    # Global / Adaptive / Otsu tests
│   └── weight_violation_checker.py        # Multi-engine OCR weight-violation checker
├── .gitignore
└── README.md
```

---

## Weekly Progress

### Week 1 — Foundations

| Day | Focus |
|-----|-------|
| Mon | Research on CV, YOLO, OCR. GitHub repo + folder structure + `.gitignore` + license |
| Tue | Industrial display challenges (glare, blur, low contrast, perspective). Python env + `requirements.txt` |
| Wed | CV pipeline & system architecture. High-level diagrams + component table |
| Thu | Detailed docs: pipeline stages, data flow, responsibilities, assumptions |
| Fri | Model training process research |

### Week 2 — Data Generation

| Day | Focus |
|-----|-------|
| Mon | Challenge documentation + initial YOLO exploration (carton boxes) |
| Tue | `image_processing.py` — resize, grayscale, brightness/contrast, blur & noise types |
| Wed | `synthetic_generator.py` — random combined augmentations (200 variations from one image) |
| Thu | `automation_pipeline.py` — folder-level batch generation with progress, logging, error handling |
| Fri | Scale-up to ~1,000-image synthetic dataset + validation + documentation |

### Week 3 — Preprocessing for OCR

| Day | Focus |
|-----|-------|
| Mon | Necessity of OCR preprocessing. Noise, shadows, motion blur + CLAHE / bilateral / Gaussian |
| Tue | `thresholding.py` + `morphology.py`. Otsu vs Adaptive; erosion/dilation for 7-segment isolation |
| Wed | `perspective_correction.py`. Contour detection → ROI extraction → deskew |
| Thu | `Preprocessing_pipeline.py`. Modular chain: Resize → Grayscale → Denoise → Contrast → Deskew → Threshold → Morphology |
| Fri | Validation on 20–30 distorted images. Dynamic aspect ratios / kernel sizes. Final Week 3 docs |

### Week 4 — Material Giveaway Financial Analytics

| Day | Focus |
|-----|-------|
| Mon | Material giveaway concept, key terms, and formulas. `financial_analytics.md` + assumptions document |
| Tue | `financial_calculator.py` — Weight Difference, % Difference, Giveaway, Cost per Packet, Daily/Monthly Loss |
| Wed | `data_processing.py` — batch-process a production CSV with Pandas, add Drift/Giveaway/Loss columns. `weight_violation_checker.py` — multi-engine OCR (Tesseract/EasyOCR/PaddleOCR/RapidOCR) weight-violation checker |
| Thu | `dashboard.py` — Streamlit + Plotly dashboard: summary cards, trend charts, Product/Date/Shift filters |
| Fri | Updated `dashboard.py` — column validation, invalid-input handling, and a built-in recalculation check so it works against real, larger datasets |

---

## Getting Started

### 1. Environment Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate Synthetic Dataset

```bash
python src/automation_pipeline.py \
  --input  data/input_images \
  --output data/synthetic_dataset \
  --total  1000
```

### 3. Run Preprocessing Pipeline (OCR Prep)

```bash
python src/Preprocessing_pipeline.py
```

> Place sample images in the configured input directory.
> The script writes step-by-step intermediate results and a final OCR-ready image.

You can also run the demo:

```bash
python src/preprocessing_demo.py
```

### 4. Run the Material Giveaway Pipeline

```bash
# Process a production CSV into Weight Drift / Giveaway / Loss
python src/data_processing.py

# Launch the interactive dashboard
streamlit run src/dashboard.py
```

> `data_processing.py` expects a CSV with `Timestamp, Product Name, Target Weight,
> Actual Weight, Cost per Kg` and writes a processed CSV with the added calculated
> columns. `dashboard.py` reads that processed CSV — place it in the same folder
> or update the path at the top of the script.

### 5. Run the OCR Weight-Violation Checker

```bash
python src/weight_violation_checker.py
```

> Reuses the Week 3 preprocessing chain (resize → perspective correction → threshold
> → morphology) ahead of OCR, and supports Tesseract, EasyOCR, PaddleOCR, and
> RapidOCR as interchangeable backends. Currently a standalone module — not yet
> wired into the giveaway calculator.

---

## Key Deliverables

| Deliverable | Description | Location |
|-------------|-------------|----------|
| **Base Dataset** | Curated clean display images | `data/base_dataset/` |
| **Augmentation Scripts** | Standalone OpenCV processing & batch pipelines | `src/image_processing.py`, `src/synthetic_generator.py`, `src/automation_pipeline.py` |
| **Preprocessing Modules** | Thresholding, morphology, perspective correction | `src/thresholding.py`, `src/morphology.py`, `src/perspective_correction.py` |
| **Unified Pipeline** | Modular OCR-prep chain (deskew / denoise / 7-segment isolation) | `src/Preprocessing_pipeline.py` |
| **Giveaway Calculation Engine** | Weight Drift, Giveaway, Cost per Packet, Daily/Monthly Loss | `src/financial_calculator.py` |
| **Batch Data Processing** | CSV → processed CSV with calculated columns | `src/data_processing.py` |
| **Interactive Dashboard** | Summary cards, trend charts, Product/Date/Shift filters | `src/dashboard.py` |
| **OCR Weight-Violation Checker** | Multi-engine OCR reading + threshold violation flagging | `src/weight_violation_checker.py` |
| **Documentation** | Architecture, challenges, results, technique evaluation, financial model | `docs/` |

---

## Challenges Addressed

- Reflections & glare on glossy displays
- Low-contrast / faded digits
- Motion blur & display flickering
- Perspective distortion & angled views
- Uneven lighting & shadows
- Noise and compression artifacts
- Overfill cost (material giveaway) going untracked at production volume

---

## Documentation Index

| File | Content |
|------|---------|
| `docs/cv_pipeline.md` | Overall computer vision pipeline |
| `docs/pipeline_components.md` | Component breakdown |
| `docs/component_responsibilities.md` | Responsibility matrix |
| `docs/assumptions.md` | CV pipeline design assumptions |
| `docs/preprocessing_research.md` | Noise, distortion & preprocessing research |
| `docs/perspective_correction_documentation.md` | Contour / ROI / deskew notes |
| `docs/Thresholding_Morphology_result.md` | Thresholding & morphology experiments |
| `docs/Preprocessing_pipeline_Results.md` | End-to-end pipeline results |
| `docs/week2_documentation.md` | Week 2 data-generation notes |
| `docs/financial_analytics.md` | Material giveaway terms, formulas & worked examples |
| `docs/architecture_diagram.png` | System architecture diagram |
| `docs/data_flow_diagram.png` | Data flow diagram |

---

## Known Gaps / Next Steps

- `Assumptions_Document.docx` (the material giveaway assumptions) hasn't been committed to `docs/` yet.
- `data/synthetic_dataset/` (Week 2's ~1,000 generated images, `manifest.csv`, logs, validation report) isn't in the repo — only `data/base_dataset/` is.
- No sample production CSVs (e.g. `production_data.csv`, `production_data_processed.csv`) are committed under `data/`, so `data_processing.py` and `dashboard.py` can't be run against the repo as-is without supplying one.
- `Total Loss` has been defined inconsistently across data-processing runs (cumulative sum vs. per-row) — standardize on the per-row definition before adding more sample data, since that's what the dashboard's summary cards, charts, and verification check all assume.
- `weight_violation_checker.py`'s OCR readings are not yet connected to `financial_calculator.py` / `data_processing.py`.
