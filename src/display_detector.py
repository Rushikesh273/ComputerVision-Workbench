"""
display_detector.py
====================
Uses the trained YOLO model to locate and crop the display out of factory
images.

Pipeline:
    Factory Image -> YOLO Detection -> Display Bounding Box -> Confidence Check -> Crop ROI -> Save Display Image


Usage:
    python display_detector.py

Expects, relative to this script (adjust the constants below if different):
    runs/detect/display_detection/weights/best.pt   -- the trained model
    input/*.jpg                                      -- factory images to process

Output, for every input/factory_001.jpg:
    output/factory_001_detected.jpg   -- original image with the box drawn on it
    output/factory_001_crop.jpg       -- just the cropped display region
"""

import os
import cv2
from ultralytics import YOLO

# ---------------- settings ----------------
MODEL_PATH = "best.pt"
INPUT_DIR = "input"
OUTPUT_DIR = "output"
CONFIDENCE_THRESHOLD = 0.5  # detections below this are discarded
BOX_COLOR = (0, 255, 0)


def process_image(model, image_path, output_dir):
    filename = os.path.basename(image_path)
    name, ext = os.path.splitext(filename)

    # Load the image
    img = cv2.imread(image_path)
    if img is None:
        print(f"  [!] could not read image: {image_path}")
        return

    # Run YOLO inference
    results = model(img, verbose=False)[0]

    if len(results.boxes) == 0:
        print(f"  [!] {filename}: no display detected, skipping")
        return

    # Find the display bounding box -- take the highest-confidence detection
    best_box = max(results.boxes, key=lambda b: float(b.conf[0]))
    confidence = float(best_box.conf[0])

    # Check the confidence score
    if confidence < CONFIDENCE_THRESHOLD:
        print(f"  [!] {filename}: best detection confidence {confidence:.2f} "
              f"below threshold {CONFIDENCE_THRESHOLD}, skipping")
        return

    # Extract the bounding box coordinates (pixel space)
    x0, y0, x1, y1 = map(int, best_box.xyxy[0].tolist())
    h, w = img.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)

    # Crop the display
    cropped = img[y0:y1, x0:x1]
    if cropped.size == 0:
        print(f"  [!] {filename}: empty crop after clipping, skipping")
        return

    # Save the original image with the bounding box drawn on it
    detected_img = img.copy()
    cv2.rectangle(detected_img, (x0, y0), (x1, y1), BOX_COLOR, 2)
    label = f"display {confidence:.2f}"
    cv2.putText(detected_img, label, (x0, max(0, y0 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, BOX_COLOR, 1)

    detected_path = os.path.join(output_dir, f"{name}_detected{ext}")
    crop_path = os.path.join(output_dir, f"{name}_crop{ext}")
    cv2.imwrite(detected_path, detected_img)
    cv2.imwrite(crop_path, cropped)

    print(f"  [OK] {filename}: confidence {confidence:.2f} -> "
          f"{os.path.basename(detected_path)}, {os.path.basename(crop_path)}")


def main():
    if not os.path.exists(MODEL_PATH):
        print(f"[!] Model not found at '{MODEL_PATH}'. Train it first with train_display_detector.py.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.isdir(INPUT_DIR):
        print(f"[!] Input folder '{INPUT_DIR}/' not found. Create it and add factory images to process.")
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
    for fname in image_files:
        process_image(model, os.path.join(INPUT_DIR, fname), OUTPUT_DIR)

    print(f"\nDone. Results saved to '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
