"""
digit_detector.py
==================
Runs the trained digit-detection YOLO model (best.pt) on a cropped display image.
"""

import sys
import time
from pathlib import Path
from ultralytics import YOLO

# ---------------- settings ----------------
MODEL_PATH = "best.pt"
CONFIDENCE_THRESHOLD = 0.25

_model = None  # Lazy-loaded singleton instance


def get_model():
    global _model
    if _model is None:
        _model = YOLO(MODEL_PATH)
    return _model


def detect_digits(image_path):
    model = get_model()

    start = time.perf_counter()
    results = model(image_path, verbose=False)[0]
    inference_time = time.perf_counter() - start

    detections = []
    for box in results.boxes:
        confidence = float(box.conf[0])
        if confidence < CONFIDENCE_THRESHOLD:
            continue

        class_id = int(box.cls[0])
        class_name = model.names[class_id]

        x0, y0, x1, y1 = box.xyxy[0].tolist()
        x_center = (x0 + x1) / 2

        detections.append({
            "class_name": class_name,
            "confidence": confidence,
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "x_center": x_center,
        })

    return {
        "detections": detections,
        "inference_time_sec": inference_time,
        "image_path": str(image_path),
    }


def print_clean_summary(result):
    detections = result.get("detections", [])
    digit_detections = [d for d in detections if d["class_name"] != "screen"]
    digit_detections.sort(key=lambda d: d["x_center"])
    detected_string = "".join(d["class_name"] for d in digit_detections) if digit_detections else "None"

    print("\n" + "=" * 45)
    print(f"  Image Path     : {result['image_path']}")
    print(f" Detected String: {detected_string}")
    print(f"  Inference Time : {result['inference_time_sec']:.2f}s")
    print("=" * 45)

    if digit_detections:
        print(" Digits Breakdown (Left to Right):")
        for d in digit_detections:
            print(f"   • {d['class_name']}  (Confidence: {d['confidence'] * 100:.1f}%)")
        print("=" * 45 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python digit_detector.py <image_path>")
        sys.exit(1)

    image_file = sys.argv[1]
    if not Path(image_file).exists():
        print(f"Error: Image '{image_file}' does not exist.")
        sys.exit(1)

    result_data = detect_digits(image_file)
    print_clean_summary(result_data)