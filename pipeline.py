import subprocess
import sys
from pathlib import Path

# Change these to your actual folders
RAW_DIR = Path("data")
#PREPROC_DIR = Path("data/preprocessed")
EVENNESS_DIR = Path("results/evenness")
NEATNESS_DIR = Path("results/neatness")


def run_step(cmd):
    """Run a shell command and stop the pipeline if it fails."""
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    # Make sure output folders exist
    #PREPROC_DIR.mkdir(parents=True, exist_ok=True)
    EVENNESS_DIR.mkdir(parents=True, exist_ok=True)
    NEATNESS_DIR.mkdir(parents=True, exist_ok=True)

    # Loop over all raw images
    # raw_images = sorted(list(RAW_DIR.glob("*.png")) + list(RAW_DIR.glob("*.jpg")))

    # if not raw_images:
    #     return

    # for raw_path in raw_images:
    #     # 1) Preprocessing output path
    #     preproc_path = PREPROC_DIR / f"{raw_path.stem}_preproc.png"

    #     # 2) Evenness & neatness result files
    #     evenness_result = EVENNESS_DIR / f"{raw_path.stem}_evenness.csv"
    #     neatness_result = NEATNESS_DIR / f"{raw_path.stem}_neatness.csv"

    #     # Final required prints only
    #     print(f"Preprocessed image : {preproc_path}")
    #     print(f"Evenness result    : {evenness_result}")
    #     print(f"Neatness result    : {neatness_result}")
    
    # --- Step 1: preprocessing.py ---
    run_step(
        [
            sys.executable,
            "precrop.py"
        ]
    )

    run_step(
            [
                sys.executable,
                "crop.py"
            ]
    )
    
    # --- Step 2: evenness.py ---
    run_step(
        [
            sys.executable,
            "even.py"
        ]
    )

    # --- Step 3: neatness.py ---
    run_step(
        [
            sys.executable,
            "clean_neat.py"
        ]
    )


if __name__ == "__main__":
    main()
