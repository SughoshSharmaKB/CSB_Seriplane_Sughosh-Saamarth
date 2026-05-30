import os
import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO
from collections import defaultdict
from datetime import datetime

# --------------------------------------------------
# CONFIG (LOCAL SYSTEM)
# --------------------------------------------------
BASE_DIR = os.getcwd()

MODEL_PATH = os.path.join(BASE_DIR, "models", "best.pt")

INPUT_DIR = os.path.join(BASE_DIR, "preprocessed")
OUTPUT_DIR = os.path.join(BASE_DIR, "results", "neatness")
CSV_LOG = os.path.join("results", "neatness_cleanness.csv")

IMG_EXT = {".jpg", ".jpeg", ".png"}

# create required folders
os.makedirs(OUTPUT_DIR, exist_ok=True)

# defect category groups
CLEANLINESS_CLASSES = {"minor", "major", "supermajor", "super_major"}
NEATNESS_CLASSES = {"neatness"}

# --------------------------------------------------
# LOAD YOLO MODEL
# --------------------------------------------------
model = YOLO(MODEL_PATH)

def run_batch_yolo(folder_path):
    """
    Run YOLO inference on all images inside data folder
    and save results to results/neatness
    """

    if not os.path.exists(folder_path):
        print("❌ Folder does not exist:", folder_path)
        return

    results_list = []

    # ------------------------------------------
    # PROCESS ALL IMAGES
    # ------------------------------------------
    for filename in os.listdir(folder_path):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in IMG_EXT:
            continue

        img_path = os.path.join(folder_path, filename)

        img = cv2.imread(img_path)
        if img is None:
            continue

        # run inference
        results = model(img)
        annotated = results[0].plot()

        # save annotated image
        output_path = os.path.join(OUTPUT_DIR, filename)
        cv2.imwrite(output_path, annotated)

        # defect counting
        defect_counts = defaultdict(int)
        total_defects = 0

        if results[0].boxes is not None:
            class_ids = results[0].boxes.cls.cpu().numpy()
            class_names = results[0].names

            for cid in class_ids:
                cls_name = class_names[int(cid)]
                defect_counts[cls_name] += 1
                total_defects += 1

        cleanliness = {cls: defect_counts.get(cls, 0) for cls in CLEANLINESS_CLASSES}
        neatness = {cls: defect_counts.get(cls, 0) for cls in NEATNESS_CLASSES}

        row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Image_Name": filename,
            **{f"Cleanliness_{k}": cleanliness[k] for k in CLEANLINESS_CLASSES},
            **{f"Neatness_{k}": neatness[k] for k in NEATNESS_CLASSES},
            "Total_Defects": total_defects,
            "Output_Image_Path": output_path
        }

        results_list.append(row)

    # ------------------------------------------
    # SAVE CSV
    # ------------------------------------------
    if results_list:
        df = pd.DataFrame(results_list)
        df.to_csv(CSV_LOG, index=False)
        print("✅ CSV saved:", CSV_LOG)
        print("📁 Annotated images saved in:", OUTPUT_DIR)
    else:
        print("⚠️ No valid images found.")


# --------------------------------------------------
# MAIN ENTRY
# --------------------------------------------------
if __name__ == "__main__":
    run_batch_yolo(INPUT_DIR)
