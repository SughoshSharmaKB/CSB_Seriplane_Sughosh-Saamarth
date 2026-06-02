from flask import Flask, jsonify, send_file, request
import subprocess
import os
import re
import csv
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(BASE_DIR, "results")
LOGS_DIR   = os.path.join(BASE_DIR, "logs")

app = Flask(__name__, static_folder="static")

# ── Evenness columns (actual headers in your CSVs) ───────────────
EVENNESS_COLS = ["Mean_v1_Count", "Mean_v2_Count", "Mean_v3_Count"]

# ── Neatness columns ──────────────────────────────────────────────
NEATNESS_SUM_COLS  = ["Cleanliness_minor", "Cleanliness_major", "Cleanliness_supermajor"]
NEATNESS_GRADE_COL = "Neatness_Grade"
VALID_GRADES       = [str(g) for g in range(70, 105, 5)]  # 70,75,...,100


# ═════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════
@app.route("/print-worksheet", methods=["POST"])
def print_worksheet():
    """Generate printable worksheet from all panels"""
    try:
        data = request.json or {}
        mode = data.get("mode", "all")
        from_panel = data.get("from", 1)
        to_panel = data.get("to", 9999)

        if not os.path.exists(LOGS_DIR):
            return jsonify({"error": "No logs directory found"}), 404

        panel_dirs = sorted(
            [d for d in os.listdir(LOGS_DIR) if re.match(r"panel\d+", d)],
            key=lambda x: int(re.search(r"\d+", x).group())
        )

        if mode == "range":
            panel_dirs = [
                p for p in panel_dirs
                if from_panel <= int(re.search(r"\d+", p).group()) <= to_panel
            ]

        # Collect all neatness data (100 strips)
        all_strips = []
        
        for panel in panel_dirs:
            panel_path = os.path.join(LOGS_DIR, panel)
            neatness_path = os.path.join(panel_path, "neatness_cleanness.csv")

            if os.path.isfile(neatness_path):
                with open(neatness_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        neatness = row.get("Neatness_Grade", "").strip()
                        minness = row.get("Cleanliness_minor", "").strip()
                        all_strips.append({
                            "neatness": neatness,
                            "minness": minness
                        })

        # Pad to 100 strips if less
        while len(all_strips) < 100:
            all_strips.append({"neatness": "", "minness": ""})

        # Calculate summary
        neatness_values = [float(s["neatness"]) for s in all_strips if s["neatness"]]
        
        # Weighted neatness
        grade_counts = {}
        for val in neatness_values:
            grade_counts[val] = grade_counts.get(val, 0) + 1
        
        weighted_sum = sum(grade * count for grade, count in grade_counts.items())
        total_count = sum(grade_counts.values())
        neatness_avg = weighted_sum / total_count if total_count > 0 else 0
        
        # Low neatness (bottom 20%)
        sorted_desc = sorted(neatness_values, reverse=True)
        bottom_count = max(1, int(len(sorted_desc) * 0.2))
        bottom_values = sorted_desc[-bottom_count:]
        low_neatness = sum(bottom_values) / len(bottom_values) if bottom_values else 0

        return jsonify({
            "strips": all_strips[:100],
            "summary": {
                "neatness": round(neatness_avg, 2),
                "low_neatness": round(low_neatness, 2),
                "neatness_breakdown": dict(grade_counts)
            }
        })

    except Exception as e:
        print("Error in /print-worksheet:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def read_csv_dicts(filepath):
    """Read a CSV into list of stripped row-dicts. Empty list if missing."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [{k.strip(): v.strip() for k, v in row.items()} for row in reader]


def sum_cols(rows, cols):
    """Sum numeric values for each column name. Returns {col: float}."""
    totals = {col: 0.0 for col in cols}
    for row in rows:
        for col in cols:
            try:
                totals[col] += float(row.get(col, 0) or 0)
            except ValueError:
                pass
    return totals


def count_grades(rows):
    """Count occurrences of each Neatness_Grade value."""
    counts = {g: 0 for g in VALID_GRADES}
    for row in rows:
        grade = row.get(NEATNESS_GRADE_COL, "").strip()
        if grade in counts:
            counts[grade] += 1
    return counts


def get_panel_dirs():
    """Return sorted list of (panel_num, panel_name, panel_path)."""
    if not os.path.exists(LOGS_DIR):
        return []
    panels = []
    for name in os.listdir(LOGS_DIR):
        m = re.match(r"panel(\d+)$", name, re.IGNORECASE)
        if m and os.path.isdir(os.path.join(LOGS_DIR, name)):
            panels.append((int(m.group(1)), name, os.path.join(LOGS_DIR, name)))
    panels.sort(key=lambda x: x[0])
    return panels


# ═════════════════════════════════════════════════════════════════
#  ROUTES
# ═════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return app.send_static_file("index.html")


@app.route("/home", methods=["POST"])
def home_reset():
    data = request.json or {}

    PREPROCESSED_DIR = os.path.join(BASE_DIR, "preprocessed")
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Find next panel number
    panel_numbers = []
    for name in os.listdir(LOGS_DIR):
        match = re.match(r"panel(\d+)", name)
        if match:
            panel_numbers.append(int(match.group(1)))

    next_panel = max(panel_numbers) + 1 if panel_numbers else 1
    if next_panel > 100:
        return jsonify({"error": "Maximum panel limit reached"}), 400

    PANEL_DIR = os.path.join(LOGS_DIR, f"panel{next_panel}")
    os.makedirs(PANEL_DIR)

    # Save updated CSVs
    if data.get("evenness", "").strip():
        with open(os.path.join(PANEL_DIR, "evenness.csv"), "w") as f:
            f.write(data["evenness"])

    if data.get("neatness", "").strip():
        with open(os.path.join(PANEL_DIR, "neatness_cleanness.csv"), "w") as f:
            f.write(data["neatness"])

    # Copy result subfolders
    for sub in ["evenness", "neatness"]:
        src = os.path.join(RESULT_DIR, sub)
        dst = os.path.join(PANEL_DIR, sub)
        if os.path.exists(src):
            shutil.copytree(src, dst)

    # Clean result CSVs
    for fname in ["evenness.csv", "neatness_cleanness.csv"]:
        path = os.path.join(RESULT_DIR, fname)
        if os.path.exists(path):
            os.remove(path)

    # Clean preprocessed images
    if os.path.exists(PREPROCESSED_DIR):
        for file in os.listdir(PREPROCESSED_DIR):
            fp = os.path.join(PREPROCESSED_DIR, file)
            if os.path.isfile(fp):
                os.remove(fp)

    # Delete evenness images
    EVENNESS_DIR = os.path.join(BASE_DIR, "results/evenness")
    if os.path.exists(EVENNESS_DIR):
        for filename in os.listdir(EVENNESS_DIR):
            fp = os.path.join(EVENNESS_DIR, filename)
            if os.path.isfile(fp):
                os.remove(fp)

    # Delete neatness images
    NEATNESS_DIR = os.path.join(BASE_DIR, "results/neatness")
    if os.path.exists(NEATNESS_DIR):
        for filename in os.listdir(NEATNESS_DIR):
            fp = os.path.join(NEATNESS_DIR, filename)
            if os.path.isfile(fp):
                os.remove(fp)

    return jsonify({"status": "panel_saved", "panel": f"panel{next_panel}"})


@app.route("/execute", methods=["POST"])
def execute_pipeline():
    subprocess.run(["python", "pipeline.py"], check=True)
    return jsonify({"status": "Pipeline executed"})


@app.route("/csv/<name>")
def get_csv(name):
    if name == "evenness":
        file_path = os.path.join(RESULT_DIR, "evenness.csv")
    elif name == "neatness":
        file_path = os.path.join(RESULT_DIR, "neatness_cleanness.csv")
    else:
        return "Invalid CSV", 404

    if not os.path.exists(file_path):
        return "", 204

    return send_file(file_path, mimetype="text/csv")


@app.route("/generate", methods=["POST"])
def generate():
    try:
        if not os.path.exists(LOGS_DIR):
            return jsonify({"error": "No logs directory found"}), 404

        data = request.json or {}
        mode = data.get("mode", "all")
        from_panel = data.get("from", 1)
        to_panel = data.get("to", 9999)

        panel_dirs = sorted(
            [d for d in os.listdir(LOGS_DIR) if re.match(r"panel\d+", d)],
            key=lambda x: int(re.search(r"\d+", x).group())
        )

        if mode == "range":
            panel_dirs = [
                p for p in panel_dirs
                if from_panel <= int(re.search(r"\d+", p).group()) <= to_panel
            ]

        all_evenness = []
        all_neatness = []

        for panel in panel_dirs:
            panel_path = os.path.join(LOGS_DIR, panel)

            # 🔥 Using .csv extension to read the actual files
            evenness_path = os.path.join(panel_path, "evenness.csv")
            neatness_path = os.path.join(panel_path, "neatness_cleanness.csv")

            if os.path.isfile(evenness_path):
                with open(evenness_path, "r") as f:
                    lines = f.read().strip().split("\n")
                    all_evenness.append({"panel": panel, "rows": lines})

            if os.path.isfile(neatness_path):
                with open(neatness_path, "r") as f:
                    lines = f.read().strip().split("\n")
                    all_neatness.append({"panel": panel, "rows": lines})

        return jsonify({
            "evenness": all_evenness,
            "neatness": all_neatness,
            "panels": panel_dirs
        })

    except Exception as e:
        print("Error in /generate:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/panel-images/<panel>")
def panel_images(panel):
    """Return a JSON list of images available for a given panel."""
    if not re.match(r'^panel\d+$', panel, re.IGNORECASE):
        return jsonify({"error": "Invalid panel name"}), 400

    panel_path = os.path.join(LOGS_DIR, panel)
    if not os.path.isdir(panel_path):
        return jsonify({"error": "Panel not found"}), 404

    images = []
    for folder in ["evenness", "neatness"]:
        folder_path = os.path.join(panel_path, folder)
        if os.path.isdir(folder_path):
            for filename in sorted(os.listdir(folder_path)):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                    images.append({"folder": folder, "filename": filename})

    return jsonify({"panel": panel, "images": images})


@app.route("/panel-image/<panel>/<folder>/<filename>")
def panel_image(panel, folder, filename):
    """Serve a specific image from a panel's evenness or neatness subfolder."""
    if not re.match(r'^panel\d+$', panel, re.IGNORECASE):
        return "Invalid panel", 400
    if folder not in ["evenness", "neatness"]:
        return "Invalid folder", 400
    if not re.match(r'^[\w\-\.]+$', filename):
        return "Invalid filename", 400

    image_path = os.path.join(LOGS_DIR, panel, folder, filename)
    if not os.path.isfile(image_path):
        return "Image not found", 404

    return send_file(image_path)


@app.route("/update-panel-csv", methods=["POST"])
def update_panel_csv():
    """Update a single field's value in a panel's CSV.
    The table displays column *sums*; we apply the delta to the first data row
    so the new sum equals the requested new_value."""
    try:
        data      = request.json or {}
        panel     = data.get("panel", "")
        field     = data.get("field", "")
        new_value = float(data.get("value", 0))

        if not re.match(r'^panel\d+$', panel, re.IGNORECASE):
            return jsonify({"error": "Invalid panel"}), 400

        EVENNESS_MAP = {
            "EV1": "v1_Count",
            "EV2": "v2_Count",
            "EV3": "v3_Count",
        }
        NEATNESS_MAP = {
            "Super Major": "Cleanliness_supermajor",
            "Major":       "Cleanliness_major",
            "Minor":       "Cleanliness_minor",
        }

        panel_path = os.path.join(LOGS_DIR, panel)

        if field in EVENNESS_MAP:
            csv_col  = EVENNESS_MAP[field]
            csv_path = os.path.join(panel_path, "evenness.csv")
        elif field in NEATNESS_MAP:
            csv_col  = NEATNESS_MAP[field]
            csv_path = os.path.join(panel_path, "neatness_cleanness.csv")
        else:
            return jsonify({"error": f"Field '{field}' is not editable"}), 400

        if not os.path.isfile(csv_path):
            return jsonify({"error": "CSV file not found"}), 404

        # Read CSV
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader    = csv.DictReader(f)
            rows      = list(reader)
            fieldnames = reader.fieldnames

        if not rows:
            return jsonify({"error": "CSV file is empty"}), 400

        # Calculate current column total and the required delta
        current_total = sum(float(r.get(csv_col, 0) or 0) for r in rows)
        delta         = new_value - current_total

        # Apply delta to the first data row
        first_val         = float(rows[0].get(csv_col, 0) or 0)
        rows[0][csv_col]  = str(round(first_val + delta, 6))

        # Write back
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return jsonify({"status": "updated", "panel": panel, "field": field, "newTotal": new_value})

    except Exception as e:
        print("Error in /update-panel-csv:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── Error handlers ────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Route not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": str(e)}), 500


# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
