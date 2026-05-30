import os
import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO
from collections import defaultdict
from datetime import datetime

# MODEL_PATH = "silk_defect_detection/rtdetr_silk3/weights/best.pt"
# OUTPUT_DIR = "batch_output"
# CSV_LOG = "batch_results.csv"
IMG_EXT = {".jpg", ".jpeg", ".png"}
CONF_THRESHOLD_MINOR = 0.5


BASE_DIR = os.getcwd()
MODEL_PATH = os.path.join(BASE_DIR, "models", "transformer.pt")
INPUT_DIR = os.path.join(BASE_DIR, "preprocessed")
OUTPUT_DIR = os.path.join(BASE_DIR, "results", "neatness")
CSV_LOG = os.path.join("results", "neatness_cleanness.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# defect category groups
CLEANLINESS_CLASSES = {"minor", "major", "supermajor"}
NEATNESS_CLASSES = {"neatness"}

# color map (BGR)
CLASS_COLORS = {
    "minor": (0, 165, 255),
    "major": (0, 0, 255),
    "supermajor": (255, 0, 255),
    "neatness": (255, 0, 0)
}

DEFAULT_COLOR = (0, 255, 255)

# LOAD YOLO MODEL
model = YOLO(MODEL_PATH)


def get_neatness_grade(neatness_count):
    """Return neatness grade based on defect count"""
    if neatness_count == 0:
        return 100
    elif neatness_count <= 5:
        return 90
    elif neatness_count <= 10:
        return 80
    elif neatness_count <= 15:
        return 70
    elif neatness_count <= 20:
        return 60
    elif neatness_count <= 25:
        return 50
    elif neatness_count <= 30:
        return 40
    elif neatness_count <= 35:
        return 30
    elif neatness_count <= 40:
        return 20
    else:
        return 10


def draw_box(img, box, label, conf):
    color = CLASS_COLORS.get(label, DEFAULT_COLOR)

    x1, y1, x2, y2 = map(int, box)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)

    text = f"{label.upper()} {conf:.2f}"
    font_scale = 1.5
    thickness = 4

    (w, h), _ = cv2.getTextSize(
        text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
    )

    cv2.rectangle(
        img,
        (x1, y1 - h - 12),
        (x1 + w + 4, y1),
        color,
        -1
    )

    cv2.putText(
        img,
        text,
        (x1 + 2, y1 - 6),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA
    )


def run_batch_yolo(folder_path):

    if not os.path.exists(folder_path):
        return

    results_list = []

    for filename in os.listdir(folder_path):
        if os.path.splitext(filename)[1].lower() not in IMG_EXT:
            continue

        img_path = os.path.join(folder_path, filename)
        img = cv2.imread(img_path)
        if img is None:
            continue

        results = model(img)
        boxes_obj = results[0].boxes
        class_names = results[0].names

        annotated = img.copy()
        defect_counts = defaultdict(int)
        total_defects = 0

        if boxes_obj is not None and len(boxes_obj) > 0:
            boxes = boxes_obj.xyxy.cpu().numpy()
            class_ids = boxes_obj.cls.cpu().numpy()
            confidences = boxes_obj.conf.cpu().numpy()

            for box, cid, conf in zip(boxes, class_ids, confidences):
                original_cls = class_names[int(cid)]

                if original_cls == "minor":
                    if conf > CONF_THRESHOLD_MINOR:
                        final_cls = "minor"
                        defect_counts["minor"] += 1
                    else:
                        final_cls = "neatness"
                        defect_counts["neatness"] += 1
                else:
                    final_cls = original_cls
                    defect_counts[original_cls] += 1

                total_defects += 1
                draw_box(annotated, box, final_cls, conf)

        output_path = os.path.join(OUTPUT_DIR, filename)
        cv2.imwrite(output_path, annotated)

        cleanliness = {cls: defect_counts.get(cls, 0) for cls in CLEANLINESS_CLASSES}
        neatness = defect_counts.get("neatness", 0)
        neatness_grade = get_neatness_grade(neatness)

        row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Image_Name": filename,
            **{f"Cleanliness_{k}": cleanliness[k] for k in CLEANLINESS_CLASSES},
            "Neatness_neatness": neatness,
            "Neatness_Grade": neatness_grade,
            "Total_Defects": total_defects,
            "Output_Image_Path": output_path
        }

        results_list.append(row)

    if results_list:
        pd.DataFrame(results_list).to_csv(CSV_LOG, index=False)
        print("✅ CSV saved:", CSV_LOG)
        print("📁 Images saved in:", OUTPUT_DIR)

# MAIN
if __name__ == "__main__":
    folder = INPUT_DIR
    run_batch_yolo(folder)
