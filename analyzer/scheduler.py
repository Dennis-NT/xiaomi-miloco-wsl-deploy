import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from analyzer.config import Config
from analyzer.db import Database
from analyzer.notifier_email import EmailNotifier
from analyzer.stream_reader import StreamReader
from analyzer.behavior_analyzer import BehaviorAnalyzer

logger = logging.getLogger(__name__)


def parse_time(t: str) -> tuple[int, int]:
    h, m = t.split(":")
    return int(h), int(m)


def next_window_occurrence(start_str: str, tz_now: datetime) -> datetime:
    """Return the next occurrence of start time (today or tomorrow)."""
    h, m = parse_time(start_str)
    candidate = tz_now.replace(hour=h, minute=m, second=0, microsecond=0)
    if candidate <= tz_now:
        candidate += timedelta(days=1)
    return candidate


class AnalysisWindow:
    def __init__(self, name: str, start: str, end: str):
        self.name = name
        self.start = start
        self.end = end


class Scheduler:
    def __init__(
        self,
        config: Config,
        db: Database,
        notifier: EmailNotifier,
        stream_reader: StreamReader,
    ):
        self.config = config
        self.db = db
        self.notifier = notifier
        self.stream = stream_reader
        self.windows: list[AnalysisWindow] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

        for w in config.windows:
            self.windows.append(AnalysisWindow(w["name"], w["start"], w["end"]))

    def _now(self) -> datetime:
        import pytz
        tz = pytz.timezone(self.config.timezone)
        return datetime.now(tz)

    def _window_duration_seconds(self, window: AnalysisWindow) -> float:
        sh, sm = parse_time(window.start)
        eh, em = parse_time(window.end)
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        if end_min < start_min:
            end_min += 24 * 60
        return (end_min - start_min) * 60.0

    def _next_window(self) -> tuple[AnalysisWindow, datetime]:
        now = self._now()
        best_window = None
        best_time = None
        for w in self.windows:
            occ = next_window_occurrence(w.start, now)
            if best_time is None or occ < best_time:
                best_time = occ
                best_window = w
        assert best_window is not None and best_time is not None
        return best_window, best_time

    async def _run_window(self, window: AnalysisWindow):
        now_str = self._now().strftime("%Y-%m-%d")
        start_dt = self._now()

        if self.db.has_result_for_window(now_str, window.name):
            logger.info(
                "Window %s already has a result for %s, skipping duplicate run",
                window.name,
                now_str,
            )
            return

        logger.info("Starting analysis window: %s (%s–%s)", window.name, window.start, window.end)

        # 1. Check stream availability
        available = await self.stream.is_available()
        if not available:
            logger.error("Stream unavailable at window start")
            self.db.insert_event("stream_unavailable", f"Window {window.name}: RTSP not accessible", "error")
            self.db.insert_result(
                date=now_str,
                window=window.name,
                start_time=start_dt.isoformat(),
                end_time=self._now().isoformat(),
                status="stream_unavailable",
                summary_text="视频流不可用，请检查桥接服务或摄像机在线状态。",
            )
            await self.notifier.notify_error(
                window_name=window.name,
                window_start=window.start,
                window_end=window.end,
                status="视频流不可用",
                description="本次未完成分析，请检查桥接服务或摄像机在线状态。",
            )
            return

        # 2. Initialize behavior analyzer
        analyzer = BehaviorAnalyzer(self.config)

        def frame_callback(frame, relative_time):
            analyzer.process_frame(frame, relative_time)

        # 3. Collect frames and analyze in real-time (with clip recording)
        duration = self._window_duration_seconds(window)
        tag = f"{now_str}_{window.name}"
        collect_result = await self.stream.collect(
            duration_seconds=duration,
            frame_callback=frame_callback,
            window_tag=tag,
            enable_clip_recording=True,
        )

        end_dt = self._now()

        if not collect_result["success"]:
            logger.error("Frame collection failed")
            self.db.insert_event("collection_failed", f"Window {window.name}: no frames collected", "error")
            self.db.insert_result(
                date=now_str,
                window=window.name,
                start_time=start_dt.isoformat(),
                end_time=end_dt.isoformat(),
                status="analysis_failed",
                summary_text="视频采集失败，未获取到有效帧。",
            )
            await self.notifier.notify_error(
                window_name=window.name,
                window_start=window.start,
                window_end=window.end,
                status="采集失败",
                description="视频采集失败，未获取到有效帧。",
            )
            analyzer.close()
            return

        # 4. Get analysis result
        result = analyzer.get_result(end_time=collect_result["duration"])

        # 5. Save best evidence frames
        frame_paths = analyzer.save_evidence_frames(
            tag=tag,
            frames_dir=self.config.storage_frames_dir,
        )
        analyzer.close()

        # 6. Extract clip segments from full recording
        evidence_clips: list[str] = []
        full_clip = collect_result.get("full_clip_path")

        if full_clip:
            # Extract best brush segment
            if result["brush_segments"]:
                best_brush = max(result["brush_segments"], key=lambda s: s[1] - s[0])
                clip_out = str(Path(self.config.storage_clips_dir) / f"{tag}_brush_clip.mp4")
                if self.stream.extract_clip_segment(full_clip, best_brush[0], best_brush[1], clip_out, padding=3.0):
                    evidence_clips.append(clip_out)

            # Extract best facewash segment
            if result["facewash_segments"]:
                best_fw = max(result["facewash_segments"], key=lambda s: s[1] - s[0])
                clip_out = str(Path(self.config.storage_clips_dir) / f"{tag}_facewash_clip.mp4")
                if self.stream.extract_clip_segment(full_clip, best_fw[0], best_fw[1], clip_out, padding=3.0):
                    evidence_clips.append(clip_out)

            # Clean up full clip after extraction
            try:
                Path(full_clip).unlink()
                logger.info("Deleted full clip: %s", full_clip)
            except Exception as e:
                logger.warning("Failed to delete full clip: %s", e)

        # Determine evidence frame path for DB (prefer brush, fallback facewash)
        evidence_frame = frame_paths.get("brush") or frame_paths.get("facewash")
        evidence_clip = evidence_clips[0] if evidence_clips else None

        logger.info(
            "Window %s analyzed: toothbrush=%s(%ds), facewash=%s(%ds), frames=%d, clips=%d",
            window.name,
            result["toothbrush_grade"],
            result["toothbrush_seconds"],
            result["facewash_grade"],
            result["facewash_seconds"],
            len(frame_paths),
            len(evidence_clips),
        )

        result_id = self.db.insert_result(
            date=now_str,
            window=window.name,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            status="success",
            toothbrush_grade=result["toothbrush_grade"],
            facewash_grade=result["facewash_grade"],
            toothbrush_seconds=result["toothbrush_seconds"],
            facewash_seconds=result["facewash_seconds"],
            rinse_detected=result["rinse_detected"],
            summary_text=result["summary_text"],
            evidence_frame_path=evidence_frame,
            evidence_clip_path=evidence_clip,
        )
        logger.info("Result saved to DB, id=%s", result_id)

        # 7. Notify with attachments
        attachments = []
        for p in frame_paths.values():
            attachments.append(Path(p))
        for c in evidence_clips:
            attachments.append(Path(c))

        await self.notifier.notify_result(
            window_name=window.name,
            window_start=window.start,
            window_end=window.end,
            toothbrush_grade=result["toothbrush_grade"],
            facewash_grade=result["facewash_grade"],
            summary=result["summary_text"],
            evidence_frame_path=evidence_frame,
            attachments=attachments,
        )

        self.db.insert_event("window_completed", f"Window {window.name} analyzed successfully", "info")

    async def _loop(self):
        while self._running:
            window, target_time = self._next_window()
            now = self._now()
            wait_seconds = (target_time - now).total_seconds()

            # Check if we are already inside a window (e.g. after restart)
            for w in self.windows:
                sh, sm = parse_time(w.start)
                eh, em = parse_time(w.end)
                start_min = sh * 60 + sm
                end_min = eh * 60 + em
                now_min = now.hour * 60 + now.minute
                if end_min < start_min:
                    end_min += 24 * 60
                if start_min <= now_min < end_min:
                    window = w
                    wait_seconds = 0
                    break

            if wait_seconds > 0:
                logger.info("Next window '%s' at %s, waiting %.0f seconds", window.name, target_time, wait_seconds)
                await asyncio.sleep(min(wait_seconds, 60))
                continue

            await self._run_window(window)
            # After running, sleep a bit to avoid immediate re-trigger
            await asyncio.sleep(60)

    def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")
