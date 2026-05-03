import os
import logging
from pathlib import Path
from typing import Optional, List, Tuple

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions

logger = logging.getLogger(__name__)

# Tip landmark indices: thumb, index, middle, ring, pinky
TIP_INDICES = [4, 8, 12, 16, 20]


class HandsDetector:
    def __init__(
        self,
        model_path: Optional[str] = None,
        num_hands: int = 2,
        min_detection_confidence: float = 0.3,
        min_presence_confidence: float = 0.3,
    ):
        if model_path is None:
            model_path = str(Path(__file__).resolve().parent / "models" / "hand_landmarker.task")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Hand model not found: {model_path}")

        base_options = BaseOptions(
            model_asset_path=model_path,
            delegate=BaseOptions.Delegate.CPU,
        )
        options = HandLandmarkerOptions(
            base_options=base_options,
            num_hands=num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_presence_confidence,
        )
        self.detector = HandLandmarker.create_from_options(options)
        logger.info("HandsDetector initialized: %s", model_path)

    def detect(self, image_bgr: np.ndarray) -> List[List]:
        """
        Detect hands in a BGR image.
        Returns list of hands, each hand is a list of 21 landmarks.
        """
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        results = self.detector.detect(mp_image)
        return results.hand_landmarks if results.hand_landmarks else []

    def get_all_finger_tips(self, hand_landmarks: List[List]) -> List[Tuple[float, float]]:
        """Return all visible finger tip coordinates [(x, y), ...]."""
        tips = []
        for hand in hand_landmarks:
            for idx in TIP_INDICES:
                if idx < len(hand):
                    lm = hand[idx]
                    # hand landmarks don't have visibility field in MediaPipe 0.10
                    # use presence score if available, otherwise assume visible
                    score = getattr(lm, 'presence', None)
                    if score is None or score >= 0.5:
                        tips.append((lm.x, lm.y))
        return tips

    def close(self):
        try:
            self.detector.close()
        except Exception as e:
            logger.warning("Error closing hand detector: %s", e)
