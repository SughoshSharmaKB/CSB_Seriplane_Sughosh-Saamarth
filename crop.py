import os
import cv2
import numpy as np
from PIL import Image

# ===================== USER SETTINGS =====================
INPUT_DIR  = "./data"      # folder with original images
OUTPUT_DIR = "./preprocessed"     # folder to save results

smooth_kernel = 31               # odd number
min_height_px = 8                # minimum height of a valid strip
padding_px = 6                   # padding above & below strip
max_strips = 2                   # expected strips per image

use_manual_threshold = True
manual_thr_value = 65             # brightness threshold

target_width = 1100              # final width after rotate+resize
rotate_clockwise = True          # True = -90°, False = +90°
# ========================================================

VALID_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

os.makedirs(OUTPUT_DIR, exist_ok=True)

def process_image(image_path):
    filename = os.path.basename(image_path)
    name, ext = os.path.splitext(filename)

    if ext.lower() not in VALID_EXTS:
        return

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        print(f"[WARN] Cannot read {filename}")
        return

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    H, W = img_rgb.shape[:2]
    print(f"\nProcessing: {filename} ({W}x{H})")

    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

    # ---- ROW AVERAGING ----
    row_mean = gray.mean(axis=1).astype(np.float32)

    k = smooth_kernel if smooth_kernel % 2 == 1 else smooth_kernel + 1
    row_smooth = cv2.GaussianBlur(row_mean.reshape(-1, 1), (1, k), 0).flatten()

    # ---- THRESHOLD ----
    if use_manual_threshold:
        thr = manual_thr_value
    else:
        thr = row_smooth.mean() + 0.6 * row_smooth.std()

    bright_rows = np.where(row_smooth > thr)[0]

    if len(bright_rows) == 0:
        print("  No bright rows found — skipping")
        return

    # ---- GROUP ROWS INTO STRIPS ----
    splits = np.where(np.diff(bright_rows) != 1)[0] + 1
    bands = np.split(bright_rows, splits)

    valid = []
    for b in bands:
        if len(b) >= min_height_px:
            valid.append((b[0], b[-1], len(b)))

    if not valid:
        print("  No valid horizontal strips — skipping")
        return

    # Keep largest strips
    valid = sorted(valid, key=lambda x: x[2], reverse=True)[:max_strips]
    valid = sorted(valid, key=lambda x: x[0])

    # ---- PROCESS EACH STRIP ----
    for idx, (y0, y1, _) in enumerate(valid, start=1):
        yy0 = max(0, y0 - padding_px)
        yy1 = min(H, y1 + padding_px + 1)

        crop = img_rgb[yy0:yy1, :]

        pil_img = Image.fromarray(crop)

        angle = -90 if rotate_clockwise else 90
        rot = pil_img.rotate(angle, expand=True)

        w, h = rot.size
        scale = target_width / w
        new_h = int(h * scale)
        resized = rot.resize((target_width, new_h), Image.LANCZOS)

        out_name = f"{name}_{idx}{ext}"
        out_path = os.path.join(OUTPUT_DIR, out_name)
        resized.save(out_path)

        print(f"  Saved → {out_name} ({target_width}x{new_h})")


def main():
    files = sorted(os.listdir(INPUT_DIR))
    print(f"Found {len(files)} files in '{INPUT_DIR}'")

    for f in files:
        path = os.path.join(INPUT_DIR, f)
        if os.path.isfile(path):
            process_image(path)

    print("\n✅ DONE")
    print("Input folder :", INPUT_DIR)
    print("Output folder:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
