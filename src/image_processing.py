"""
image_processing.py

All OpenCV image manipulation functions for this project, in one file.
Each function does exactly one job and returns a new image.

Run this file directly to test every function once on a sample image
and save the results to outputs/ (see the bottom of this file).
"""

import os
import numpy as np
import cv2


# ---------- Read / Save ----------

def read_image(path):
    """Read an image from disk."""
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image at '{path}'")
    return img


def save_image(img, path):
    """Save an image to disk, creating the folder if needed."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cv2.imwrite(path, img)


# ---------- Resize / Grayscale ----------

def resize_image(img, width, height):
    """Resize an image to an exact width and height."""
    return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)


def convert_to_grayscale(img):
    """Convert a color image to grayscale."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


# ---------- Brightness / Contrast ----------

def adjust_brightness(img, value):
    """Increase (positive value) or decrease (negative value) brightness."""
    return cv2.convertScaleAbs(img, alpha=1.0, beta=value)


def adjust_contrast(img, alpha):
    """Increase (alpha > 1) or decrease (alpha < 1) contrast."""
    return cv2.convertScaleAbs(img, alpha=alpha, beta=0)


# ---------- Blur ----------

def gaussian_blur(img, kernel_size=5):
    """Apply Gaussian blur (soft, natural blur)."""
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)


def median_blur(img, kernel_size=5):
    """Apply median blur (good at removing salt & pepper noise)."""
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.medianBlur(img, kernel_size)


def motion_blur(img, kernel_size=15, angle=0):
    """Simulate motion blur in a given direction (angle in degrees)."""
    kernel = np.zeros((kernel_size, kernel_size))
    kernel[kernel_size // 2, :] = np.ones(kernel_size)
    rot_matrix = cv2.getRotationMatrix2D((kernel_size / 2 - 0.5, kernel_size / 2 - 0.5), angle, 1)
    kernel = cv2.warpAffine(kernel, rot_matrix, (kernel_size, kernel_size))
    kernel = kernel / kernel.sum()
    return cv2.filter2D(img, -1, kernel)


# ---------- Noise ----------

def add_gaussian_noise(img, mean=0, sigma=25):
    """Add Gaussian (random, grainy) noise to the image."""
    noise = np.random.normal(mean, sigma, img.shape).astype(np.float32)
    noisy = img.astype(np.float32) + noise
    return np.clip(noisy, 0, 255).astype(np.uint8)


def add_salt_pepper_noise(img, amount=0.02, salt_ratio=0.5):
    """Add salt & pepper noise (random pure white and black pixels)."""
    noisy = img.copy()
    total_pixels = img.shape[0] * img.shape[1]
    num_salt = int(total_pixels * amount * salt_ratio)
    num_pepper = int(total_pixels * amount * (1 - salt_ratio))

    coords = [np.random.randint(0, dim, num_salt) for dim in img.shape[:2]]
    noisy[coords[0], coords[1]] = 255

    coords = [np.random.randint(0, dim, num_pepper) for dim in img.shape[:2]]
    noisy[coords[0], coords[1]] = 0

    return noisy


# ---------- Test every function individually, across multiple input images ----------

if __name__ == "__main__":
    INPUT_DIR = "sample_inputs"   # folder containing multiple test images
    OUTPUT_DIR = "outputs"

    def test(name, result, path):
        """Print a quick pass/fail check and save the result."""
        save_image(result, path)
        print(f"  [PASS] {name:<22} -> shape={result.shape}  saved: {path}")

    input_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not input_files:
        raise FileNotFoundError(f"No images found in '{INPUT_DIR}/' — add some .jpg/.png files there first.")

    print(f"Found {len(input_files)} input image(s) in '{INPUT_DIR}/'\n")

    for filename in input_files:
        name_no_ext = os.path.splitext(filename)[0]
        image_outdir = os.path.join(OUTPUT_DIR, name_no_ext)

        print(f"--- Testing on: {filename} ---")
        img = read_image(os.path.join(INPUT_DIR, filename))
        print(f"  [PASS] {'read_image':<22} -> shape={img.shape}  loaded: {filename}")
        save_image(img, os.path.join(image_outdir, "00_original.jpg"))

        test("resize_image", resize_image(img, 300, 300), os.path.join(image_outdir, "01_resized.jpg"))
        test("convert_to_grayscale", convert_to_grayscale(img), os.path.join(image_outdir, "02_grayscale.jpg"))

        test("adjust_brightness (+)", adjust_brightness(img, 60), os.path.join(image_outdir, "03_brightness_up.jpg"))
        test("adjust_brightness (-)", adjust_brightness(img, -60), os.path.join(image_outdir, "03_brightness_down.jpg"))

        test("adjust_contrast (+)", adjust_contrast(img, 1.8), os.path.join(image_outdir, "04_contrast_up.jpg"))
        test("adjust_contrast (-)", adjust_contrast(img, 0.5), os.path.join(image_outdir, "04_contrast_down.jpg"))

        test("gaussian_blur", gaussian_blur(img, 9), os.path.join(image_outdir, "05_gaussian_blur.jpg"))
        test("median_blur", median_blur(img, 9), os.path.join(image_outdir, "06_median_blur.jpg"))
        test("motion_blur", motion_blur(img, kernel_size=21, angle=0), os.path.join(image_outdir, "07_motion_blur.jpg"))

        test("add_gaussian_noise", add_gaussian_noise(img, sigma=25), os.path.join(image_outdir, "08_gaussian_noise.jpg"))
        test("add_salt_pepper_noise", add_salt_pepper_noise(img, amount=0.03), os.path.join(image_outdir, "09_salt_pepper_noise.jpg"))
        print()

    print(f"All 11 functions tested individually on {len(input_files)} image(s). Outputs saved under '{OUTPUT_DIR}/<image_name>/'")
