import cv2
import numpy as np
import os


# =============================================================================
# STAGE 1: RESIZE
# =============================================================================
def resize_image(image: np.ndarray, target_width: int = 500) -> np.ndarray:
    h, w = image.shape[:2]
    if w == 0 or h == 0:
        return image
    aspect_ratio = target_width / float(w)
    target_height = int(h * aspect_ratio)
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


# =============================================================================
# STAGE 2: GLOBAL NUMBERS ROI EXTRACTION
# =============================================================================
def extract_numbers_roi(image: np.ndarray):
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
        min_x = min([box[0] for box in valid_boxes])
        min_y = min([box[1] for box in valid_boxes])
        max_x = max([box[0] + box[2] for box in valid_boxes])
        max_y = max([box[1] + box[3] for box in valid_boxes])

        box_w = max_x - min_x
        box_h = max_y - min_y

        pad_x = int(box_w * 0.15)
        pad_y = int(box_h * 0.15)

        x1 = max(0, min_x - pad_x)
        y1 = max(0, min_y - pad_y)
        x2 = min(w, max_x + pad_x)
        y2 = min(h, max_y + pad_y)

        return image[y1:y2, x1:x2]

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
    return cv2.bilateralFilter(gray_roi, d=7, sigmaColor=50, sigmaSpace=50)


def enhance_contrast(denoised_roi: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(denoised_roi)


# =============================================================================
# STAGE 6: THRESHOLDING + POLARITY (fixed indentation + better decision)
# =============================================================================
def apply_thresholding(enhanced_roi: np.ndarray) -> np.ndarray:
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

    # Bright background (LCD) OR weak contrast → invert so digits become white
    if bg_intensity > 127 or p90 < bg_intensity + 15:
        _, binary = cv2.threshold(blur, adjusted_thresh, 255, cv2.THRESH_BINARY_INV)
    else:
        # Dark background (LED) → bright digits become white
        _, binary = cv2.threshold(blur, adjusted_thresh, 255, cv2.THRESH_BINARY)

    return binary


# =============================================================================
# STAGE 7: 7-SEGMENT MORPHOLOGY
# =============================================================================
def apply_morphological_operations(thresh_roi: np.ndarray) -> np.ndarray:
    kernel_close = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    closed = cv2.morphologyEx(thresh_roi, cv2.MORPH_CLOSE, kernel_close)

    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    dilated = cv2.dilate(closed, kernel_dilate, iterations=1)

    return dilated


# =============================================================================
# STAGE 8: CLEAN + OCR PREP
# =============================================================================
def clean_display_image(morph_roi: np.ndarray) -> np.ndarray:
    h, w = morph_roi.shape[:2]
    total_area = h * w

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(morph_roi, connectivity=8)
    cleaned_mask = np.zeros_like(morph_roi)
    valid_components_found = False

    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]

        if bw > 0.98 * w or bh > 0.98 * h or area > 0.90 * total_area:
            continue

        if bh < int(0.05 * h) or area < 10:
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
def run_pipeline(input_path: str, output_dir: str):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.basename(input_path)

    try:
        raw_image = cv2.imread(input_path)
        if raw_image is None:
            print(f"  [!] Could not load {input_path}")
            return

        resized_img = resize_image(raw_image)
        cv2.imwrite(os.path.join(output_dir, "01_resized.jpg"), resized_img)

        roi_img = extract_numbers_roi(resized_img)
        cv2.imwrite(os.path.join(output_dir, "02_roi_numbers.jpg"), roi_img)

        gray_roi = convert_to_grayscale(roi_img)
        cv2.imwrite(os.path.join(output_dir, "03_grayscale_roi.jpg"), gray_roi)

        denoised_roi = reduce_noise(gray_roi)
        cv2.imwrite(os.path.join(output_dir, "04_noise_reduction.jpg"), denoised_roi)

        enhanced_roi = enhance_contrast(denoised_roi)
        cv2.imwrite(os.path.join(output_dir, "05_contrast_enhancement.jpg"), enhanced_roi)

        thresh_roi = apply_thresholding(enhanced_roi)
        cv2.imwrite(os.path.join(output_dir, "06_thresholding.jpg"), thresh_roi)

        morph_roi = apply_morphological_operations(thresh_roi)
        cv2.imwrite(os.path.join(output_dir, "07_morphological_operations.jpg"), morph_roi)

        clean_roi = clean_display_image(morph_roi)
        cv2.imwrite(os.path.join(output_dir, "08_clean_display_image.jpg"), clean_roi)

        print(f" -> Processed successfully: {base_name}")

    except Exception as e:
        print(f" [!] Error processing {input_path}: {e}")


if __name__ == "__main__":
    INPUT_DIR = "Sample_inputs"
    BASE_OUTPUT_DIR = "Outputs"

    if os.path.exists(INPUT_DIR):
        valid_extensions = ('.png', '.jpg', '.jpeg')
        image_files = sorted([f for f in os.listdir(INPUT_DIR) if f.lower().endswith(valid_extensions)])

        if image_files:
            print(f"Processing {len(image_files)} images...\n" + "-" * 50)
            for img_name in image_files:
                img_path = os.path.join(INPUT_DIR, img_name)
                folder_name = os.path.splitext(img_name)[0]
                output_folder = os.path.join(BASE_OUTPUT_DIR, folder_name)
                run_pipeline(img_path, output_folder)
            print("-" * 50 + f"\nDone! Outputs generated in '{BASE_OUTPUT_DIR}'.")
        else:
            print(f"No images found in '{INPUT_DIR}'.")
    else:
        print(f"Directory '{INPUT_DIR}' not found.")