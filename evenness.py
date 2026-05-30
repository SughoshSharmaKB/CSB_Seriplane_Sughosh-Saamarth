import os
import glob
import cv2
import numpy as np
import pandas as pd
from scipy import stats

# ============================
# USER CONFIG
# ============================
folder_path = r"preprocessed"   # <-- CHANGE ME: folder with images
output_csv = "results/evenness.csv"
output_image_dir = "results/evenness"

# analysis parameters (same as your final code)
column_width = 15
window_size = 5
v1_threshold = 5
v2_threshold = 8
v3_threshold = 11
min_cols_for_defect = 8

# create output dir
os.makedirs(output_image_dir, exist_ok=True)

# colors for drawing (BGR)
colors = {
    'v1': (0, 255, 0),       # Bright Green
    'v2': (0, 165, 255),     # Bright Orange
    'v3': (0, 0, 255)        # Bright Red
}
priority = {'v1': 1, 'v2': 2, 'v3': 3}


def classify(dev):
    """Classify by deviation percentage into v1 / v2 / v3."""
    abs_dev = abs(dev)
    if abs_dev >= v3_threshold:
        return 'v3'
    elif abs_dev >= v2_threshold:
        return 'v2'
    elif abs_dev >= v1_threshold:
        return 'v1'
    else:
        return None


def compute_regions_from_comparator(local_means, comparator_value, num_cols, min_cols):
    """
    Given local_means and a comparator (global mean or mode),
    compute final merged regions + class counts, following your logic.
    Returns (final_regions, class_counts).
    """
    eps = 1e-8
    deviation_percent = ((local_means - comparator_value) / (comparator_value + eps)) * 100

    # classify columns
    column_classes = [classify(dev) for dev in deviation_percent]

    # merge adjacent same-class into regions
    regions = []
    start = None
    current_class = None
    for i in range(num_cols):
        c = column_classes[i]
        if c != current_class:
            if current_class is not None:
                regions.append((start, i - 1, current_class))
            start = i if c is not None else None
            current_class = c
    if current_class is not None:
        regions.append((start, num_cols - 1, current_class))

    # keep regions with length >= min_cols
    filtered_regions = [
        (start, end, cls)
        for start, end, cls in regions
        if (end - start + 1) >= min_cols
    ]

    # overlap resolution by priority
    final_classes = [None] * num_cols
    for start, end, cls in filtered_regions:
        for i in range(start, end + 1):
            if final_classes[i] is None or priority[cls] > priority.get(final_classes[i], 0):
                final_classes[i] = cls

    # rebuild regions from final_classes
    final_regions = []
    start = None
    current_class = None
    for i in range(num_cols):
        c = final_classes[i]
        if c != current_class:
            if current_class is not None:
                final_regions.append((start, i - 1, current_class))
            start = i if c is not None else None
            current_class = c
    if current_class is not None:
        final_regions.append((start, num_cols - 1, current_class))

    # merge nearby boxes if gap < min_cols, keep wider class
    merged_regions = []
    i = 0
    while i < len(final_regions):
        start1, end1, cls1 = final_regions[i]
        width1 = end1 - start1 + 1

        j = i + 1
        while j < len(final_regions):
            start2, end2, cls2 = final_regions[j]
            width2 = end2 - start2 + 1
            gap = start2 - end1 - 1

            if gap < min_cols:
                # choose class with larger width
                chosen_class = cls1 if width1 >= width2 else cls2
                end1 = end2
                cls1 = chosen_class
                width1 = end1 - start1 + 1
                j += 1
            else:
                break

        merged_regions.append((start1, end1, cls1))
        i = j

    # count classes
    class_counts = {'v1': 0, 'v2': 0, 'v3': 0}
    for _, _, cls in merged_regions:
        if cls is not None:
            class_counts[cls] += 1

    return merged_regions, class_counts, deviation_percent


def process_image(img_path):
    """Run the full pipeline on a single image and return summary + save images."""
    img_name = os.path.basename(img_path)
    img = cv2.imread(img_path)
    if img is None:
        print(f"Could not read {img_path}, skipping.")
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # column means
    num_cols = w // column_width
    if num_cols <= 0:
        print(f"Image {img_name}: column_width too large, skipping.")
        return None

    column_means = []
    for i in range(num_cols):
        start = i * column_width
        end = min((i + 1) * column_width, w)
        block = gray[:, start:end]
        column_means.append(np.mean(block))
    column_means = np.array(column_means)

    # global mean & mode
    mean_brightness = float(np.mean(gray))
    mode_res = stats.mode(gray.flatten(), keepdims=True)
    mode_brightness = float(mode_res.mode[0]) if mode_res.count.size > 0 else 0.0

    # local means
    half_w = window_size // 2
    local_means = []
    for i in range(num_cols):
        s = max(0, i - half_w)
        e = min(num_cols, i + half_w + 1)
        local_means.append(np.mean(column_means[s:e]))
    local_means = np.array(local_means)

    # ===== MEAN COMPARATOR =====
    final_regions_mean, class_counts_mean, dev_mean = compute_regions_from_comparator(
        local_means, mean_brightness, num_cols, min_cols_for_defect
    )

    # draw boxes for MEAN comparator
    output_img_mean = img.copy()
    for start, end, cls in final_regions_mean:
        if cls is None:
            continue
        color = colors[cls]
        x1 = start * column_width
        x2 = min((end + 1) * column_width, w - 1)
        cv2.rectangle(output_img_mean, (x1, 0), (x2, h - 1), color, 15)
        cv2.putText(output_img_mean, cls.upper(), (x1 + 5, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # save MEAN image
    mean_out_path = os.path.join(
        output_image_dir,
        f"{os.path.splitext(img_name)[0]}_MEAN.jpg"
    )
    cv2.imwrite(mean_out_path, output_img_mean)

    # ===== MODE COMPARATOR =====
    final_regions_mode, class_counts_mode, dev_mode = compute_regions_from_comparator(
        local_means, mode_brightness, num_cols, min_cols_for_defect
    )

    # draw boxes for MODE comparator
    output_img_mode = img.copy()
    for start, end, cls in final_regions_mode:
        if cls is None:
            continue
        color = colors[cls]
        x1 = start * column_width
        x2 = min((end + 1) * column_width, w - 1)
        cv2.rectangle(output_img_mode, (x1, 0), (x2, h - 1), color, 15)
        cv2.putText(output_img_mode, cls.upper(), (x1 + 5, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    # save MODE image
    mode_out_path = os.path.join(
        output_image_dir,
        f"{os.path.splitext(img_name)[0]}_MODE.jpg"
    )
    cv2.imwrite(mode_out_path, output_img_mode)

    # build summary row
    summary = {
        "Image": img_name,
        "Mean_Brightness": mean_brightness,
        "Mode_Brightness": mode_brightness,
        "Mean_v1_Count": class_counts_mean['v1'],
        "Mean_v2_Count": class_counts_mean['v2'],
        "Mean_v3_Count": class_counts_mean['v3'],
        "Mean_Total_Defects": sum(class_counts_mean.values()),
        "Mode_v1_Count": class_counts_mode['v1'],
        "Mode_v2_Count": class_counts_mode['v2'],
        "Mode_v3_Count": class_counts_mode['v3'],
        "Mode_Total_Defects": sum(class_counts_mode.values()),
    }

    print(f"Processed {img_name}: MEAN defects={summary['Mean_Total_Defects']}, "
          f"MODE defects={summary['Mode_Total_Defects']}")
    return summary


# ============================
# MAIN LOOP OVER IMAGES
# ============================
image_paths = sorted(
    p for p in glob.glob(os.path.join(folder_path, "*"))
    if p.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
)

if not image_paths:
    raise RuntimeError(f"No image files found in {folder_path}")

# process at most 10 images
image_paths = image_paths[:10]

rows = []
for path in image_paths:
    row = process_image(path)
    if row is not None:
        rows.append(row)

# save CSV
df = pd.DataFrame(rows)
df.to_csv(output_csv, index=False)
print(f"\nSaved defect summary for {len(rows)} image(s) to {output_csv}")
print(f"Annotated images saved to: {output_image_dir}")