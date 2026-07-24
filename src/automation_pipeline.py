"""
automation_pipeline.py  (Final Version — Week 1, Friday)

Automates end-to-end synthetic dataset generation for the Computer-Vision-
Workbench project: reads every image from an input folder, generates
randomized augmented variations of each, and validates the resulting
dataset before it's considered done.

--------------------------------------------------------------------------
PIPELINE STAGES
--------------------------------------------------------------------------
1. Discover   - scan the input folder, sort files into valid / corrupted /
                non-image, without processing anything yet.
2. Generate   - for each valid image, generate a randomized number of
                augmented variations (random subset of 8 techniques, each
                with randomized parameters), auto-named and saved.
3. Validate   - after generation, independently re-check the OUTPUT folder
                for exact duplicate images, correct file naming, and
                correct folder structure. This is a genuine post-hoc check,
                not just a re-statement of the generation logic.

--------------------------------------------------------------------------
AUGMENTATION TECHNIQUES (8 total, applied in a randomized subset per image)
--------------------------------------------------------------------------
Geometric   : rotation (+/-5 deg), scaling, perspective warp
Photometric : brightness, contrast
Degradation : gaussian blur, motion blur, gaussian noise

See docs/week2_documentation.md for what each one does and why it's
relevant to this project.

--------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------
    python automation_pipeline.py
    python automation_pipeline.py --input data/input_images --output data/synthetic_dataset --total 1000
    python automation_pipeline.py --help

Fully standalone: only depends on OpenCV, NumPy, and the Python standard
library — no other project file needs to be present for this to run.
"""

from __future__ import annotations

import os
import sys
import csv
import re
import time
import random
import hashlib
import argparse
from dataclasses import dataclass, field

import numpy as np
import cv2

SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")

# Expected output filename pattern: <source_stem>_var<3 digits>.jpg
# e.g. "1236_263_var047.jpg" -- used by the naming validation check.
NAMING_PATTERN = re.compile(r"^.+_var\d{3}\.jpg$")


# ==========================================================================
# 1. Image I/O (safe read/write, never crashes the pipeline on a bad file)
# ==========================================================================

def read_image_safe(path: str):
    """
    Attempt to read an image from disk.
    Returns (image, None) on success, or (None, "reason") on failure.
    Deliberately never raises -- a single bad file must not crash a run
    that's processing hundreds of others.
    """
    try:
        if os.path.getsize(path) == 0:
            return None, "file is empty (0 bytes)"
    except OSError as e:
        return None, f"could not access file ({e})"

    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        return None, "could not decode image (corrupted or invalid image data)"
    if img.size == 0 or img.shape[0] < 2 or img.shape[1] < 2:
        return None, "decoded image has invalid/degenerate dimensions"
    return img, None


def save_image(img: np.ndarray, path: str) -> None:
    """Save an image to disk, creating the destination folder if needed."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cv2.imwrite(path, img)


# ==========================================================================
# 2. Augmentation techniques (the 8 building blocks)
# ==========================================================================

def adjust_brightness(img: np.ndarray, value: int) -> np.ndarray:
    """Shift every pixel's intensity up (value > 0) or down (value < 0)."""
    return cv2.convertScaleAbs(img, alpha=1.0, beta=value)


def adjust_contrast(img: np.ndarray, alpha: float) -> np.ndarray:
    """Scale pixel intensities: alpha > 1 increases contrast, < 1 decreases it."""
    return cv2.convertScaleAbs(img, alpha=alpha, beta=0)


def gaussian_blur(img: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """Soft, natural blur -- simulates a slightly out-of-focus camera."""
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)


def motion_blur(img: np.ndarray, kernel_size: int = 15, angle: float = 0) -> np.ndarray:
    """Directional smear -- simulates camera or display movement during capture."""
    kernel = np.zeros((kernel_size, kernel_size))
    kernel[kernel_size // 2, :] = np.ones(kernel_size)
    rot_matrix = cv2.getRotationMatrix2D(
        (kernel_size / 2 - 0.5, kernel_size / 2 - 0.5), angle, 1
    )
    kernel = cv2.warpAffine(kernel, rot_matrix, (kernel_size, kernel_size))
    kernel = kernel / kernel.sum()
    return cv2.filter2D(img, -1, kernel)


def add_gaussian_noise(img: np.ndarray, mean: float = 0, sigma: float = 25) -> np.ndarray:
    """Grainy sensor-style noise -- simulates low-light camera footage."""
    noise = np.random.normal(mean, sigma, img.shape).astype(np.float32)
    noisy = img.astype(np.float32) + noise
    return np.clip(noisy, 0, 255).astype(np.uint8)


def rotate_image(img: np.ndarray, angle: float) -> np.ndarray:
    """Rotate around the image center by `angle` degrees; keeps original size."""
    h, w = img.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)


def scale_image(img: np.ndarray, scale_factor: float) -> np.ndarray:
    """Scale up/down, then crop or pad back to the original size."""
    h, w = img.shape[:2]
    new_w, new_h = max(1, int(w * scale_factor)), max(1, int(h * scale_factor))
    scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros_like(img)
    if scale_factor >= 1.0:
        y0, x0 = max(0, (new_h - h) // 2), max(0, (new_w - w) // 2)
        canvas[:, :] = scaled[y0:y0 + h, x0:x0 + w]
    else:
        y0, x0 = (h - new_h) // 2, (w - new_w) // 2
        canvas[y0:y0 + new_h, x0:x0 + new_w] = scaled
    return canvas


def perspective_transform(img: np.ndarray, strength: float = 0.05) -> np.ndarray:
    """Nudge each of the 4 corners randomly -- simulates a non-straight-on camera angle."""
    h, w = img.shape[:2]
    max_dx, max_dy = int(w * strength), int(h * strength)
    src = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    dst = np.float32([
        [random.randint(-max_dx, max_dx), random.randint(-max_dy, max_dy)],
        [w + random.randint(-max_dx, max_dx), random.randint(-max_dy, max_dy)],
        [random.randint(-max_dx, max_dx), h + random.randint(-max_dy, max_dy)],
        [w + random.randint(-max_dx, max_dx), h + random.randint(-max_dy, max_dy)],
    ])
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)


# Applied in this fixed order when multiple are chosen: geometry -> lighting -> degradation.
AUGMENTATION_ORDER = [
    "rotation", "scaling", "perspective",
    "brightness", "contrast",
    "gaussian_blur", "motion_blur", "gaussian_noise",
]


def apply_random_augmentations(img: np.ndarray, min_ops: int = 3, max_ops: int = 6):
    """
    Apply a random subset (min_ops..max_ops) of the 8 techniques above, each
    with randomized parameters. Returns (augmented_image, log) where `log`
    is a list of strings recording exactly what was applied -- this log is
    what makes each generated image traceable and provably unique.
    """
    n_ops = random.randint(min_ops, max_ops)
    chosen = sorted(random.sample(AUGMENTATION_ORDER, n_ops), key=AUGMENTATION_ORDER.index)

    result = img.copy()
    log = []
    for op in chosen:
        if op == "brightness":
            v = random.randint(-50, 50)
            result = adjust_brightness(result, v)
            log.append(f"brightness({v:+d})")
        elif op == "contrast":
            a = round(random.uniform(0.6, 1.6), 2)
            result = adjust_contrast(result, a)
            log.append(f"contrast(alpha={a})")
        elif op == "gaussian_noise":
            s = random.randint(10, 35)
            result = add_gaussian_noise(result, sigma=s)
            log.append(f"gaussian_noise(sigma={s})")
        elif op == "motion_blur":
            k = random.choice([9, 13, 17, 21])
            ang = random.randint(0, 179)
            result = motion_blur(result, kernel_size=k, angle=ang)
            log.append(f"motion_blur(k={k},angle={ang})")
        elif op == "gaussian_blur":
            k = random.choice([3, 5, 7, 9])
            result = gaussian_blur(result, k)
            log.append(f"gaussian_blur(k={k})")
        elif op == "rotation":
            ang = round(random.uniform(-5, 5), 1)
            result = rotate_image(result, ang)
            log.append(f"rotation({ang:+}deg)")
        elif op == "scaling":
            sc = round(random.uniform(0.85, 1.15), 2)
            result = scale_image(result, sc)
            log.append(f"scaling(x{sc})")
        elif op == "perspective":
            st = round(random.uniform(0.02, 0.08), 3)
            result = perspective_transform(result, st)
            log.append(f"perspective(strength={st})")
    return result, log


# ==========================================================================
# 3. Progress display + logging
# ==========================================================================

def print_progress(current: int, total: int, prefix: str = "") -> None:
    """In-place terminal progress bar (updates one line instead of scrolling)."""
    bar_len = 30
    filled = int(bar_len * current / total) if total else bar_len
    bar = "#" * filled + "-" * (bar_len - filled)
    pct = (current / total * 100) if total else 100
    sys.stdout.write(f"\r{prefix} [{bar}] {current}/{total} ({pct:5.1f}%)")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")


class PipelineLogger:
    """Writes timestamped log lines to both the console and a persistent log file."""

    def __init__(self, log_path: str):
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        self.log_path = log_path
        self._fh = open(log_path, "w")

    def log(self, message: str, also_print: bool = True) -> None:
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        self._fh.write(line + "\n")
        self._fh.flush()
        if also_print:
            print(line)

    def close(self) -> None:
        self._fh.close()


@dataclass
class RunStats:
    """Simple record of how a generation run went, used for the final summary."""
    valid_images: int = 0
    corrupted_files: list = field(default_factory=list)
    non_image_files: list = field(default_factory=list)
    generated_count: int = 0


# ==========================================================================
# 4. Stage 1 + 2: Discover input files, then generate the dataset
# ==========================================================================

def discover_inputs(input_dir: str, logger: PipelineLogger):
    """Scan the input folder once and sort every file into valid / corrupted / non-image."""
    all_files = sorted(os.listdir(input_dir))
    logger.log(f"Found {len(all_files)} file(s) in input folder")

    valid_images, corrupted, non_image = [], [], []
    for fname in all_files:
        fpath = os.path.join(input_dir, fname)
        if not os.path.isfile(fpath):
            continue
        if not fname.lower().endswith(SUPPORTED_EXTENSIONS):
            non_image.append(fname)
            logger.log(f"SKIP  {fname} -- not a supported image extension")
            continue
        img, error = read_image_safe(fpath)
        if error:
            corrupted.append((fname, error))
            logger.log(f"ERROR {fname} -- {error} (skipped)")
            continue
        valid_images.append((fname, fpath))

    logger.log(
        f"Discovery complete: {len(valid_images)} valid, {len(corrupted)} corrupted/invalid, "
        f"{len(non_image)} non-image files skipped"
    )
    return valid_images, corrupted, non_image


def generate_dataset(valid_images, images_dir: str, total_images: int,
                      min_ops: int, max_ops: int, logger: PipelineLogger):
    """
    Generate `total_images` synthetic variations, spread as evenly as possible
    across every valid source image, and write a manifest.csv describing
    exactly what was applied to each output file.
    """
    os.makedirs(images_dir, exist_ok=True)
    n_sources = len(valid_images)
    base_count = total_images // n_sources
    remainder = total_images % n_sources  # first `remainder` sources get one extra

    manifest_rows = []
    generated = 0
    print()

    for idx, (fname, fpath) in enumerate(valid_images):
        img, _ = read_image_safe(fpath)  # already validated during discovery
        target_for_this_image = base_count + (1 if idx < remainder else 0)
        stem = os.path.splitext(fname)[0]

        seen_signatures = set()
        made = 0
        attempts = 0
        while made < target_for_this_image:
            attempts += 1
            augmented, log = apply_random_augmentations(img, min_ops, max_ops)
            signature = ";".join(log)
            if signature in seen_signatures:
                continue  # duplicate combination -- retry
            seen_signatures.add(signature)

            out_name = f"{stem}_var{made:03d}.jpg"
            save_image(augmented, os.path.join(images_dir, out_name))
            manifest_rows.append([out_name, fname, "; ".join(log)])

            made += 1
            generated += 1
            print_progress(generated, total_images, prefix="Generating")

        logger.log(
            f"OK    {fname} -- generated {made}/{target_for_this_image} variations "
            f"({attempts} attempts)", also_print=False
        )

    return manifest_rows, generated


# ==========================================================================
# 5. Stage 3: Post-generation validation
# ==========================================================================

def validate_dataset(images_dir: str, manifest_path: str, output_dir: str, logger: PipelineLogger):
    """
    Independently re-check the generated dataset on disk (not just trust the
    generation-time logic). Three checks, each written to the validation report:
      1. No duplicate images (exact pixel-content hash comparison)
      2. Proper file naming (matches the <source>_var###.jpg pattern)
      3. Correct folder organization (expected files/folders all present)
    """
    logger.log("")
    logger.log("=== VALIDATION ===")
    report_lines = []

    files = sorted(f for f in os.listdir(images_dir) if f.lower().endswith(".jpg"))

    # --- Check 1: exact duplicate images (hash of pixel content, not just filename) ---
    hashes = {}
    duplicates = []
    for fname in files:
        img = cv2.imread(os.path.join(images_dir, fname))
        if img is None:
            continue
        digest = hashlib.md5(img.tobytes()).hexdigest()
        if digest in hashes:
            duplicates.append((fname, hashes[digest]))
        else:
            hashes[digest] = fname

    dup_status = "PASS" if not duplicates else "FAIL"
    report_lines.append(f"[{dup_status}] Duplicate check: {len(duplicates)} duplicate(s) found "
                         f"out of {len(files)} images")
    for a, b in duplicates:
        report_lines.append(f"         duplicate: {a}  ==  {b}")

    # --- Check 2: naming convention ---
    bad_names = [f for f in files if not NAMING_PATTERN.match(f)]
    name_status = "PASS" if not bad_names else "FAIL"
    report_lines.append(f"[{name_status}] Naming check: {len(bad_names)} file(s) don't match "
                         f"'<source>_var###.jpg'")
    for f in bad_names[:10]:
        report_lines.append(f"         bad name: {f}")

    # --- Check 3: folder organization ---
    expected = {
        "images/ folder exists": os.path.isdir(images_dir),
        "manifest.csv exists": os.path.isfile(manifest_path),
        "images/ is non-empty": len(files) > 0,
    }
    struct_status = "PASS" if all(expected.values()) else "FAIL"
    report_lines.append(f"[{struct_status}] Folder structure check:")
    for label, ok in expected.items():
        report_lines.append(f"         [{'OK' if ok else 'MISSING'}] {label}")

    # --- Basic image-quality check (catch blank/degenerate outputs) ---
    low_quality = []
    for fname in files:
        img = cv2.imread(os.path.join(images_dir, fname))
        if img is None or img.std() < 1.0:
            low_quality.append(fname)
    quality_status = "PASS" if not low_quality else "WARN"
    report_lines.append(f"[{quality_status}] Image quality check: {len(low_quality)} "
                         f"near-blank/degenerate image(s) out of {len(files)}")

    report_lines.append("")
    report_lines.append(f"Total images validated: {len(files)}")
    overall = "PASS" if not duplicates and not bad_names and struct_status == "PASS" else "FAIL"
    report_lines.append(f"OVERALL: {overall}")

    for line in report_lines:
        logger.log(line, also_print=False)

    report_path = os.path.join(output_dir, "validation_report.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines) + "\n")

    print("\n".join(report_lines))
    logger.log(f"Validation report saved to '{report_path}'")
    return overall == "PASS"


# ==========================================================================
# 6. Orchestration
# ==========================================================================

def run_pipeline(input_dir: str, output_dir: str, total_images: int = 1000,
                  min_ops: int = 3, max_ops: int = 6, seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)

    images_dir = os.path.join(output_dir, "images")
    logger = PipelineLogger(os.path.join(output_dir, "pipeline_log.txt"))
    logger.log(f"Pipeline started. input_dir='{input_dir}', output_dir='{output_dir}', "
               f"total_images={total_images}, seed={seed}")

    valid_images, corrupted, non_image = discover_inputs(input_dir, logger)
    if not valid_images:
        logger.log("No valid images to process. Exiting.")
        logger.close()
        return

    manifest_rows, generated = generate_dataset(
        valid_images, images_dir, total_images, min_ops, max_ops, logger
    )

    manifest_path = os.path.join(output_dir, "manifest.csv")
    with open(manifest_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["output_filename", "source_image", "augmentations_applied"])
        writer.writerows(manifest_rows)

    logger.log("")
    logger.log("=== GENERATION SUMMARY ===")
    logger.log(f"Valid source images processed  : {len(valid_images)}")
    logger.log(f"Corrupted/invalid files skipped: {len(corrupted)}"
               + (f" -> {[f for f, _ in corrupted]}" if corrupted else ""))
    logger.log(f"Non-image files skipped        : {len(non_image)}"
               + (f" -> {non_image}" if non_image else ""))
    logger.log(f"Total synthetic images generated: {generated}")
    logger.log(f"Manifest                        : {manifest_path}")

    validate_dataset(images_dir, manifest_path, output_dir, logger)
    logger.close()

    print(f"\nDone. {generated} images generated from {len(valid_images)} valid source images.")
    print(f"See '{output_dir}/pipeline_log.txt' and '{output_dir}/validation_report.txt' for full details.")


def main():
    parser = argparse.ArgumentParser(description="Generate a validated synthetic image dataset.")
    parser.add_argument("--input", default="data/input_images", help="Folder of source images")
    parser.add_argument("--output", default="data/synthetic_dataset", help="Folder to write results into")
    parser.add_argument("--total", type=int, default=1000, help="Total number of images to generate")
    parser.add_argument("--min-ops", type=int, default=3, help="Minimum augmentations applied per image")
    parser.add_argument("--max-ops", type=int, default=6, help="Maximum augmentations applied per image")
    parser.add_argument("--seed", type=int, default=42, help="Random seed, for reproducible runs")
    args = parser.parse_args()

    run_pipeline(
        input_dir=args.input,
        output_dir=args.output,
        total_images=args.total,
        min_ops=args.min_ops,
        max_ops=args.max_ops,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
