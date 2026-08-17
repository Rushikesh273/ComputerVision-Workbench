"""
crop_display.py
================
Builds a single contact-sheet image out of the crops that display_detector.py
already produced, so Task 3 (manually reviewing crops -- is the whole display
captured? is there extra background? is it cut off?) can be done by scanning
one image instead of opening every file in output/ individually.

Run display_detector.py first. This script does not run the model itself --
it just reads what display_detector.py already wrote.

Usage:
    python crop_display.py

Expects, relative to this script (same folder display_detector.py writes to):
    output/*_crop.jpg        -- crop images produced by display_detector.py
    output/review_log.csv    -- filename, confidence, flags -- also written by
                                 display_detector.py

Output:
    output/contact_sheet.jpg -- grid of every crop, each labeled with filename,
                                 confidence, and flags (flagged ones shown in red)
"""

import csv
import math
import os

import cv2
import numpy as np

# ---------------- settings ----------------
OUTPUT_DIR = "output"
REVIEW_LOG = os.path.join(OUTPUT_DIR, "review_log.csv")
CONTACT_SHEET_PATH = os.path.join(OUTPUT_DIR, "contact_sheet.jpg")

THUMB_W, THUMB_H = 220, 160   # every crop is resized to this so the grid is uniform
COLS = 5
LABEL_HEIGHT = 40
PAD = 6
BG_COLOR = (30, 30, 30)
TEXT_COLOR = (255, 255, 255)   # white
FLAG_COLOR = (0, 0, 255)       # red (BGR) -- flagged crops get their text in red


def load_review_log(path):
    """filename -> {'confidence': ..., 'flags': ...}"""
    log = {}
    if not os.path.exists(path):
        print(f"[!] '{path}' not found -- contact sheet will show crops without "
              f"confidence/flag labels. Run display_detector.py first for full labels.")
        return log
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            log[row["filename"]] = row
    return log


def find_log_row(log, crop_stem):
    """Match a '<name>_crop.jpg' file back to its original filename's log row."""
    for orig_name, row in log.items():
        if os.path.splitext(orig_name)[0] == crop_stem:
            return row
    return None


def make_thumbnail(crop_path):
    img = cv2.imread(crop_path)
    if img is None:
        return np.full((THUMB_H, THUMB_W, 3), BG_COLOR, dtype=np.uint8)
    h, w = img.shape[:2]
    scale = min(THUMB_W / w, THUMB_H / h)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(img, (new_w, new_h))
    canvas = np.full((THUMB_H, THUMB_W, 3), BG_COLOR, dtype=np.uint8)
    y_off, x_off = (THUMB_H - new_h) // 2, (THUMB_W - new_w) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    return canvas


def make_cell(crop_path, filename, confidence, flags):
    thumb = make_thumbnail(crop_path)
    cell = np.full((THUMB_H + LABEL_HEIGHT, THUMB_W, 3), BG_COLOR, dtype=np.uint8)
    cell[:THUMB_H, :] = thumb

    is_flagged = bool(flags) and flags != "OK"
    text_color = FLAG_COLOR if is_flagged else TEXT_COLOR

    name_line = filename if len(filename) <= 22 else filename[:19] + "..."
    conf_line = f"conf {confidence}" if confidence else "conf n/a"
    flag_line = flags if flags else "OK"
    if len(flag_line) > 28:
        flag_line = flag_line[:25] + "..."

    cv2.putText(cell, name_line, (4, THUMB_H + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.38, TEXT_COLOR, 1)
    cv2.putText(cell, conf_line, (4, THUMB_H + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.38, TEXT_COLOR, 1)
    cv2.putText(cell, flag_line, (4, THUMB_H + 38), cv2.FONT_HERSHEY_SIMPLEX, 0.36, text_color, 1)
    return cell, is_flagged


def main():
    if not os.path.isdir(OUTPUT_DIR):
        print(f"[!] '{OUTPUT_DIR}/' not found -- run display_detector.py first.")
        return

    crop_files = sorted(
        f for f in os.listdir(OUTPUT_DIR)
        if f.lower().endswith("_crop.jpg") or f.lower().endswith("_crop.png")
    )
    if not crop_files:
        print(f"[!] No crop images found in '{OUTPUT_DIR}/' -- run display_detector.py first.")
        return

    log = load_review_log(REVIEW_LOG)

    cells = []
    n_flagged = 0
    for crop_file in crop_files:
        stem = crop_file.rsplit("_crop", 1)[0]
        row = find_log_row(log, stem)
        confidence = row["confidence"] if row else ""
        flags = row["flags"] if row else ""

        cell, is_flagged = make_cell(os.path.join(OUTPUT_DIR, crop_file), crop_file, confidence, flags)
        cells.append(cell)
        if is_flagged:
            n_flagged += 1

    cell_h, cell_w = cells[0].shape[:2]
    rows = math.ceil(len(cells) / COLS)
    sheet_w = COLS * cell_w + (COLS + 1) * PAD
    sheet_h = rows * cell_h + (rows + 1) * PAD
    sheet = np.full((sheet_h, sheet_w, 3), BG_COLOR, dtype=np.uint8)

    for i, cell in enumerate(cells):
        r, c = divmod(i, COLS)
        y = PAD + r * (cell_h + PAD)
        x = PAD + c * (cell_w + PAD)
        sheet[y:y + cell_h, x:x + cell_w] = cell

    cv2.imwrite(CONTACT_SHEET_PATH, sheet)
    print(f"Built contact sheet with {len(cells)} crop(s) -> '{CONTACT_SHEET_PATH}'")
    print(f"({n_flagged} flagged for manual review -- shown in red)")


if __name__ == "__main__":
    main()
