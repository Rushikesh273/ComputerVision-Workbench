"""
preprocessing_demo.py

Applies each of 6 standard OCR preprocessing techniques individually to a set
of sample images, and saves the results so they can be compared side by side.

Techniques covered:
  - Grayscale conversion
  - Histogram Equalization
  - CLAHE (Contrast Limited Adaptive Histogram Equalization)
  - Gaussian Blur
  - Median Blur
  - Bilateral Filter

Each sample image was deliberately picked because it shows a specific real
problem (low contrast, motion blur, uneven lighting) plus one clean baseline
image, so the effect of each technique is actually visible in the comparison
rather than being applied to an already-perfect image.

Run directly:
    python preprocessing_demo.py
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


# ---------- The 6 preprocessing techniques ----------

def convert_to_grayscale(img):
    """Reduce to a single intensity channel. Usually the very first step before OCR."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def histogram_equalization(img):
    """
    Redistributes intensity values across the WHOLE image so the histogram
    spreads out to use the full 0-255 range. Works on grayscale only.
    """
    gray = convert_to_grayscale(img) if len(img.shape) == 3 else img
    return cv2.equalizeHist(gray)


def clahe(img, clip_limit=2.0, tile_grid_size=(8, 8)):
    """
    Like histogram equalization, but applied in small local tiles rather than
    the whole image at once, with a clip limit to stop noise being over-amplified
    in flat regions. Generally the better choice for uneven/patchy lighting.
    """
    gray = convert_to_grayscale(img) if len(img.shape) == 3 else img
    clahe_obj = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe_obj.apply(gray)


def gaussian_blur(img, kernel_size=5):
    """Smooths using a weighted average of neighboring pixels. Soft, natural blur."""
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)


def median_blur(img, kernel_size=5):
    """Replaces each pixel with the median of its neighborhood. Best against salt & pepper noise."""
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.medianBlur(img, kernel_size)


def bilateral_filter(img, d=9, sigma_color=75, sigma_space=75):
    """
    Smooths flat regions like Gaussian blur, but preserves edges -- it only
    averages neighboring pixels that are also similar in color/intensity,
    so it won't blur across a sharp digit edge the way Gaussian blur does.
    """
    return cv2.bilateralFilter(img, d, sigma_color, sigma_space)


# ---------- Run every technique on every sample image ----------

if __name__ == "__main__":
    SAMPLES_DIR = "sample_images"
    OUTPUT_DIR = "outputs"

    sample_files = [f for f in os.listdir(SAMPLES_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not sample_files:
        raise FileNotFoundError(f"No images found in '{SAMPLES_DIR}/'")

    print(f"Found {len(sample_files)} sample image(s)\n")

    for filename in sorted(sample_files):
        name = os.path.splitext(filename)[0]
        img = read_image(os.path.join(SAMPLES_DIR, filename))
        outdir = os.path.join(OUTPUT_DIR, name)

        print(f"--- {filename} ---")
        save_image(img, os.path.join(outdir, "00_original.jpg"))

        save_image(convert_to_grayscale(img), os.path.join(outdir, "01_grayscale.jpg"))
        print("  [PASS] grayscale conversion")

        save_image(histogram_equalization(img), os.path.join(outdir, "02_histogram_equalization.jpg"))
        print("  [PASS] histogram equalization")

        save_image(clahe(img), os.path.join(outdir, "03_clahe.jpg"))
        print("  [PASS] CLAHE")

        save_image(gaussian_blur(img, 5), os.path.join(outdir, "04_gaussian_blur.jpg"))
        print("  [PASS] gaussian blur")

        save_image(median_blur(img, 5), os.path.join(outdir, "05_median_blur.jpg"))
        print("  [PASS] median blur")

        save_image(bilateral_filter(img), os.path.join(outdir, "06_bilateral_filter.jpg"))
        print("  [PASS] bilateral filter")
        print()

    print(f"Done. All outputs saved under '{OUTPUT_DIR}/<sample_name>/'")
