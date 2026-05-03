import os
import logging
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions

logger = logging.getLogger(__name__)

# Landmark indices
NOSE = 0
LEFT_EYE_INNER = 1
LEFT_EYE = 2
LEFT_EYE_OUTER = 3
RIGHT_EYE_INNER = 4
RIGHT_EYE = 5
RIGHT_EYE_OUTER = 6
LEFT_EAR = 7
RIGHT_EAR = 8
MOUTH_LEFT = 9
MOUTH_RIGHT = 10
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16


class PoseDetector:
    def __init__(
        self,
        model_path: Optional[str] = None,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        if model_path is None:
            # Default to bundled model relative to this file
            model_path = str(Path(__file__).resolve().parent / "models" / "pose_landmarker_lite.task")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Pose model not found: {model_path}")

        base_options = BaseOptions(
            model_asset_path=model_path,
            delegate=BaseOptions.Delegate.CPU,
        )
        options = PoseLandmarkerOptions(
            base_options=base_options,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.detector = PoseLandmarker.create_from_options(options)
        logger.info("PoseDetector initialized with model: %s", model_path)

    def detect(self, image_bgr: np.ndarray) -> Optional[List]:
        """
        Detect pose landmarks in a BGR image.
        Returns list of 33 landmarks or None if no person detected.
        Each landmark has .x, .y, .z, .visibility in normalized coordinates.
        """
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        results = self.detector.detect(mp_image)

        if not results.pose_landmarks:
            return None

        return results.pose_landmarks[0]

    def get_mouth_center(self, landmarks: list) -> Optional[Tuple[float, float]]:
        """Return normalized (x, y) of mouth center."""
        if len(landmarks) <= max(MOUTH_LEFT, MOUTH_RIGHT):
            return None
        ml = landmarks[MOUTH_LEFT]
        mr = landmarks[MOUTH_RIGHT]
        if ml.visibility < 0.5 or mr.visibility < 0.5:
            return None
        return ((ml.x + mr.x) / 2.0, (ml.y + mr.y) / 2.0)

    def get_face_center(self, landmarks: list) -> Optional[Tuple[float, float]]:
        """Return normalized (x, y) of face center (nose)."""
        if len(landmarks) <= NOSE:
            return None
        nose = landmarks[NOSE]
        if nose.visibility < 0.5:
            return None
        return (nose.x, nose.y)

    def get_wrists(self, landmarks: list) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        """Return (left_wrist, right_wrist) as normalized (x, y) or None."""
        if len(landmarks) <= max(LEFT_WRIST, RIGHT_WRIST):
            return None, None
        lw = landmarks[LEFT_WRIST]
        rw = landmarks[RIGHT_WRIST]
        left = (lw.x, lw.y) if lw.visibility >= 0.5 else None
        right = (rw.x, rw.y) if rw.visibility >= 0.5 else None
        return left, right

    def close(self):
        try:
            self.detector.close()
        except Exception as e:
            logger.warning("Error closing detector: %s", e)


