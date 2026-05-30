from PIL import Image
import os

def main():
    # =========================================================
    #                  USER SETTINGS
    # =========================================================

    # Folder containing images
    input_folder = "./data"

    # Image DPI (must match your overlay/grid DPI)
    dpi = 300

    # Crop mode: choose ONE -> "px" or "cm"
    crop_mode = "cm"   # "px" OR "cm"

    # ---------------------------------------------------------
    # Crop region definition
    # (left, top, right, bottom)
    # ---------------------------------------------------------

    # ---- If crop_mode = "px" ----
    crop_px = {
        "left": 100,      # pixels
        "top": 200,
        "right": 1200,
        "bottom": 1600
    }

    # ---- If crop_mode = "cm" ----
    crop_cm = {
        "left": 1.0,      # cm from LEFT
        "top": 0.5,       # cm from TOP
        "right": 19.0,    # cm from LEFT (as per your current logic)
        "bottom": 12.0
    }

    # =========================================================
    #               DO NOT EDIT BELOW
    # =========================================================

    px_per_cm = dpi / 2.54

    image_files = [
        f for f in os.listdir(input_folder)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

    if not image_files:
        print(f"❌ No image files found in {input_folder}")
        return

    print(f"📂 Found {len(image_files)} image(s)\n")

    for img_name in image_files:
        img_path = os.path.join(input_folder, img_name)
        img = Image.open(img_path).convert("RGB")
        W, H = img.size

        # Convert crop coordinates to pixels
        if crop_mode.lower() == "cm":
            left   = int(round(crop_cm["left"]   * px_per_cm))
            top    = int(round(crop_cm["top"]    * px_per_cm))
            right  = int(round(crop_cm["right"]  * px_per_cm))
            bottom = int(round(crop_cm["bottom"] * px_per_cm))
        else:
            left   = crop_px["left"]
            top    = crop_px["top"]
            right  = crop_px["right"]
            bottom = crop_px["bottom"]

        # Clamp to image boundaries
        left   = max(0, min(left, W))
        right  = max(0, min(right, W))
        top    = max(0, min(top, H))
        bottom = max(0, min(bottom, H))

        # Validate crop box
        if right <= left or bottom <= top:
            print(f"❌ Invalid crop for {img_name}, skipped.")
            continue

        # Crop image
        cropped_img = img.crop((left, top, right, bottom))

        # OVERWRITE original image
        cropped_img.save(img_path)

        print(f"✅ Cropped & replaced: {img_name}")
        print(f"   Image size before: {W} x {H} px")
        print(f"   Crop box (px): ({left}, {top}) → ({right}, {bottom})")
        print(f"   Image size after : {cropped_img.size[0]} x {cropped_img.size[1]} px\n")

    print("🎯 Pre-cropping completed successfully.")


if __name__ == "__main__":
    main()