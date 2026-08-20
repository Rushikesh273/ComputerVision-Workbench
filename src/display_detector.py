"""
display_detector.py
====================
Uses the trained YOLO model to locate and crop the display out of factory
images, and automatically flags likely failure cases (no ground-truth boxes
needed -- this works on brand new, unlabeled images).

Pipeline:
    Factory Image -> YOLO Detection -> Display Bounding Box ->
    Confidence Check -> Crop ROI -> Save Display Image

Usage:
    python display_detector.py

Expects, relative to this script:
    display_detector.pt        -- the trained model (change MODEL_PATH below if it's elsewhere)
    input/*.jpg     -- new images to process

Output, for every input/xyz.jpg:
    output/xyz_detected.jpg   -- original image with the box drawn on it
    output/xyz_crop.jpg       -- just the cropped display region
    output/review_log.csv     -- one row per image, with confidence + any flags raised
"""

import csv
import os
import cv2
from ultralytics import YOLO

# ---------------- settings ----------------
MODEL_PATH = "display_detector.pt"
INPUT_DIR = "input"
OUTPUT_DIR = "output"
CONFIDENCE_THRESHOLD = 0.5   # below this, detection is discarded entirely
REVIEW_THRESHOLD = 0.65      # below this (but above the discard line), flagged "Low Confidence" for manual review
EDGE_MARGIN_PX = 5           # box within this many px of the frame edge -> flagged "Partial Detection"
                              # (tune based on your real photos' resolution; 2px flagged too
                              # aggressively on full-res factory images in earlier testing)
BOX_COLOR = (0, 255, 0)


def check_failure_flags(box_xyxy, confidence, img_w, img_h, num_detections):
    """Heuristic checks that don't need ground truth -- flags worth a manual look."""
    flags = []
    x0, y0, x1, y1 = box_xyxy

    if confidence < REVIEW_THRESHOLD:
        flags.append("Low Confidence")

    if num_detections > 1:
        flags.append("Possible False Positive (multiple candidates)")

    touches_edge = (x0 <= EDGE_MARGIN_PX or y0 <= EDGE_MARGIN_PX
                     or x1 >= img_w - EDGE_MARGIN_PX or y1 >= img_h - EDGE_MARGIN_PX)
    if touches_edge:
        flags.append("Partial Detection (box touches frame edge)")

    box_w, box_h = x1 - x0, y1 - y0
    if box_w <= 0 or box_h <= 0:
        flags.append("Incorrect Crop (degenerate box)")
    elif (box_w * box_h) / (img_w * img_h) < 0.02:
        flags.append("Incorrect Crop (suspiciously small relative to frame)")

    return flags


def process_image(model, image_path, output_dir, log_rows):
    filename = os.path.basename(image_path)
    name, ext = os.path.splitext(filename)

    img = cv2.imread(image_path)
    if img is None:
        print(f"  [!] could not read image: {image_path}")
        log_rows.append([filename, "ERROR", "", "Could not read image"])
        return
    h, w = img.shape[:2]

    results = model(img, verbose=False)[0]

    if len(results.boxes) == 0:
        print(f"  [!] {filename}: no display detected -> False Negative")
        log_rows.append([filename, "NO_DETECTION", "", "False Negative"])
        return

    best_box = max(results.boxes, key=lambda b: float(b.conf[0]))
    confidence = float(best_box.conf[0])

    if confidence < CONFIDENCE_THRESHOLD:
        print(f"  [!] {filename}: confidence {confidence:.2f} below threshold, skipping -> Low Confidence")
        log_rows.append([filename, "BELOW_THRESHOLD", f"{confidence:.3f}", "Low Confidence"])
        return

    x0, y0, x1, y1 = map(int, best_box.xyxy[0].tolist())
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)

    flags = check_failure_flags((x0, y0, x1, y1), confidence, w, h, len(results.boxes))

    cropped = img[y0:y1, x0:x1]
    if cropped.size == 0:
        print(f"  [!] {filename}: empty crop, skipping -> Incorrect Crop")
        log_rows.append([filename, "EMPTY_CROP", f"{confidence:.3f}", "Incorrect Crop"])
        return

    detected_img = img.copy()
    cv2.rectangle(detected_img, (x0, y0), (x1, y1), BOX_COLOR, 2)
    cv2.putText(detected_img, f"display {confidence:.2f}", (x0, max(0, y0 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, BOX_COLOR, 1)

    detected_path = os.path.join(output_dir, f"{name}_detected{ext}")
    crop_path = os.path.join(output_dir, f"{name}_crop{ext}")
    cv2.imwrite(detected_path, detected_img)
    cv2.imwrite(crop_path, cropped)

    flag_text = "; ".join(flags) if flags else "OK"
    print(f"  [OK] {filename}: confidence {confidence:.2f} -> {flag_text}")
    log_rows.append([filename, "DETECTED", f"{confidence:.3f}", flag_text])


def main():
    if not os.path.exists(MODEL_PATH):
        print(f"[!] Model not found at '{MODEL_PATH}'.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.isdir(INPUT_DIR):
        print(f"[!] Input folder '{INPUT_DIR}/' not found.")
        return

    print(f"Loading model from {MODEL_PATH} ...")
    model = YOLO(MODEL_PATH)

    image_files = sorted(
        f for f in os.listdir(INPUT_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )
    if not image_files:
        print(f"[!] No images found in '{INPUT_DIR}/'.")
        return

    print(f"Processing {len(image_files)} image(s) from '{INPUT_DIR}/' ...\n")
    log_rows = []
    for fname in image_files:
        process_image(model, os.path.join(INPUT_DIR, fname), OUTPUT_DIR, log_rows)

    log_path = os.path.join(OUTPUT_DIR, "review_log.csv")
    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "status", "confidence", "flags"])
        writer.writerows(log_rows)

    n_flagged = sum(1 for r in log_rows if r[3] not in ("OK",))
    print(f"\nDone. {len(log_rows)} image(s) processed, {n_flagged} flagged for manual review.")
    print(f"Results saved to '{OUTPUT_DIR}/', full log at '{log_path}'")


if __name__ == "__main__":
    main()
