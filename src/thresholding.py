"""
thresholding.py

Implements and tests 4 thresholding techniques for separating a display's
digit segments (foreground) from its background:

  - Global Thresholding
  - Adaptive Mean Thresholding
  - Adaptive Gaussian Thresholding
  - Otsu Thresholding

Each is tested individually against multiple real sample images -- including
deliberately challenging ones (low contrast, uneven lighting) -- since a
technique that works on a clean image may fail on a realistic one, and the
whole point of this comparison is to find out which actually holds up.

Run directly:
    python thresholding.py
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


def to_gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img


# ---------- The 4 thresholding techniques ----------

def global_threshold(img, thresh_val=127):
    """
    Every pixel above `thresh_val` becomes white, everything below becomes
    black. Simplest possible method -- one fixed cutoff for the whole image.
    """
    gray = to_gray(img)
    _, result = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
    return result


def adaptive_mean_threshold(img, block_size=11, C=2):
    """
    Instead of one global cutoff, calculates a LOCAL threshold for each pixel
    based on the mean of its surrounding block_size x block_size neighborhood,
    minus a constant C. Adapts to lighting that varies across the image.
    """
    gray = to_gray(img)
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, block_size, C
    )


def adaptive_gaussian_threshold(img, block_size=11, C=2):
    """
    Same local-neighborhood idea as adaptive mean, but the neighborhood
    average is weighted (closer pixels count more), which usually gives a
    smoother, less noisy result than the plain mean version.
    """
    gray = to_gray(img)
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, C
    )


def otsu_threshold(img):
    """
    Automatically calculates the single best global cutoff by analyzing the
    image's histogram (looking for the point that best splits it into two
    groups), rather than the fixed guess used in global_threshold. Still a
    single global value, just a smarter one.
    """
    gray = to_gray(img)
    _, result = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return result


# ---------- Simple quantitative comparison metric ----------

def foreground_ratio(binary_img):
    """
    % of pixels that ended up white (foreground). Not a measure of
    'correctness' on its own, but a useful sanity signal: a seven-segment
    display's digit area is a small fraction of the frame, so a result where
    50%+ of the image is white almost certainly means the threshold picked
    up background noise/glare rather than just the digits.
    """
    return round(100 * np.count_nonzero(binary_img == 255) / binary_img.size, 2)


# ---------- Run every technique on every sample image ----------

if __name__ == "__main__":
    SAMPLES_DIR = "sample_images"
    OUTPUT_DIR = "outputs"

    sample_files = sorted(f for f in os.listdir(SAMPLES_DIR) if f.lower().endswith((".jpg", ".png")))
    if not sample_files:
        raise FileNotFoundError(f"No images found in '{SAMPLES_DIR}/'")

    print(f"Found {len(sample_files)} sample image(s)\n")
    print(f"{'sample':<28}{'technique':<28}{'% white (foreground)':<22}")
    print("-" * 78)

    for filename in sample_files:
        name = os.path.splitext(filename)[0]
        img = read_image(os.path.join(SAMPLES_DIR, filename))
        outdir = os.path.join(OUTPUT_DIR, name)

        save_image(img, os.path.join(outdir, "00_original.jpg"))
        save_image(to_gray(img), os.path.join(outdir, "01_grayscale.jpg"))

        results = {
            "02_global_threshold.jpg": global_threshold(img),
            "03_adaptive_mean.jpg": adaptive_mean_threshold(img),
            "04_adaptive_gaussian.jpg": adaptive_gaussian_threshold(img),
            "05_otsu_threshold.jpg": otsu_threshold(img),
        }

        for out_name, result in results.items():
            save_image(result, os.path.join(outdir, out_name))
            pct = foreground_ratio(result)
            print(f"{name:<28}{out_name:<28}{pct:<22}")

    print(f"\nDone. All outputs saved under '{OUTPUT_DIR}/<sample_name>/'")
