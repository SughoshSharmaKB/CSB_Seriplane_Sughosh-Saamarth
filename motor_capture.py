import os
import time
from datetime import datetime

import cv2
import vmbpy as vmb
import Jetson.GPIO as GPIO

# =====================================================
# CAMERA SETUP (UNCHANGED LOGIC)
# =====================================================
SAVE_DIR = os.path.expanduser("~/u1800_images")
os.makedirs(SAVE_DIR, exist_ok=True)

def configure_camera(cam):
    try: cam.ExposureAuto.set('Off')
    except: pass

    try: cam.GainAuto.set('Off')
    except: pass

    try:
        cam.ExposureTime.set(236004.727)
        print(f"✅ Exposure set to {cam.ExposureTime.get()} µs")
    except:
        print("⚠️ Failed to set exposure")

    try: cam.Gain.set(0.0)
    except: pass

    try: cam.AcquisitionMode.set('Continuous')
    except: pass

    try: cam.TriggerMode.set('Off')
    except: pass

    try: cam.AcquisitionFrameRateEnable.set(False)
    except: pass

    try:
        cam.set_pixel_format(vmb.PixelFormat.Bgr8)
    except:
        cam.set_pixel_format(vmb.PixelFormat.Mono8)

def capture_one_image(cam):
    frame = cam.get_frame()

    try:
        cvt = frame.convert_pixel_format(vmb.PixelFormat.Bgr8)
    except vmb.VmbPyError:
        cvt = frame.convert_pixel_format(vmb.PixelFormat.Mono8)

    img = cvt.as_opencv_image()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SAVE_DIR, f"u1800_{ts}.jpg")

    cv2.imwrite(path, img)
    print(f"📸 Captured: {path}")

# =====================================================
# MOTOR SETUP (UNCHANGED LOGIC)
# =====================================================
GPIO.setmode(GPIO.BOARD)

IN1, IN2, IN3, IN4 = 12, 13, 15, 18
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

step_seq = [
    [1, 0, 1, 0],
    [0, 1, 1, 0],
    [0, 1, 0, 1],
    [1, 0, 0, 1]
]

STEP_DELAY = 0.01

def run_motor_for(duration_sec, reverse=False):
    seq = step_seq[::-1] if reverse else step_seq
    start = time.time()
    while time.time() - start < duration_sec:
        for step in seq:
            GPIO.output(IN1, step[0])
            GPIO.output(IN2, step[1])
            GPIO.output(IN3, step[2])
            GPIO.output(IN4, step[3])
            time.sleep(STEP_DELAY)

def stop_motor():
    GPIO.output(IN1, 0)
    GPIO.output(IN2, 0)
    GPIO.output(IN3, 0)
    GPIO.output(IN4, 0)

# =====================================================
# MAIN INTEGRATED SEQUENCE
# =====================================================
def main():
    with vmb.VmbSystem.get_instance() as vmb_sys:
        cams = vmb_sys.get_all_cameras()
        if not cams:
            print("❌ No Allied Vision camera found")
            return

        cam = cams[0]
        print(f"✅ Using camera: {cam}")

        with cam:
            configure_camera(cam)

            try:
                # Initial 6 sec stop → capture
                time.sleep(3)
                capture_one_image(cam)
                time.sleep(3)

                run_motor_for(4.1)
                stop_motor()
                time.sleep(3)
                capture_one_image(cam)
                time.sleep(3)

                run_motor_for(5.32)
                stop_motor()
                time.sleep(3)
                capture_one_image(cam)
                time.sleep(3)

                run_motor_for(4.2)
                stop_motor()
                time.sleep(3)
                capture_one_image(cam)
                time.sleep(3)

                # Reverse motion
                run_motor_for(13.62, reverse=True)
                stop_motor()

                print("✅ Sequence completed")

            finally:
                GPIO.cleanup()
                print("🛑 GPIO cleaned up")

# =====================================================
# ENTRY POINT
# =====================================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        GPIO.cleanup()
        print("🛑 Stopped by user")

