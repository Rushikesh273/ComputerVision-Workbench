"""
morphology.py

Implements and tests 5 morphological operations, used to clean up a binary
(thresholded) image -- removing small noise specks, closing small gaps in
digit segments, and outlining shapes.

  - Erosion
  - Dilation
  - Opening   (erosion followed by dilation)
  - Closing   (dilation followed by erosion)
  - Morphological Gradient  (dilation minus erosion -- outlines edges)

These operate on a BINARY image, so this script first thresholds each sample
image (using Otsu, the best-performing method identified in thresholding.py)
before applying each morphological operation, so the results are realistic
rather than tested on an arbitrary input.

Run directly:
    python morphology.py
"""

import os
import cv2
import numpy as np


# ---------- I/O ----------

def read_image(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image at '{path}'")
    return img


def save_image(img, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cv2.imwrite(path, img)


def to_binary(img):
    """Grayscale + Otsu threshold -- turns a normal image into the black/white
    input that morphological operations expect."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


# ---------- The 5 morphological operations ----------

def erosion(img, kernel_size=3, iterations=1):
    """
    Shrinks white regions -- a white pixel only survives if ALL of its
    neighbors (within the kernel) are also white. Removes small white noise
    specks, but also shrinks/thins real digit segments.
    """
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.erode(img, kernel, iterations=iterations)


def dilation(img, kernel_size=3, iterations=1):
    """
    Grows white regions -- a pixel becomes white if ANY of its neighbors are
    white. Fills small black gaps/holes, but also thickens/merges nearby
    white regions that should stay separate.
    """
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.dilate(img, kernel, iterations=iterations)


def opening(img, kernel_size=3):
    """
    Erosion followed by dilation. Removes small white noise specks (via the
    erosion step) WITHOUT permanently shrinking the real shapes (the dilation
    step grows them back). Good general-purpose noise cleanup.
    """
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)


def closing(img, kernel_size=3):
    """
    Dilation followed by erosion. Fills small black gaps/holes inside a
    white shape WITHOUT permanently growing the shape's outer boundary.
    Useful for reconnecting a digit segment broken by noise or a small gap.
    """
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)


def morphological_gradient(img, kernel_size=3):
    """
    Dilation minus erosion. What's left is just the OUTLINE/edge of each
    white shape -- useful for visualizing or extracting digit boundaries
    rather than the filled-in shape itself.
    """
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.morphologyEx(img, cv2.MORPH_GRADIENT, kernel)


# ---------- Simple quantitative comparison metric ----------

def white_pixel_count(binary_img):
    return int(np.count_nonzero(binary_img == 255))


# ---------- Run every operation on every sample image ----------

if __name__ == "__main__":
    SAMPLES_DIR = "sample_images"
    OUTPUT_DIR = "outputs"

    sample_files = sorted(f for f in os.listdir(SAMPLES_DIR) if f.lower().endswith((".jpg", ".png")))
    if not sample_files:
        raise FileNotFoundError(f"No images found in '{SAMPLES_DIR}/'")

    print(f"Found {len(sample_files)} sample image(s)\n")
    print(f"{'sample':<28}{'operation':<28}{'white pixel count':<20}")
    print("-" * 76)

    for filename in sample_files:
        name = os.path.splitext(filename)[0]
        img = read_image(os.path.join(SAMPLES_DIR, filename))
        outdir = os.path.join(OUTPUT_DIR, name)

        binary = to_binary(img)
        save_image(binary, os.path.join(outdir, "10_binary_input_otsu.jpg"))
        print(f"{name:<28}{'(binary input)':<28}{white_pixel_count(binary):<20}")

        results = {
            "11_erosion.jpg": erosion(binary, 3),
            "12_dilation.jpg": dilation(binary, 3),
            "13_opening.jpg": opening(binary, 3),
            "14_closing.jpg": closing(binary, 3),
            "15_morphological_gradient.jpg": morphological_gradient(binary, 3),
        }

        for out_name, result in results.items():
            save_image(result, os.path.join(outdir, out_name))
            print(f"{name:<28}{out_name:<28}{white_pixel_count(result):<20}")
        print()

    print(f"Done. All outputs saved under '{OUTPUT_DIR}/<sample_name>/'")
