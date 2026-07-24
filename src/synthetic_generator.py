"""
synthetic_generator.py

Generates realistic synthetic variations of a single original image by
randomly combining:
  - Brightness adjustment
  - Contrast adjustment
  - Gaussian noise
  - Motion blur
  - Gaussian blur
  - Rotation (+/- 5 degrees)
  - Scaling
  - Perspective transformation

Each generated image applies a random SUBSET of these (not all 8 every time)
with randomized parameters, so no two generated images end up identical.

Fully standalone — no dependency on any other project file, only OpenCV/NumPy.

Run directly:
    python synthetic_generator.py
"""

import os
import csv
import random
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


# ---------- Geometric transforms ----------

def rotate_image(img, angle):
    """Rotate the image by `angle` degrees around its center. Keeps the original size."""
    h, w = img.shape[:2]
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)


def scale_image(img, scale_factor):
    """
    Scale the image up or down by `scale_factor`, then crop or pad back to the
    original size so every output image stays a consistent shape.
    """
    h, w = img.shape[:2]
    new_w, new_h = max(1, int(w * scale_factor)), max(1, int(h * scale_factor))
    scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros_like(img)
    if scale_factor >= 1.0:
        start_y = max(0, (new_h - h) // 2)
        start_x = max(0, (new_w - w) // 2)
        canvas[:, :] = scaled[start_y:start_y + h, start_x:start_x + w]
    else:
        start_y = (h - new_h) // 2
        start_x = (w - new_w) // 2
        canvas[start_y:start_y + new_h, start_x:start_x + new_w] = scaled
    return canvas


def perspective_transform(img, strength=0.05):
    """
    Apply a mild perspective warp by randomly nudging each of the 4 corners
    of the image inward/outward by up to `strength` (as a fraction of width/height).
    Simulates a camera not viewing the display perfectly straight-on.
    """
    h, w = img.shape[:2]
    max_dx = int(w * strength)
    max_dy = int(h * strength)

    src = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    dst = np.float32([
        [0 + random.randint(-max_dx, max_dx), 0 + random.randint(-max_dy, max_dy)],
        [w + random.randint(-max_dx, max_dx), 0 + random.randint(-max_dy, max_dy)],
        [0 + random.randint(-max_dx, max_dx), h + random.randint(-max_dy, max_dy)],
        [w + random.randint(-max_dx, max_dx), h + random.randint(-max_dy, max_dy)],
    ])
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)


# ---------- Random augmentation engine ----------

# Fixed, sensible order to apply ops in (geometric first, then lighting, then degradation)
# regardless of which subset gets randomly picked for a given image.
AUGMENTATION_ORDER = [
    "rotation", "scaling", "perspective",
    "brightness", "contrast",
    "gaussian_blur", "motion_blur", "gaussian_noise",
]


def apply_random_augmentations(img, min_ops=3, max_ops=6):
    """
    Apply a random subset (min_ops to max_ops) of the 8 augmentations, each with
    randomized parameters. Returns the augmented image plus a log of exactly what
    was applied (used for the manifest / to guarantee no two images are identical).
    """
    n_ops = random.randint(min_ops, max_ops)
    chosen = random.sample(AUGMENTATION_ORDER, n_ops)
    chosen.sort(key=AUGMENTATION_ORDER.index)  # apply in a consistent, sensible order

    result = img.copy()
    log = []

    for op in chosen:
        if op == "brightness":
            value = random.randint(-50, 50)
            result = adjust_brightness(result, value)
            log.append(f"brightness({value:+d})")

        elif op == "contrast":
            alpha = round(random.uniform(0.6, 1.6), 2)
            result = adjust_contrast(result, alpha)
            log.append(f"contrast(alpha={alpha})")

        elif op == "gaussian_noise":
            sigma = random.randint(10, 35)
            result = add_gaussian_noise(result, sigma=sigma)
            log.append(f"gaussian_noise(sigma={sigma})")

        elif op == "motion_blur":
            k = random.choice([9, 13, 17, 21])
            angle = random.randint(0, 179)
            result = motion_blur(result, kernel_size=k, angle=angle)
            log.append(f"motion_blur(k={k},angle={angle})")

        elif op == "gaussian_blur":
            k = random.choice([3, 5, 7, 9])
            result = gaussian_blur(result, k)
            log.append(f"gaussian_blur(k={k})")

        elif op == "rotation":
            angle = round(random.uniform(-5, 5), 1)
            result = rotate_image(result, angle)
            log.append(f"rotation({angle:+}deg)")

        elif op == "scaling":
            scale = round(random.uniform(0.85, 1.15), 2)
            result = scale_image(result, scale)
            log.append(f"scaling(x{scale})")

        elif op == "perspective":
            strength = round(random.uniform(0.02, 0.08), 3)
            result = perspective_transform(result, strength)
            log.append(f"perspective(strength={strength})")

    return result, log


# ---------- Dataset generation ----------

def generate_synthetic_dataset(input_image_path, output_dir, num_images=200,
                                min_ops=3, max_ops=6, seed=42):
    """
    Read a single original image and generate `num_images` synthetic variations
    of it, each using a random subset/combination of augmentations. Saves all
    generated images plus a manifest.csv describing exactly what was applied
    to each one.
    """
    random.seed(seed)
    np.random.seed(seed)

    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    print(f"Reading original image: {input_image_path}")
    original = read_image(input_image_path)
    print(f"Generating {num_images} synthetic images into '{images_dir}/'...\n")

    seen_signatures = set()
    manifest_rows = []

    generated = 0
    attempts = 0
    while generated < num_images:
        attempts += 1
        augmented, log = apply_random_augmentations(original, min_ops, max_ops)

        # Guarantee every generated image is genuinely different: the exact
        # augmentation log (technique + randomized parameters) is used as a
        # signature. If we ever land on an identical one (astronomically
        # unlikely given the continuous random parameters), just re-roll.
        signature = ";".join(log)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        out_name = f"synthetic_{generated:04d}.jpg"
        save_image(augmented, os.path.join(images_dir, out_name))
        manifest_rows.append([out_name, os.path.basename(input_image_path), "; ".join(log)])

        generated += 1
        if generated % 50 == 0:
            print(f"  {generated}/{num_images} generated...")

    manifest_path = os.path.join(output_dir, "manifest.csv")
    with open(manifest_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["output_filename", "source_image", "augmentations_applied"])
        writer.writerows(manifest_rows)

    print(f"\nDone. {generated} synthetic images saved to '{images_dir}/'")
    print(f"Manifest (what was applied to each image) saved to '{manifest_path}'")
    print(f"(took {attempts} attempts to generate {generated} unique images)")


if __name__ == "__main__":
    generate_synthetic_dataset(
        input_image_path="original_image.jpg",
        output_dir="synthetic_output",
        num_images=200,
        min_ops=3,
        max_ops=6,
        seed=42,
    )
