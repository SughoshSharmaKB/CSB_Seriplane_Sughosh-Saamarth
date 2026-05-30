import os
import csv
import json
import sys

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")

# Evenness columns to sum
EVENNESS_COLS = ["v1 count", "v2 count", "v3 count"]

# Neatness columns to sum
NEATNESS_SUM_COLS = ["Cleanliness_minor", "Cleanliness_major", "Cleanliness_supermajor"]

# Neatness grade column
NEATNESS_GRADE_COL = "Neatness_Grade"

# Valid grades from 70 to 100 step 5
VALID_GRADES = list(range(70, 105, 5))  # [70, 75, 80, 85, 90, 95, 100]


def get_panel_folders(logs_dir):
    """Return sorted list of panel folders (panel1, panel2, ...) in logs dir."""
    folders = []
    if not os.path.exists(logs_dir):
        return folders
    for name in os.listdir(logs_dir):
        path = os.path.join(logs_dir, name)
        if os.path.isdir(path) and name.lower().startswith("panel"):
            suffix = name[5:]  # everything after "panel"
            if suffix.isdigit():
                folders.append((int(suffix), name, path))
    folders.sort(key=lambda x: x[0])
    return folders


def read_csv_as_dicts(filepath):
    """Read a CSV file and return list of row dicts."""
    rows = []
    if not os.path.exists(filepath):
        return rows
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Strip whitespace from keys and values
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows


def aggregate_evenness(rows):
    """Sum v1 count, v2 count, v3 count across all rows."""
    totals = {col: 0 for col in EVENNESS_COLS}
    for row in rows:
        for col in EVENNESS_COLS:
            try:
                totals[col] += float(row.get(col, 0) or 0)
            except ValueError:
                pass
    return totals


def aggregate_neatness(rows):
    """
    Sum Cleanliness_minor, Cleanliness_major, Cleanliness_supermajor.
    Count occurrences of each Neatness_Grade (70–100 step 5).
    """
    sums = {col: 0 for col in NEATNESS_SUM_COLS}
    grade_counts = {str(g): 0 for g in VALID_GRADES}

    for row in rows:
        # Sum cleanliness columns
        for col in NEATNESS_SUM_COLS:
            try:
                sums[col] += float(row.get(col, 0) or 0)
            except ValueError:
                pass

        # Count grades
        grade_val = row.get(NEATNESS_GRADE_COL, "").strip()
        if grade_val in grade_counts:
            grade_counts[grade_val] += 1

    return sums, grade_counts


def generate():
    panels = get_panel_folders(LOGS_DIR)

    if not panels:
        return {"error": f"No panel folders found in '{LOGS_DIR}'"}

    # Global accumulators
    global_evenness = {col: 0 for col in EVENNESS_COLS}
    global_neatness_sums = {col: 0 for col in NEATNESS_SUM_COLS}
    global_grade_counts = {str(g): 0 for g in VALID_GRADES}

    panel_results = []

    for panel_num, panel_name, panel_path in panels:
        evenness_file = os.path.join(panel_path, "evenness.csv")
        neatness_file = os.path.join(panel_path, "neatness_cleanness.csv")

        # --- Evenness ---
        evenness_rows = read_csv_as_dicts(evenness_file)
        evenness_totals = aggregate_evenness(evenness_rows)

        # Accumulate into global
        for col in EVENNESS_COLS:
            global_evenness[col] += evenness_totals[col]

        # --- Neatness ---
        neatness_rows = read_csv_as_dicts(neatness_file)
        neatness_sums, grade_counts = aggregate_neatness(neatness_rows)

        # Accumulate into global
        for col in NEATNESS_SUM_COLS:
            global_neatness_sums[col] += neatness_sums[col]
        for grade in grade_counts:
            global_grade_counts[grade] += grade_counts[grade]

        panel_results.append({
            "panel": panel_name,
            "evenness": evenness_totals,
            "neatness_sums": neatness_sums,
            "grade_counts": grade_counts
        })

    result = {
        "total_panels": len(panels),
        "panels": panel_results,
        "global_evenness": global_evenness,
        "global_neatness_sums": global_neatness_sums,
        "global_grade_counts": global_grade_counts
    }

    return result


if __name__ == "__main__":
    output = generate()
    print(json.dumps(output))
