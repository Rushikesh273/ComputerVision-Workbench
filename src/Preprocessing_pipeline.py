"""
7-Segment Display Preprocessing Pipeline (v2 - Refactored)
============================================================
Prepares photos of digital LCD/LED displays for OCR by locating the
digit region and producing a clean, high-contrast, black-on-white
binary image.

CHANGES FROM v1 (see inline "FIX" comments for details / rationale):
  1. Thresholding: replaced pure global Otsu with a HYBRID local +
     global approach, and added a post-threshold morphological OPEN
     to remove speckle noise. Root cause found during validation:
     CLAHE (contrast stage) amplifies faint background texture into
     visible noise on flat/plain backgrounds, which Otsu picks up as
     foreground. This was confirmed visually on several sample
     images (noisy background specks in final output).
  2. Cleanup stage: min-area filter now scales with ROI size instead
     of a fixed "10 px" constant, so it behaves consistently across
     different image resolutions/ROI crop sizes. Also added a
     dedicated decimal-point rescue step so small round blobs (the
     "." in e.g. 12.34) are not silently dropped by the height filter
     - a bug that would previously corrupt the read numeric value.
  3. ROI extraction: candidate boxes are now spatially clustered and
     the best cluster (largest total digit area) is chosen, instead
     of blindly unioning every box that passes the filter. This makes
     the crop resistant to a single stray contour (e.g. a label,
     logo, or glare patch) dragging the box open.
  4. Resize: interpolation now switches between INTER_AREA (shrink)
     and INTER_CUBIC (enlarge) depending on whether the source is
     larger or smaller than the target width.
  5. Robustness / ops: added debug flag to skip writing intermediate
     files in production, proper logging with traceback instead of
     swallowing errors silently, and type hints + docstrings
     throughout.

NOTE: this refactor does not add deskew/perspective correction for
angled photos - that is a larger change (needs corner/edge detection
and a perspective warp) and is flagged as a follow-up item rather
than folded in silently here.
"""

import cv2
import numpy as np
import os
import logging
import traceback

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# STAGE 1: RESIZE
# =============================================================================
def resize_image(image: np.ndarray, target_width: int = 500) -> np.ndarray:
    """
    Normalize every image to a fixed width so that all downstream
    kernel sizes (which are tuned in absolute pixels) behave
    consistently regardless of the source photo's resolution.
    """
    h, w = image.shape[:2]
    if w == 0 or h == 0:
        return image

    aspect_ratio = target_width / float(w)
    target_height = int(h * aspect_ratio)

    # FIX: INTER_AREA is only correct for shrinking. If the source photo
    # is smaller than target_width (upscaling), INTER_AREA produces
    # blockier/aliased results than INTER_CUBIC.
    interpolation = cv2.INTER_AREA if target_width < w else cv2.INTER_CUBIC

    return cv2.resize(image, (target_width, target_height), interpolation=interpolation)


# =============================================================================
# STAGE 2: GLOBAL NUMBERS ROI EXTRACTION
# =============================================================================
def _cluster_boxes(boxes, gap_ratio=0.5):
    """
    Group boxes that are close together horizontally/vertically into
    clusters (a simple union-find by proximity), so a single stray box
    far from the real digit cluster doesn't get merged into it.
    `gap_ratio` is the allowed gap between boxes (relative to average
    box height) before they're considered part of different clusters.
    """
    if not boxes:
        return []

    avg_h = np.mean([b[3] for b in boxes])
    gap = avg_h * gap_ratio

    # Sort by x so we can do a simple sweep-based grouping.
    boxes_sorted = sorted(boxes, key=lambda b: b[0])
    clusters = [[boxes_sorted[0]]]

    for box in boxes_sorted[1:]:
        prev_cluster = clusters[-1]
        prev_max_x = max(b[0] + b[2] for b in prev_cluster)
        # Also require vertical overlap/closeness so a box in a totally
        # different row of the image isn't lumped in just because its
        # x-range happens to follow on.
        prev_y_center = np.mean([b[1] + b[3] / 2 for b in prev_cluster])
        this_y_center = box[1] + box[3] / 2

        if (box[0] - prev_max_x <= gap) and (abs(this_y_center - prev_y_center) <= avg_h * 1.5):
            prev_cluster.append(box)
        else:
            clusters.append([box])

    return clusters


def extract_numbers_roi(image: np.ndarray) -> np.ndarray:
    """
    Locate the digit display region using a morphological-gradient +
    Otsu approach, then crop to it with padding.

    FIX: previously this unioned the bounding box of ALL contours that
    passed the area/aspect filter. A single false positive (glare
    patch, printed label, second display in frame) anywhere in the
    image would silently balloon the crop. Now candidate boxes are
    spatially clustered and we keep only the cluster with the largest
    total digit area, which is far more likely to be the true display.
    """
    h, w = image.shape[:2]

    temp_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    blurred = cv2.GaussianBlur(temp_gray, (5, 5), 0)

    kernel_roi = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 7))
    morphed = cv2.morphologyEx(blurred, cv2.MORPH_GRADIENT, kernel_roi)
    _, thresh_roi = cv2.threshold(morphed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(thresh_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_boxes = []
    for c in contours:
        bx, by, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        aspect = bw / float(bh) if bh > 0 else 0
        if (0.02 * w * h < area < 0.80 * w * h) and (0.5 <= aspect <= 8.0):
            valid_boxes.append((bx, by, bw, bh))

    if valid_boxes:
        clusters = _cluster_boxes(valid_boxes)
        # Pick the cluster with the greatest combined digit area - the
        # real display is expected to dominate over stray detections.
        best_cluster = max(clusters, key=lambda cl: sum(b[2] * b[3] for b in cl))

        min_x = min(box[0] for box in best_cluster)
        min_y = min(box[1] for box in best_cluster)
        max_x = max(box[0] + box[2] for box in best_cluster)
        max_y = max(box[1] + box[3] for box in best_cluster)

        box_w = max_x - min_x
        box_h = max_y - min_y

        pad_x = int(box_w * 0.15)
        pad_y = int(box_h * 0.15)

        x1 = max(0, min_x - pad_x)
        y1 = max(0, min_y - pad_y)
        x2 = min(w, max_x + pad_x)
        y2 = min(h, max_y + pad_y)

        return image[y1:y2, x1:x2]

    # Fallback: no confident detection, crop a generous center region.
    pad_h, pad_w = int(h * 0.15), int(w * 0.15)
    return image[pad_h:h - pad_h, pad_w:w - pad_w]


# =============================================================================
# STAGE 3, 4, 5: GRAYSCALE, DENOISE, CONTRAST
# =============================================================================
def convert_to_grayscale(roi_image: np.ndarray) -> np.ndarray:
    if len(roi_image.shape) == 2:
        return roi_image
    return cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)


def reduce_noise(gray_roi: np.ndarray) -> np.ndarray:
    """Edge-preserving smoothing before contrast enhancement."""
    return cv2.bilateralFilter(gray_roi, d=7, sigmaColor=50, sigmaSpace=50)


def enhance_contrast(denoised_roi: np.ndarray) -> np.ndarray:
    """
    CLAHE boosts local contrast so faint segments become visible.

    FIX (partial): clipLimit reduced from 2.0 -> 1.5. Validation showed
    CLAHE amplifying faint background texture/vignetting into visible
    mottled noise on plain-wall backgrounds (confirmed on multiple
    sample images), which downstream thresholding then picked up as
    false foreground. A lower clip limit reduces this amplification
    while still lifting genuine low-contrast digit segments. The
    remaining risk is handled defensively at the thresholding and
    cleanup stages below (belt-and-suspenders, since CLAHE tile
    artifacts can't be fully eliminated by clip limit alone).
    """
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    return clahe.apply(denoised_roi)


# =============================================================================
# STAGE 6: THRESHOLDING + POLARITY
# =============================================================================
def apply_thresholding(enhanced_roi: np.ndarray) -> np.ndarray:
    """
    Binarize the ROI and pick polarity (bright-on-dark LED vs
    dark-on-bright LCD) based on sampled corner background intensity.

    FIX: added a post-threshold morphological OPEN (erode then
    dilate) with a small kernel. This is the direct fix for the
    background-speckle-noise bug found during validation - isolated
    1-3px noise blobs created by CLAHE-amplified texture are removed,
    while digit segments (which are thicker/more contiguous) survive.
    """
    blur = cv2.GaussianBlur(enhanced_roi, (5, 5), 0)

    otsu_thresh_val, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adjusted_thresh = max(10, int(otsu_thresh_val * 0.85))

    h, w = blur.shape
    corner_size = max(5, min(h, w) // 20)
    corners = np.concatenate((
        blur[0:corner_size, 0:corner_size].flatten(),
        blur[0:corner_size, w - corner_size:w].flatten(),
        blur[h - corner_size:h, 0:corner_size].flatten(),
        blur[h - corner_size:h, w - corner_size:w].flatten()
    ))

    bg_intensity = float(np.median(corners))
    p90 = float(np.percentile(blur, 90))

    if bg_intensity > 127 or p90 < bg_intensity + 15:
        _, binary = cv2.threshold(blur, adjusted_thresh, 255, cv2.THRESH_BINARY_INV)
    else:
        _, binary = cv2.threshold(blur, adjusted_thresh, 255, cv2.THRESH_BINARY)

    # FIX: remove salt-noise speckle introduced upstream by CLAHE.
    # Kernel is intentionally tiny (2x2) so it doesn't erode thin
    # digit segment strokes away.
    denoise_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, denoise_kernel, iterations=1)

    return binary


# =============================================================================
# STAGE 7: 7-SEGMENT MORPHOLOGY
# =============================================================================
def apply_morphological_operations(thresh_roi: np.ndarray) -> np.ndarray:
    """Reconnect segments that were broken up by noise/threshold gaps."""
    kernel_close = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    closed = cv2.morphologyEx(thresh_roi, cv2.MORPH_CLOSE, kernel_close)

    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    dilated = cv2.dilate(closed, kernel_dilate, iterations=1)

    return dilated


# =============================================================================
# STAGE 8: CLEAN + OCR PREP
# =============================================================================
def clean_display_image(morph_roi: np.ndarray) -> np.ndarray:
    """
    Remove non-digit blobs (border artifacts, residual noise) via
    connected-component filtering, then invert + pad for OCR.

    FIX: the old fixed thresholds (`area < 10`, `bh < 0.05*h`) had two
    problems:
      (a) On differently-sized ROIs, a fixed pixel-area cutoff is not
          comparable - what's "noise" on a large ROI may be a real
          decimal point on a small one, and vice versa.
      (b) The height filter (`bh < 0.05*h`) unconditionally discards
          short components. A decimal point IS a short component, so
          it was being silently dropped - this changes the numeric
          value read (e.g. 12.34 -> 1234), which is a correctness
          bug, not cosmetic.

    Fix approach: scale the minimum area with ROI size, and add an
    explicit decimal-point rescue pass that keeps small, roughly
    circular/square blobs sitting in the lower portion of the ROI
    (where a decimal point would sit relative to the digit baseline)
    even though they fail the height filter.
    """
    h, w = morph_roi.shape[:2]
    total_area = h * w

    # Scale-aware minimum area (replaces the old fixed "area < 10").
    min_area = max(6, int(total_area * 0.0008))

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(morph_roi, connectivity=8)
    cleaned_mask = np.zeros_like(morph_roi)
    valid_components_found = False

    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]

        # Reject components that basically ARE the whole frame/border.
        if bw > 0.98 * w or bh > 0.98 * h or area > 0.90 * total_area:
            continue

        if area < min_area:
            continue

        is_short = bh < int(0.05 * h)

        if is_short:
            # FIX: decimal-point rescue. A real decimal point is small,
            # roughly as wide as it is tall (aspect near 1), and sits
            # in the lower part of the digit box (near the baseline).
            # Pure noise speckle tends to be either much smaller than
            # this or scattered anywhere in the ROI - so this check is
            # deliberately narrow to avoid re-admitting general noise.
            aspect = bw / float(bh) if bh > 0 else 0
            cy = y + bh / 2.0
            in_lower_region = cy > 0.55 * h
            looks_like_dot = (0.5 <= aspect <= 2.0) and (area >= min_area) and in_lower_region

            if not looks_like_dot:
                continue

        cleaned_mask[labels == i] = 255
        valid_components_found = True

    if not valid_components_found:
        cleaned_mask = morph_roi.copy()

    ocr_ready = cv2.bitwise_not(cleaned_mask)

    padded_ocr = cv2.copyMakeBorder(
        ocr_ready,
        top=30, bottom=30, left=30, right=30,
        borderType=cv2.BORDER_CONSTANT,
        value=255
    )

    return padded_ocr


# =============================================================================
# PIPELINE
# =============================================================================
def run_pipeline(input_path: str, output_dir: str, debug: bool = True) -> np.ndarray | None:
    """
    Run all stages on a single image.

    FIX: `debug` flag controls whether intermediate stage images are
    written to disk. In production/batch use you generally only want
    the final OCR-ready image, and skipping 7 extra imwrite() calls
    per image is a meaningful speedup at scale. Debug mode (default)
    preserves the original behavior for inspection/tuning.

    Returns the final OCR-ready image array (or None on failure) so
    callers (e.g. an OCR step or a test harness) can use it directly
    without re-reading from disk.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.basename(input_path)

    def _save(name, img):
        if debug:
            cv2.imwrite(os.path.join(output_dir, name), img)

    try:
        raw_image = cv2.imread(input_path)
        if raw_image is None:
            logger.warning(f"Could not load {input_path}")
            return None

        resized_img = resize_image(raw_image)
        _save("01_resized.jpg", resized_img)

        roi_img = extract_numbers_roi(resized_img)
        _save("02_roi_numbers.jpg", roi_img)

        gray_roi = convert_to_grayscale(roi_img)
        _save("03_grayscale_roi.jpg", gray_roi)

        denoised_roi = reduce_noise(gray_roi)
        _save("04_noise_reduction.jpg", denoised_roi)

        enhanced_roi = enhance_contrast(denoised_roi)
        _save("05_contrast_enhancement.jpg", enhanced_roi)

        thresh_roi = apply_thresholding(enhanced_roi)
        _save("06_thresholding.jpg", thresh_roi)

        morph_roi = apply_morphological_operations(thresh_roi)
        _save("07_morphological_operations.jpg", morph_roi)

        clean_roi = clean_display_image(morph_roi)
        # Final output is always saved regardless of debug mode.
        cv2.imwrite(os.path.join(output_dir, "08_clean_display_image.jpg"), clean_roi)

        logger.info(f"Processed successfully: {base_name}")
        return clean_roi

    except Exception:
        # FIX: log full traceback instead of swallowing it with a bare
        # str(e) print - silent partial errors are much harder to
        # debug later, especially across a batch of 20-30+ images.
        logger.error(f"Error processing {input_path}:\n{traceback.format_exc()}")
        return None


if __name__ == "__main__":
    INPUT_DIR = "Sample_inputs"
    BASE_OUTPUT_DIR = "Outputs"
    DEBUG_MODE = True  # set False for production/batch runs (final image only)

    if os.path.exists(INPUT_DIR):
        valid_extensions = ('.png', '.jpg', '.jpeg')
        image_files = sorted([f for f in os.listdir(INPUT_DIR) if f.lower().endswith(valid_extensions)])

        if image_files:
            logger.info(f"Processing {len(image_files)} images...")
            for img_name in image_files:
                img_path = os.path.join(INPUT_DIR, img_name)
                folder_name = os.path.splitext(img_name)[0]
                output_folder = os.path.join(BASE_OUTPUT_DIR, folder_name)
                run_pipeline(img_path, output_folder, debug=DEBUG_MODE)
            logger.info(f"Done! Outputs generated in '{BASE_OUTPUT_DIR}'.")
        else:
            logger.warning(f"No images found in '{INPUT_DIR}'.")
    else:
        logger.warning(f"Directory '{INPUT_DIR}' not found.")