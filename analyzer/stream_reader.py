import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Callable

import cv2

logger = logging.getLogger(__name__)


class StreamReader:
    def __init__(
        self,
        rtsp_url: str,
        sample_fps: int = 2,
        reconnect_retries: int = 3,
        frames_dir: str = "./data/frames",
        clips_dir: str = "./data/clips",
    ):
        self.rtsp_url = rtsp_url
        self.sample_fps = sample_fps
        self.sample_interval = 1.0 / sample_fps
        self.reconnect_retries = reconnect_retries
        self.frames_dir = Path(frames_dir)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir = Path(clips_dir)
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.cap: Optional[cv2.VideoCapture] = None

    def _open_stream(self) -> bool:
        logger.info("Opening RTSP stream: %s", self.rtsp_url)
        self.cap = cv2.VideoCapture(self.rtsp_url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if self.cap.isOpened():
            logger.info("Stream opened successfully")
            return True
        logger.error("Failed to open stream")
        return False

    def _close_stream(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    async def is_available(self) -> bool:
        """Quickly check if stream is accessible."""
        cap = cv2.VideoCapture(self.rtsp_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        available = cap.isOpened()
        cap.release()
        return available

    async def collect(
        self,
        duration_seconds: float,
        frame_callback: Optional[Callable] = None,
        window_tag: str = "window",
        enable_clip_recording: bool = False,
    ) -> dict:
        """
        Collect frames from stream for a given duration.
        Returns metadata about the collection.
        """
        saved_frames: list[Path] = []
        frame_count = 0
        start_time = time.time()
        end_time = start_time + duration_seconds
        last_sample_time = 0.0
        success = False

        # Video writer for full-window recording (optional)
        video_writer: Optional[cv2.VideoWriter] = None
        full_clip_path: Optional[Path] = None
        if enable_clip_recording:
            full_clip_path = self.clips_dir / f"{window_tag}_full.mp4"
            # Use mp4v codec; if unavailable, fallback to avc1/x264
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            # Resolution will be set on first frame
            logger.info("Clip recording enabled, will save to: %s", full_clip_path)

        for attempt in range(self.reconnect_retries):
            if await asyncio.to_thread(self._open_stream):
                success = True
                break
            logger.warning("Stream open attempt %d/%d failed, retrying...", attempt + 1, self.reconnect_retries)
            await asyncio.sleep(2)

        if not success:
            logger.error("Failed to open stream after %d attempts", self.reconnect_retries)
            return {
                "success": False,
                "frame_count": 0,
                "saved_frames": [],
                "duration": 0.0,
                "full_clip_path": None,
            }

        try:
            while time.time() < end_time:
                ret, frame = await asyncio.to_thread(self.cap.read)
                if not ret:
                    logger.warning("Stream read failed, attempting reconnect...")
                    self._close_stream()
                    if not await asyncio.to_thread(self._open_stream):
                        break
                    continue

                now = time.time()
                elapsed = now - start_time
                if now - last_sample_time >= self.sample_interval:
                    last_sample_time = now
                    frame_count += 1

                    if frame_callback:
                        await asyncio.to_thread(frame_callback, frame, elapsed)

                    # Save a few sample frames for evidence (first 3)
                    if frame_count <= 3:
                        ts = int(elapsed * 1000)
                        frame_path = self.frames_dir / f"{window_tag}_frame_{ts:06d}.jpg"
                        await asyncio.to_thread(cv2.imwrite, str(frame_path), frame)
                        saved_frames.append(frame_path)
                        logger.debug("Saved frame: %s", frame_path)

                    # Write to full-window video if enabled
                    if enable_clip_recording and full_clip_path is not None:
                        if video_writer is None:
                            h, w = frame.shape[:2]
                            video_writer = cv2.VideoWriter(
                                str(full_clip_path), fourcc, self.sample_fps, (w, h)
                            )
                            if not video_writer.isOpened():
                                logger.error("Failed to open VideoWriter, clip recording disabled")
                                video_writer = None
                        if video_writer is not None:
                            video_writer.write(frame)

                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.01)
        finally:
            self._close_stream()
            if video_writer is not None:
                video_writer.release()
                logger.info("Full clip saved: %s", full_clip_path)

        actual_duration = time.time() - start_time
        logger.info(
            "Collection finished: %d frames in %.1fs",
            frame_count, actual_duration,
        )
        return {
            "success": frame_count > 0,
            "frame_count": frame_count,
            "saved_frames": saved_frames,
            "duration": actual_duration,
            "full_clip_path": str(full_clip_path) if full_clip_path and full_clip_path.exists() else None,
        }

    def extract_clip_segment(
        self,
        full_clip_path: str,
        start_sec: float,
        end_sec: float,
        output_path: str,
        padding: float = 3.0,
    ) -> bool:
        """
        Extract a segment from full clip using ffmpeg.
        Adds padding seconds before/after.
        """
        import subprocess
        s = max(0.0, start_sec - padding)
        duration = (end_sec - start_sec) + padding * 2
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(s),
            "-t", str(duration),
            "-i", full_clip_path,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]
        logger.info("Extracting clip segment: %s [%.1fs-%.1fs] -> %s", full_clip_path, s, s + duration, output_path)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.info("Clip segment saved: %s", output_path)
                return True
            else:
                logger.error("ffmpeg failed: %s", result.stderr)
                return False
        except Exception as e:
            logger.error("ffmpeg exception: %s", e)
            return False
