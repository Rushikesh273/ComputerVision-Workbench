"""
digit_decoder.py
=================
Decodes YOLO digit detections into a final reading string.

"""

import sys
import json
from pathlib import Path
import cv2
import numpy as np

CLASS_TO_CHAR = {
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    ".": ".", "-": "-",
}

NON_CHARACTER_CLASSES = {"screen"}
OVERLAP_X_GAP_PX = 8
OVERLAP_IOU_THRESHOLD = 0.3
LOW_CONFIDENCE_THRESHOLD = 0.6


def _iou(a, b):
    ix0, iy0 = max(a["x0"], b["x0"]), max(a["y0"], b["y0"])
    ix1, iy1 = min(a["x1"], b["x1"]), min(a["y1"], b["y1"])
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    area_a = max(0.0, a["x1"] - a["x0"]) * max(0.0, a["y1"] - a["y0"])
    area_b = max(0.0, b["x1"] - b["x0"]) * max(0.0, b["y1"] - b["y0"])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _merge_duplicates(sorted_detections, flags):
    merged = []
    for det in sorted_detections:
        duplicate_of = None
        for kept in merged:
            close_in_x = abs(det["x_center"] - kept["x_center"]) < OVERLAP_X_GAP_PX
            overlaps = _iou(det, kept) >= OVERLAP_IOU_THRESHOLD
            if close_in_x and overlaps:
                duplicate_of = kept
                break

        if duplicate_of is None:
            merged.append(det)
        elif det["confidence"] > duplicate_of["confidence"]:
            flags.append(
                f"Duplicate near x={det['x_center']:.1f}: kept '{det['class_name']}' "
                f"(conf {det['confidence']:.2f}) over '{duplicate_of['class_name']}'"
            )
            merged[merged.index(duplicate_of)] = det
        else:
            flags.append(
                f"Duplicate near x={det['x_center']:.1f}: kept '{duplicate_of['class_name']}' "
                f"(conf {duplicate_of['confidence']:.2f}) over '{det['class_name']}'"
            )
    return merged


def _fix_minus_position(sorted_detections, flags):
    fixed = []
    for i, det in enumerate(sorted_detections):
        is_minus = CLASS_TO_CHAR.get(det["class_name"]) == "-"
        if is_minus and i != 0:
            flags.append(
                f"Dropped misplaced 'minus' at position {i} (x={det['x_center']:.1f})"
            )
            continue
        fixed.append(det)
    return fixed


def _refine_2_vs_5(det, image):
    """
    Measures corner segment brightness ratio using Otsu thresholding:
    - Digit '2': Top-Right (B) + Bottom-Left (E) are LIT.
    - Digit '5': Top-Left (F) + Bottom-Right (C) are LIT.
    """
    h, w = image.shape[:2]
    ix0, iy0 = max(0, int(det["x0"])), max(0, int(det["y0"]))
    ix1, iy1 = min(w, int(det["x1"])), min(h, int(det["y1"]))

    crop = image[iy0:iy1, ix0:ix1]
    if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
        return det["class_name"]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    ch, cw = thresh.shape

    top_left_f  = thresh[int(ch * 0.15):int(ch * 0.40), 0:int(cw * 0.40)]
    top_right_b = thresh[int(ch * 0.15):int(ch * 0.40), int(cw * 0.60):cw]
    bot_left_e  = thresh[int(ch * 0.60):int(ch * 0.85), 0:int(cw * 0.40)]
    bot_right_c = thresh[int(ch * 0.60):int(ch * 0.85), int(cw * 0.60):cw]

    f_ratio = cv2.countNonZero(top_left_f) / max(1, top_left_f.size)
    b_ratio = cv2.countNonZero(top_right_b) / max(1, top_right_b.size)
    e_ratio = cv2.countNonZero(bot_left_e) / max(1, bot_left_e.size)
    c_ratio = cv2.countNonZero(bot_right_c) / max(1, bot_right_c.size)

    score_2 = (b_ratio + e_ratio) - (f_ratio + c_ratio)

    if score_2 > 0.15:
        return "2"
    elif score_2 < -0.15:
        return "5"
    return det["class_name"]


def _correct_digit_shapes(sorted_detections, image_path, flags):
    if not image_path:
        return sorted_detections

    path_obj = Path(image_path).resolve()
    image = cv2.imread(str(path_obj))
    if image is None:
        flags.append(f"Warning: Could not load image at '{path_obj}' for pixel analysis")
        return sorted_detections

    for det in sorted_detections:
        current_class = det["class_name"]
        if current_class in ["2", "5"]:
            corrected = _refine_2_vs_5(det, image)
            if corrected != current_class:
                flags.append(
                    f"Pixel analysis corrected '{current_class}' -> '{corrected}' "
                    f"at x={det['x_center']:.1f} (conf was {det['confidence']:.2f})"
                )
                det["class_name"] = corrected

    return sorted_detections


def decode(detection_result, image_path=None):
    raw_detections = detection_result.get("detections", [])
    img_path = image_path or detection_result.get("image_path")
    flags = []

    screen_boxes = [d for d in raw_detections if d["class_name"] in NON_CHARACTER_CLASSES]
    raw_detections = [d for d in raw_detections if d["class_name"] not in NON_CHARACTER_CLASSES]

    if not raw_detections:
        return {
            "decoded_string": "",
            "characters": [],
            "avg_confidence": 0.0,
            "flags": ["No detections -- nothing to decode"],
            "screen_boxes": screen_boxes,
        }

    sorted_detections = sorted(raw_detections, key=lambda d: d["x_center"])
    sorted_detections = _merge_duplicates(sorted_detections, flags)
    sorted_detections = _fix_minus_position(sorted_detections, flags)
    sorted_detections = _correct_digit_shapes(sorted_detections, img_path, flags)

    characters = []
    for det in sorted_detections:
        char = CLASS_TO_CHAR.get(det["class_name"])
        if char is None:
            flags.append(f"Unknown class '{det['class_name']}' skipped at x={det['x_center']:.1f}")
            continue

        is_low_conf = det["confidence"] < LOW_CONFIDENCE_THRESHOLD
        if is_low_conf:
            flags.append(
                f"Low-confidence character '{char}' at x={det['x_center']:.1f} "
                f"(conf={det['confidence']:.2f})"
            )

        characters.append({
            "char": char,
            "confidence": det["confidence"],
            "x_center": det["x_center"],
            "low_confidence": is_low_conf,
        })

    decoded_string = "".join(c["char"] for c in characters)
    avg_confidence = (
        sum(c["confidence"] for c in characters) / len(characters)
        if characters else 0.0
    )

    return {
        "decoded_string": decoded_string,
        "characters": characters,
        "avg_confidence": avg_confidence,
        "flags": flags,
        "screen_boxes": screen_boxes,
    }


def print_formatted_summary(decoded_result, image_path):
    print("\n" + "=" * 50)
    print(f"  Image File    : {image_path}")
    print(f"  Decoded Result: {decoded_result['decoded_string']}")
    print(f"  Avg Confidence: {decoded_result['avg_confidence'] * 100:.2f}%")
    print("=" * 50)

    print(" Character Breakdown (Left to Right):")
    for idx, char_info in enumerate(decoded_result["characters"], 1):
        status = " LOW CONF" if char_info["low_confidence"] else "OK"
        print(
            f"   {idx}. '{char_info['char']}'  │  Conf: {char_info['confidence'] * 100:.1f}%  "
            f"│  x_center: {char_info['x_center']:.1f}  │  [{status}]"
        )

    print("=" * 50)
    if decoded_result["flags"]:
        print(f"  Audit Trail & Adjustments ({len(decoded_result['flags'])}):")
        for flag in decoded_result["flags"]:
            print(f"   • {flag}")
    else:
        print("  Audit Trail: No adjustments or warnings.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    from digit_detector import detect_digits

    if len(sys.argv) < 2:
        print("Usage: python digit_decoder.py <image_path>")
        sys.exit(1)

    input_path = sys.argv[1]
    detection_result = detect_digits(input_path)
    decoded = decode(detection_result, image_path=input_path)

    print_formatted_summary(decoded, input_path)