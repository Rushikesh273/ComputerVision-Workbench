"""
perspective_correction.py

Objective:
    Correct camera angle distortions and isolate the display.

Concepts used:
    - Contour Detection
    - Largest Rectangle Detection
    - Corner Detection
    - Perspective Transformation
    - Image Cropping
    - Region of Interest (ROI) Extraction
"""

import argparse
import os
import cv2
import numpy as np

# ---------- Helper Functions ----------

def read_image(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image at '{path}'")
    return img


def save_image(img, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cv2.imwrite(path, img)


def order_corners(pts):
    """
    Corner Detection + Ordering
    Orders 4 points as: Top-Left, Top-Right, Bottom-Right, Bottom-Left
    """
    pts = np.asarray(pts, dtype="float32").reshape(4, 2)
    ordered = np.zeros((4, 2), dtype="float32")

    s = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(s)]          # Top-Left
    ordered[2] = pts[np.argmax(s)]          # Bottom-Right

    diff = np.diff(pts, axis=1).ravel()
    ordered[1] = pts[np.argmin(diff)]       # Top-Right
    ordered[3] = pts[np.argmax(diff)]       # Bottom-Left

    return ordered


def perspective_transform(img, corners):
    """
    Perspective Transformation
    Warps the image so the display appears straight / front-facing.
    """
    (tl, tr, br, bl) = corners

    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)

    target_w = max(int(max(width_top, width_bottom)), 20)
    target_h = max(int(max(height_left, height_right)), 20)

    dst = np.array([
        [0, 0],
        [target_w - 1, 0],
        [target_w - 1, target_h - 1],
        [0, target_h - 1]
    ], dtype="float32")

    matrix = cv2.getPerspectiveTransform(corners, dst)
    warped = cv2.warpPerspective(img, matrix, (target_w, target_h))
    return warped


def detect_display(img):
    """
    Detects specifically the inner blue LCD display screen using 
    HSV Color Segmentation + Contour Approximation.
    """
    # 1. Convert to HSV for robust color isolation
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 2. Define range for the blue display bezel/background
    # Blue in OpenCV HSV: Hue ~ 90-130
    lower_blue = np.array([90, 50, 50])
    upper_blue = np.array([130, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)

    # Clean up noise in mask
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # 3. Find contours inside the blue mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_area = img.shape[0] * img.shape[1]
    best_corners = None
    best_score = -1

    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:15]:
        area = cv2.contourArea(cnt)
        
        # Screen is smaller relative to full frame: ~0.1% to 15% of image area
        if area < (img_area * 0.001) or area > (img_area * 0.25):
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)

        # If approximation gives 4 corners, process directly
        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype("float32")
        else:
            # Fallback for rounded corners: fit a minimum area rotated rectangle
            rect = cv2.minAreaRect(cnt)
            pts = cv2.boxPoints(rect).astype("float32")

        ordered = order_corners(pts)

        # Dimension & Aspect Ratio Checks
        (tl, tr, br, bl) = ordered
        width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
        height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))

        if height == 0:
            continue

        aspect = width / float(height)
        
        # Display screen typically has aspect ratio between 1.8 and 4.0
        if 1.5 <= aspect <= 4.5:
            if area > best_score:
                best_score = area
                best_corners = ordered

    # --- FALLBACK METHOD ---
    # If color mask fails (e.g. bad lighting), fall back to adaptive edge detection
    if best_corners is None:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 11, 2
        )
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:30]:
            area = cv2.contourArea(cnt)
            if not (img_area * 0.002 < area < img_area * 0.15):
                continue
            
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
            
            if len(approx) == 4:
                pts = approx.reshape(4, 2).astype("float32")
                ordered = order_corners(pts)
                (tl, tr, br, bl) = ordered
                w = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
                h = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
                if h > 0 and 1.8 <= (w / h) <= 4.0:
                    return ordered

    return best_corners


def draw_corners(img, corners):
    """Helper to visualize the detected rectangle."""
    vis = img.copy()
    pts = corners.astype(int)
    cv2.polylines(vis, [pts], isClosed=True, color=(0, 255, 0), thickness=3)
    for pt in pts:
        cv2.circle(vis, tuple(pt), 7, (0, 0, 255), -1)
    return vis


# ---------- Main Pipeline ----------

def correct_display(img):
    """
    Full pipeline:
    1. Detect display (contours + largest rectangle + corners)
    2. Perspective Transformation
    3. Image Cropping / ROI Extraction
    """
    corners = detect_display(img)

    if corners is None:
        return img, img.copy(), "no_detection"

    # Perspective Transformation + Cropping (ROI)
    corrected = perspective_transform(img, corners)
    before_vis = draw_corners(img, corners)

    return corrected, before_vis, "perspective_corrected"


# ---------- CLI ----------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Perspective correction of display")
    parser.add_argument("--input", default=None, help="Path to input image")
    args = parser.parse_args()

    # Folders
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    SAMPLES_DIR = os.path.join(SCRIPT_DIR, "..", "sample_images")
    OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "outputs")

    # Find input image
    if args.input and os.path.isfile(args.input):
        image_path = args.input
    else:
        images = [f for f in os.listdir(SAMPLES_DIR)
                  if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        if not images:
            raise FileNotFoundError("No images found in sample_images/")
        image_path = os.path.join(SAMPLES_DIR, images[0])

    print(f"Processing: {os.path.basename(image_path)}")

    img = read_image(image_path)
    corrected, before_vis, method = correct_display(img)

    # Save results directly in outputs/ (no subfolders)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    save_image(img, os.path.join(OUTPUT_DIR, "00_original.jpg"))
    save_image(before_vis, os.path.join(OUTPUT_DIR, "01_detected_rectangle.jpg"))
    save_image(corrected, os.path.join(OUTPUT_DIR, "02_corrected.jpg"))

    print(f"Method used : {method}")
    print(f"Output size : {corrected.shape[1]}x{corrected.shape[0]}")
    print(f"Results saved in: {OUTPUT_DIR}/")