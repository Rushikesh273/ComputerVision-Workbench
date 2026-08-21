#!/usr/bin/env python3
"""
ocr_pipeline.py
===============
Unified OCR pipeline for cropped digital-display images.

Folder layout:
  OCR_pipeline/
  ├── ocr_pipeline.py
  ├── digit_detection.pt
  ├── input/
  └── output/

Usage:
  python ocr_pipeline.py
  python ocr_pipeline.py --method yolo
  python ocr_pipeline.py --method all
  python ocr_pipeline.py --image input/factory_image_001_crop.jpg --method yolo
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
YOLO_MODEL_PATH = ROOT / "digit_detection.pt"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def preprocess_image(image_path: str, out_path: str | None = None) -> str:
    try:
        import cv2
    except ImportError as e:
        raise RuntimeError("OpenCV (cv2) is required for --preprocess") from e

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.bilateralFilter(enhanced, d=5, sigmaColor=50, sigmaSpace=50)
    out = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)

    if out_path is None:
        out_path = str(Path(image_path).with_suffix(".preprocessed.png"))
    cv2.imwrite(out_path, out)
    return out_path


# ---------------------------------------------------------------------------
# Clean raw OCR text → keep only 0-9 . -
# ---------------------------------------------------------------------------

def clean_reading(text: str) -> str:
    """Strip everything except digits, one decimal point, and a leading minus."""
    if not text or text.startswith("[ERROR"):
        return text

    allowed = set("0123456789.-")
    cleaned = "".join(c for c in text if c in allowed)

    # keep only the first decimal point
    if cleaned.count(".") > 1:
        first = cleaned.find(".")
        cleaned = cleaned[: first + 1] + cleaned[first + 1 :].replace(".", "")

    # keep only a leading minus
    if "-" in cleaned:
        cleaned = "-" + cleaned.replace("-", "")

    return cleaned


# ---------------------------------------------------------------------------
# Standard OCR engines
# ---------------------------------------------------------------------------

def run_easyocr(image_path: str) -> str:
    import easyocr
    import cv2

    if not hasattr(run_easyocr, "_reader"):
        run_easyocr._reader = easyocr.Reader(["en"], gpu=False)

    # Load as BGR → RGB numpy array to avoid EasyOCR internal grayscale unpack bug
    img = cv2.imread(image_path)
    if img is None:
        return ""
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    results = run_easyocr._reader.readtext(img_rgb, detail=1)
    texts = []
    for item in results:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            texts.append(str(item[1]))
    return " ".join(texts).strip()


def run_tesseract(image_path: str) -> str:
    import pytesseract
    from PIL import Image

    tesseract_bin = shutil.which("tesseract")
    if tesseract_bin:
        pytesseract.pytesseract.tesseract_cmd = tesseract_bin
    else:
        pytesseract.pytesseract.tesseract_cmd = (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )

    config = "--psm 7 -c tessedit_char_whitelist=0123456789.-"
    img = Image.open(image_path)
    return pytesseract.image_to_string(img, config=config).strip()


def run_paddleocr(image_path: str) -> str:
    from paddleocr import PaddleOCR

    if not hasattr(run_paddleocr, "_ocr"):
        run_paddleocr._ocr = PaddleOCR(
            lang="en",
            device="cpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )
    ocr = run_paddleocr._ocr

    try:
        result = ocr.predict(image_path)
    except AttributeError:
        result = ocr.ocr(image_path)

    texts = []
    for res in result or []:
        if res is None:
            continue
        if hasattr(res, "rec_texts"):
            texts.extend(str(t) for t in res.rec_texts if t)
        elif isinstance(res, dict) and "rec_texts" in res:
            texts.extend(str(t) for t in res["rec_texts"] if t)
        elif isinstance(res, list):
            for line in res:
                if isinstance(line, (list, tuple)) and len(line) >= 2:
                    t = line[1]
                    texts.append(str(t[0] if isinstance(t, (list, tuple)) else t))
    return " ".join(texts).strip()


# ---------------------------------------------------------------------------
# YOLO Digit Detection
# ---------------------------------------------------------------------------

YOLO_CONF_THRESHOLD = 0.25
OVERLAP_X_GAP_PX = 8
OVERLAP_IOU_THRESHOLD = 0.3
CLASS_TO_CHAR = {
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    ".": ".", "-": "-",
}
NON_CHAR_CLASSES = {"screen"}


def _iou(a: dict, b: dict) -> float:
    ix0 = max(a["x0"], b["x0"])
    iy0 = max(a["y0"], b["y0"])
    ix1 = min(a["x1"], b["x1"])
    iy1 = min(a["y1"], b["y1"])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    area_a = max(0.0, a["x1"] - a["x0"]) * max(0.0, a["y1"] - a["y0"])
    area_b = max(0.0, b["x1"] - b["x0"]) * max(0.0, b["y1"] - b["y0"])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _merge_duplicates(dets: list[dict]) -> list[dict]:
    merged = []
    for det in dets:
        dup = None
        for kept in merged:
            close = abs(det["x_center"] - kept["x_center"]) < OVERLAP_X_GAP_PX
            if close and _iou(det, kept) >= OVERLAP_IOU_THRESHOLD:
                dup = kept
                break
        if dup is None:
            merged.append(det)
        elif det["confidence"] > dup["confidence"]:
            merged[merged.index(dup)] = det
    return merged


def _fix_minus(dets: list[dict]) -> list[dict]:
    fixed = []
    for i, det in enumerate(dets):
        if CLASS_TO_CHAR.get(det["class_name"]) == "-" and i != 0:
            continue
        fixed.append(det)
    return fixed


def _refine(det: dict, image) -> str:
    import cv2

    h, w = image.shape[:2]
    x0, y0 = max(0, int(det["x0"])), max(0, int(det["y0"]))
    x1, y1 = min(w, int(det["x1"])), min(h, int(det["y1"]))
    crop = image[y0:y1, x0:x1]
    if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
        return det["class_name"]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ch, cw = thresh.shape

    tl = thresh[int(ch * 0.15):int(ch * 0.40), 0:int(cw * 0.40)]
    tr = thresh[int(ch * 0.15):int(ch * 0.40), int(cw * 0.60):cw]
    bl = thresh[int(ch * 0.60):int(ch * 0.85), 0:int(cw * 0.40)]
    br = thresh[int(ch * 0.60):int(ch * 0.85), int(cw * 0.60):cw]

    f = cv2.countNonZero(tl) / max(1, tl.size)
    b = cv2.countNonZero(tr) / max(1, tr.size)
    e = cv2.countNonZero(bl) / max(1, bl.size)
    c = cv2.countNonZero(br) / max(1, br.size)
    score = (b + e) - (f + c)

    if score > 0.15:
        return "2"
    if score < -0.15:
        return "5"
    return det["class_name"]


def run_yolo(image_path: str) -> str:
    from ultralytics import YOLO
    import cv2

    if not hasattr(run_yolo, "_model"):
        if not YOLO_MODEL_PATH.is_file():
            raise FileNotFoundError(
                f"YOLO model not found: {YOLO_MODEL_PATH}\n"
                "Place digit_detection.pt next to ocr_pipeline.py"
            )
        run_yolo._model = YOLO(str(YOLO_MODEL_PATH))

    model = run_yolo._model
    results = model(image_path, verbose=False)[0]

    detections = []
    for box in results.boxes:
        conf = float(box.conf[0])
        if conf < YOLO_CONF_THRESHOLD:
            continue
        name = model.names[int(box.cls[0])]
        x0, y0, x1, y1 = box.xyxy[0].tolist()
        detections.append({
            "class_name": name,
            "confidence": conf,
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "x_center": (x0 + x1) / 2,
        })

    detections = [d for d in detections if d["class_name"] not in NON_CHAR_CLASSES]
    if not detections:
        return ""

    detections.sort(key=lambda d: d["x_center"])
    detections = _merge_duplicates(detections)
    detections = _fix_minus(detections)

    img = cv2.imread(image_path)
    if img is not None:
        for d in detections:
            if d["class_name"] in ("2", "5"):
                d["class_name"] = _refine(d, img)

    chars = []
    for d in detections:
        ch = CLASS_TO_CHAR.get(d["class_name"])
        if ch is not None:
            chars.append(ch)
    return "".join(chars)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

METHOD_MAP = {
    "easyocr": ("EasyOCR", run_easyocr),
    "tesseract": ("Tesseract", run_tesseract),
    "paddle": ("PaddleOCR", run_paddleocr),
    "yolo": ("YOLO Digit Detection", run_yolo),
}


def run_method(method_key: str, image_path: str) -> tuple[str, str, float]:
    name, fn = METHOD_MAP[method_key]
    t0 = time.perf_counter()
    try:
        text = fn(image_path)
        text = clean_reading(text)
    except Exception as exc:
        text = f"[ERROR: {type(exc).__name__}: {exc}]"
    ms = (time.perf_counter() - t0) * 1000.0
    return text.strip(), name, ms


def print_result(result: str, method_name: str, ms: float) -> None:
    print(f"OCR Result: {result}")
    print(f"Method: {method_name}")
    print(f"Processing Time: {ms:.0f} ms")


def collect_images(folder: Path) -> list[Path]:
    files = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return sorted(files)


def process_folder(
    input_dir: Path,
    method: str,
    do_preprocess: bool,
    output_dir: Path,
) -> None:
    images = collect_images(input_dir)
    if not images:
        print(f"No images found in '{input_dir}'", file=sys.stderr)
        print("Put your cropped display images (.jpg / .png) into the input folder.")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "ocr_results.csv"
    rows = []

    print(f"Processing {len(images)} image(s) from '{input_dir}'")
    print(f"Method : {method}")
    print(f"Output : {output_dir}")
    print("=" * 60)

    methods_to_run = list(METHOD_MAP.keys()) if method == "all" else [method]

    for img_path in images:
        print(f"\n>>> {img_path.name}")
        work_path = str(img_path)

        if do_preprocess:
            try:
                pre_path = output_dir / f"{img_path.stem}_preprocessed.png"
                work_path = preprocess_image(str(img_path), str(pre_path))
            except Exception as exc:
                print(f"  Preprocess failed ({exc}); using original")

        for mkey in methods_to_run:
            result, name, ms = run_method(mkey, work_path)
            print(f"  [{name}]  {result!r}  ({ms:.0f} ms)")
            rows.append({
                "image": img_path.name,
                "method": name,
                "result": result,
                "time_ms": round(ms, 1),
            })

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "method", "result", "time_ms"])
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 60)
    print(f"Done. Results saved to {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified OCR pipeline for cropped digital-display images"
    )
    parser.add_argument("--image", "-i", help="Path to a single cropped display image")
    parser.add_argument("--input", type=Path, default=INPUT_DIR,
                        help=f"Folder of cropped images (default: {INPUT_DIR})")
    parser.add_argument("--output", "-o", type=Path, default=OUTPUT_DIR,
                        help=f"Folder for CSV results (default: {OUTPUT_DIR})")
    parser.add_argument("--method", "-m", default="all",
                        choices=list(METHOD_MAP) + ["all"],
                        help="OCR backend (default: all)")
    parser.add_argument("--preprocess", action="store_true",
                        help="Apply CLAHE + bilateral preprocessing")
    args = parser.parse_args()

    if args.image:
        image_path = Path(args.image)
        if not image_path.is_file():
            print(f"Error: Image '{image_path}' does not exist.", file=sys.stderr)
            sys.exit(1)

        work_path = str(image_path)
        if args.preprocess:
            try:
                work_path = preprocess_image(str(image_path))
                print(f"(Preprocessed -> {work_path})", file=sys.stderr)
            except Exception as exc:
                print(f"Preprocessing failed ({exc}); using original", file=sys.stderr)

        if args.method == "all":
            print("=" * 50)
            for key in METHOD_MAP:
                result, name, ms = run_method(key, work_path)
                print(f"\n[{name}]")
                print_result(result, name, ms)
            print("=" * 50)
        else:
            result, name, ms = run_method(args.method, work_path)
            print_result(result, name, ms)
        return

    input_dir = args.input
    if not input_dir.is_dir():
        print(
            f"Error: Input folder '{input_dir}' does not exist.\n"
            f"Create it and put cropped images inside.",
            file=sys.stderr,
        )
        sys.exit(1)

    process_folder(
        input_dir=input_dir,
        method=args.method,
        do_preprocess=args.preprocess,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()