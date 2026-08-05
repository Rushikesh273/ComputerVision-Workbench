"""
weight_violation_checker.py
=============================
Multi-OCR weight violation checker
Supports: tesseract | easyocr | paddleocr | rapidocr
Produces separate CSV for each engine.
"""

import cv2
import numpy as np
import os
import re
import pandas as pd
from typing import Optional, Tuple

# ============================================================
# CHOOSE WHICH ENGINES TO RUN
# ============================================================
OCR_ENGINES = ["tesseract", "easyocr", "paddleocr", "rapidocr"]
# Example: OCR_ENGINES = ["tesseract", "easyocr"]

# ============================================================
# PATHS
# ============================================================
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR   = os.path.join(_SCRIPT_DIR, "Sample_inputs")
OUTPUT_DIR  = os.path.join(_SCRIPT_DIR, "Outputs_violations")

# ============================================================
# THRESHOLDS
# ============================================================
DEFAULT_LOWER = 2000
DEFAULT_UPPER = 8000

THRESHOLDS = {
    "0010_9562.jpg": (8000, 11000),
    "0022_7485.jpg": (6000, 9000),
    "0027_2045.jpg": (1500, 3000),
    "0029_4088.jpg": (3000, 5500),
    "0032_2664.jpg": (2000, 3500),
    "0043_2949.jpg": (2200, 3800),
    "0059_8213.jpg": (7000, 9500),
    "0060_4272.jpg": (3500, 5500),
    "0072_6224.jpg": (5000, 7500),
    "0103_9408.jpg": (8000, 11000),
    "0105_6784.jpg": (5500, 8000),
    "0116_6149.jpg": (5000, 7500),
    "0127_1791.jpg": (1200, 2500),
    "0137_3513.jpg": (2800, 4500),
    "0140_4957.jpg": (4000, 6000),
    "0145_8355.jpg": (7000, 10000),
    "0149_4222.jpg": (3500, 5500),
    "0176_7659.jpg": (6500, 9000),
    "0193_4800.jpg": (4000, 6000),
    "0205_2604.jpg": (2000, 3500),
}

def get_thresholds(image_name: str):
    return THRESHOLDS.get(image_name, (DEFAULT_LOWER, DEFAULT_UPPER))


# ============================================================
# OPTIONAL IMPORTS (engines that may not be installed)
# ============================================================
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

try:
    from paddleocr import PaddleOCR
    HAS_PADDLE = True
except ImportError:
    HAS_PADDLE = False

try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPID = True
except ImportError:
    HAS_RAPID = False


# ============================================================
# PREPROCESSING (unchanged)
# ============================================================
def resize_image(image, target_width=500):
    h, w = image.shape[:2]
    if w == 0 or h == 0:
        return image
    aspect = target_width / float(w)
    target_height = int(h * aspect)
    interp = cv2.INTER_AREA if target_width < w else cv2.INTER_CUBIC
    return cv2.resize(image, (target_width, target_height), interpolation=interp)


def _cluster_boxes(boxes, gap_ratio=0.5):
    if not boxes:
        return []
    avg_h = np.mean([b[3] for b in boxes])
    gap = avg_h * gap_ratio
    boxes_sorted = sorted(boxes, key=lambda b: b[0])
    clusters = [[boxes_sorted[0]]]
    for box in boxes_sorted[1:]:
        prev = clusters[-1]
        prev_max_x = max(b[0] + b[2] for b in prev)
        prev_y_c = np.mean([b[1] + b[3] / 2 for b in prev])
        this_y_c = box[1] + box[3] / 2
        if (box[0] - prev_max_x <= gap) and (abs(this_y_c - prev_y_c) <= avg_h * 1.5):
            prev.append(box)
        else:
            clusters.append([box])
    return clusters


def extract_numbers_roi(image):
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 7))
    morphed = cv2.morphologyEx(blurred, cv2.MORPH_GRADIENT, kernel)
    _, thresh = cv2.threshold(morphed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_boxes = []
    for c in contours:
        bx, by, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        aspect = bw / float(bh) if bh > 0 else 0
        if (0.02 * w * h < area < 0.80 * w * h) and (0.5 <= aspect <= 8.0):
            valid_boxes.append((bx, by, bw, bh))

    if valid_boxes:
        clusters = _cluster_boxes(valid_boxes)
        best = max(clusters, key=lambda cl: sum(b[2] * b[3] for b in cl))
        min_x = min(b[0] for b in best)
        min_y = min(b[1] for b in best)
        max_x = max(b[0] + b[2] for b in best)
        max_y = max(b[1] + b[3] for b in best)
        pad_x = int((max_x - min_x) * 0.15)
        pad_y = int((max_y - min_y) * 0.15)
        x1, y1 = max(0, min_x - pad_x), max(0, min_y - pad_y)
        x2, y2 = min(w, max_x + pad_x), min(h, max_y + pad_y)
        return image[y1:y2, x1:x2]

    pad_h, pad_w = int(h * 0.15), int(w * 0.15)
    return image[pad_h:h - pad_h, pad_w:w - pad_w]


def convert_to_grayscale(roi):
    return roi if len(roi.shape) == 2 else cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)


def reduce_noise(gray):
    return cv2.bilateralFilter(gray, d=7, sigmaColor=50, sigmaSpace=50)


def enhance_contrast(denoised):
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    return clahe.apply(denoised)


def apply_thresholding(enhanced):
    blur = cv2.GaussianBlur(enhanced, (5, 5), 0)
    otsu_val, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adjusted = max(10, int(otsu_val * 0.85))
    h, w = blur.shape
    cs = max(5, min(h, w) // 20)
    corners = np.concatenate((
        blur[0:cs, 0:cs].flatten(),
        blur[0:cs, w - cs:w].flatten(),
        blur[h - cs:h, 0:cs].flatten(),
        blur[h - cs:h, w - cs:w].flatten(),
    ))
    bg = float(np.median(corners))
    p90 = float(np.percentile(blur, 90))
    if bg > 127 or p90 < bg + 15:
        _, binary = cv2.threshold(blur, adjusted, 255, cv2.THRESH_BINARY_INV)
    else:
        _, binary = cv2.threshold(blur, adjusted, 255, cv2.THRESH_BINARY)
    denoise_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    return cv2.morphologyEx(binary, cv2.MORPH_OPEN, denoise_k, iterations=1)


def apply_morphological_operations(thresh):
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)))
    return cv2.dilate(closed, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)), iterations=1)


def clean_display_image(morph):
    h, w = morph.shape[:2]
    total = h * w
    min_area = max(6, int(total * 0.0008))
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(morph, connectivity=8)
    mask = np.zeros_like(morph)
    found = False

    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]
        if bw > 0.98 * w or bh > 0.98 * h or area > 0.90 * total:
            continue
        if area < min_area:
            continue
        if bh < int(0.05 * h):
            aspect = bw / float(bh) if bh > 0 else 0
            cy = y + bh / 2.0
            if not ((0.5 <= aspect <= 2.0) and (area >= min_area) and (cy > 0.55 * h)):
                continue
        mask[labels == i] = 255
        found = True

    if not found:
        mask = morph.copy()

    ocr_ready = cv2.bitwise_not(mask)
    return cv2.copyMakeBorder(ocr_ready, 30, 30, 30, 30, borderType=cv2.BORDER_CONSTANT, value=255)


def _order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)]
    return rect


def correct_perspective(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image, False

    largest = max(contours, key=cv2.contourArea)
    img_area = image.shape[0] * image.shape[1]
    area = cv2.contourArea(largest)
    if area < 0.02 * img_area or area > 0.85 * img_area:
        return image, False

    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) != 4:
        box = cv2.boxPoints(cv2.minAreaRect(largest))
        approx = box.reshape(-1, 1, 2)

    pts = approx.reshape(len(approx), 2).astype("float32")
    if len(pts) != 4:
        return image, False

    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    max_w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    max_h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if max_w < 20 or max_h < 15:
        return image, False

    dst = np.array([[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (max_w, max_h)), True


# ============================================================
# OCR BACKENDS
# ============================================================
def clean_text(text: str) -> str:
    return re.sub(r"[^0-9.]", "", text.strip())


def read_tesseract(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    if not HAS_TESSERACT:
        return None, "pytesseract not installed"
    img = cv2.imread(image_path, 0)
    if img is None:
        return None, "could not load image"
    img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    configs = [
        r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.",
        r"--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789.",
        r"--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789.",
        r"--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.",
    ]
    candidates = [img, cv2.bitwise_not(img)]
    last_err = "empty OCR result"

    for candidate in candidates:
        for config in configs:
            try:
                raw = pytesseract.image_to_string(candidate, config=config)
                cleaned = clean_text(raw)
                if cleaned and cleaned.count(".") <= 1 and len(cleaned) >= 1:
                    return cleaned, None
                if raw.strip():
                    last_err = f"unusable: '{raw.strip()}'"
            except Exception as e:
                last_err = str(e)
    return None, last_err


_easyocr_reader = None
def read_easyocr(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    global _easyocr_reader
    if not HAS_EASYOCR:
        return None, "easyocr not installed"
    try:
        if _easyocr_reader is None:
            _easyocr_reader = easyocr.Reader(["en"], gpu=False)
        result = _easyocr_reader.readtext(image_path, detail=0, allowlist="0123456789.")
        if not result:
            return None, "empty result"
        text = "".join(result)
        cleaned = clean_text(text)
        if cleaned:
            return cleaned, None
        return None, f"unusable: '{text}'"
    except Exception as e:
        return None, str(e)


_paddle_ocr = None
def read_paddleocr(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    global _paddle_ocr
    if not HAS_PADDLE:
        return None, "paddleocr not installed"
    try:
        if _paddle_ocr is None:
            _paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = _paddle_ocr.ocr(image_path, cls=True)
        if not result or not result[0]:
            return None, "empty result"
        texts = [line[1][0] for line in result[0]]
        text = "".join(texts)
        cleaned = clean_text(text)
        if cleaned:
            return cleaned, None
        return None, f"unusable: '{text}'"
    except Exception as e:
        return None, str(e)


_rapid_ocr = None
def read_rapidocr(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    global _rapid_ocr
    if not HAS_RAPID:
        return None, "rapidocr_onnxruntime not installed"
    try:
        if _rapid_ocr is None:
            _rapid_ocr = RapidOCR()
        result, _ = _rapid_ocr(image_path)
        if not result:
            return None, "empty result"
        text = "".join([line[1] for line in result])
        cleaned = clean_text(text)
        if cleaned:
            return cleaned, None
        return None, f"unusable: '{text}'"
    except Exception as e:
        return None, str(e)


OCR_FUNCTIONS = {
    "tesseract": read_tesseract,
    "easyocr":   read_easyocr,
    "paddleocr": read_paddleocr,
    "rapidocr":  read_rapidocr,
}


# ============================================================
# PROCESS ONE IMAGE
# ============================================================
def process_image(image_path: str, debug_dir: str, ocr_engine: str):
    os.makedirs(debug_dir, exist_ok=True)
    raw = cv2.imread(image_path)
    if raw is None:
        return {
            "ocr_reading": None,
            "ocr_raw_text": None,
            "perspective_corrected": False,
            "ocr_error": "could not load image",
        }

    resized = resize_image(raw)
    corrected, was_corrected = correct_perspective(resized)
    cv2.imwrite(os.path.join(debug_dir, "01_perspective_corrected.jpg"), corrected)

    roi = extract_numbers_roi(corrected)
    gray = convert_to_grayscale(roi)
    denoised = reduce_noise(gray)
    enhanced = enhance_contrast(denoised)
    thresh = apply_thresholding(enhanced)
    morph = apply_morphological_operations(thresh)
    clean = clean_display_image(morph)

    final_path = os.path.join(debug_dir, f"02_ocr_ready_{ocr_engine}.jpg")
    cv2.imwrite(final_path, clean)

    reader = OCR_FUNCTIONS.get(ocr_engine)
    if reader is None:
        return {
            "ocr_reading": None,
            "ocr_raw_text": None,
            "perspective_corrected": was_corrected,
            "ocr_error": f"unknown engine: {ocr_engine}",
        }

    reading_str, ocr_error = reader(final_path)
    reading_val = None
    if reading_str is not None:
        try:
            reading_val = float(reading_str)
        except ValueError:
            ocr_error = f"non-numeric: '{reading_str}'"
            reading_str = None

    return {
        "ocr_reading": reading_val,
        "ocr_raw_text": reading_str,
        "perspective_corrected": was_corrected,
        "ocr_error": ocr_error,
    }


# ============================================================
# REPORT
# ============================================================
def build_report(rows):
    df = pd.DataFrame(rows)
    df["OCR Reading"] = pd.to_numeric(df["OCR Reading"], errors="coerce")

    def _violation_type(row):
        val = row["OCR Reading"]
        lower = row["Lower Threshold"]
        upper = row["Upper Threshold"]
        if pd.isna(val):
            return "OCR_FAILED"
        if val < lower:
            return "BELOW"
        if val > upper:
            return "ABOVE"
        return "NONE"

    df["Violation Type"] = df.apply(_violation_type, axis=1)
    df["Violation"] = df["Violation Type"] != "NONE"

    return df[[
        "Image", "OCR Reading", "OCR Raw Text", "Perspective Corrected",
        "Lower Threshold", "Upper Threshold", "Violation", "Violation Type",
    ]]


# ============================================================
# MAIN
# ============================================================
def main():
    if not os.path.exists(INPUT_DIR):
        print(f"Input directory not found: {INPUT_DIR}")
        return

    valid_ext = (".png", ".jpg", ".jpeg")
    image_files = sorted(f for f in os.listdir(INPUT_DIR) if f.lower().endswith(valid_ext))
    if not image_files:
        print(f"No images found in '{INPUT_DIR}'.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for engine in OCR_ENGINES:
        print(f"\n{'='*60}")
        print(f"Running OCR engine: {engine.upper()}")
        print(f"{'='*60}")

        rows = []
        ocr_errors = {}

        for fname in image_files:
            image_path = os.path.join(INPUT_DIR, fname)
            debug_dir = os.path.join(OUTPUT_DIR, os.path.splitext(fname)[0])
            result = process_image(image_path, debug_dir, engine)

            lower, upper = get_thresholds(fname)

            rows.append({
                "Image": fname,
                "OCR Reading": result["ocr_reading"],
                "OCR Raw Text": result["ocr_raw_text"] or "",
                "Perspective Corrected": result["perspective_corrected"],
                "Lower Threshold": lower,
                "Upper Threshold": upper,
            })

            if result["ocr_error"]:
                ocr_errors[result["ocr_error"]] = ocr_errors.get(result["ocr_error"], 0) + 1
                print(f"{fname:20s}  OCR_FAILED  ({result['ocr_error']})")
            else:
                print(f"{fname:20s}  reading={result['ocr_reading']}  "
                      f"limits=[{lower}–{upper}]")

        df = build_report(rows)
        csv_path = os.path.join(_SCRIPT_DIR, f"violations_report_{engine}.csv")
        df.to_csv(csv_path, index=False)

        n = len(df)
        n_viol = int(df["Violation"].sum())
        print(f"\n[{engine}] Processed {n} images")
        print(f"Saved: {csv_path}")
        print(f"OK: {n - n_viol} | Violations: {n_viol}")
        print(f"  BELOW: {(df['Violation Type']=='BELOW').sum()}")
        print(f"  ABOVE: {(df['Violation Type']=='ABOVE').sum()}")
        print(f"  OCR_FAILED: {(df['Violation Type']=='OCR_FAILED').sum()}")

        if ocr_errors:
            print("OCR errors:")
            for msg, c in sorted(ocr_errors.items(), key=lambda x: -x[1]):
                print(f"  [{c}x] {msg}")


if __name__ == "__main__":
    main()