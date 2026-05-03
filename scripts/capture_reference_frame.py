"""
Capture a single reference frame from RTSP stream for ROI manual calibration.

Usage:
    python scripts/capture_reference_frame.py

Then open the saved image and note the normalized coordinates [x1, y1, x2, y2]
to fill in config.yaml -> roi section.
"""
import os
import sys
import cv2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analyzer.config import Config


def main():
    config = Config("config.yaml")
    rtsp_url = config.stream_rtsp_url
    print(f"Connecting to: {rtsp_url}")

    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("Failed to open stream!")
        return 1

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Failed to read frame!")
        return 1

    h, w = frame.shape[:2]
    print(f"Frame size: {w}x{h}")

    out_dir = Path("./data/frames")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "reference.jpg"
    cv2.imwrite(str(out_path), frame)
    print(f"Reference frame saved to: {out_path}")
    print("\nTo configure ROI, open this image and note normalized coordinates:")
    print("  x = pixel_x / width, y = pixel_y / height")
    print("  Example sink_area: [0.25, 0.30, 0.75, 0.80]")
    print("Then update config.yaml -> roi section.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
