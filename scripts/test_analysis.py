#!/usr/bin/env python3
"""
Run a one-off 60-second analysis to test the full pipeline immediately.
"""
import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.config import Config
from analyzer.db import Database
from analyzer.stream_reader import StreamReader
from analyzer.behavior_analyzer import BehaviorAnalyzer
from analyzer.notifier_email import EmailNotifier


def main():
    config = Config("config.yaml")
    db = Database(config.storage_db_path)
    stream = StreamReader(
        rtsp_url=config.stream_rtsp_url,
        sample_fps=config.analysis_sample_fps,
        frames_dir=config.storage_frames_dir,
        clips_dir=config.storage_clips_dir,
    )
    notifier = EmailNotifier(
        smtp_host=config.email_smtp_host,
        smtp_port=config.email_smtp_port,
        smtp_user=config.email_smtp_user,
        smtp_password=config.email_smtp_password,
        from_addr=config.email_from_addr,
        to_addr=config.email_to_addr,
        use_tls=config.email_use_tls,
        enabled=config.email_enabled,
    )

    # Check stream
    print("[1/6] Checking RTSP stream...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    available = loop.run_until_complete(stream.is_available())
    if not available:
        print("ERROR: RTSP stream not available!")
        print("Make sure go2rtc and micam1 are running.")
        return 1
    print("  Stream OK")

    # Run 60s analysis
    print("[2/6] Starting 60-second analysis...")
    analyzer = BehaviorAnalyzer(config)

    def frame_callback(frame, relative_time):
        analyzer.process_frame(frame, relative_time)

    tag = "test_20260503"
    result = loop.run_until_complete(stream.collect(
        duration_seconds=60.0,
        frame_callback=frame_callback,
        window_tag=tag,
        enable_clip_recording=True,
    ))

    if not result["success"]:
        print("ERROR: Frame collection failed!")
        analyzer.close()
        return 1

    print(f"  Collected {result['frame_count']} frames in {result['duration']:.1f}s")

    # Analyze
    print("[3/6] Analyzing behavior...")
    analysis = analyzer.get_result(end_time=result["duration"])
    print(f"  Toothbrush: {analysis['toothbrush_grade']} ({analysis['toothbrush_seconds']}s)")
    print(f"  Facewash:   {analysis['facewash_grade']} ({analysis['facewash_seconds']}s)")
    print(f"  Summary:    {analysis['summary_text']}")
    print(f"  Pose detections:  {analysis['pose_detection_count']}")
    print(f"  Hands detections: {analysis['hands_detection_count']}")

    # Save evidence frames
    print("[4/6] Saving evidence frames...")
    frame_paths = analyzer.save_evidence_frames(tag=tag, frames_dir=config.storage_frames_dir)
    for k, v in frame_paths.items():
        print(f"  {k}: {v}")
    analyzer.close()

    # Extract clips
    print("[5/6] Extracting evidence clips...")
    evidence_clips = []
    full_clip = result.get("full_clip_path")
    if full_clip:
        if analysis["brush_segments"]:
            best_brush = max(analysis["brush_segments"], key=lambda s: s[1] - s[0])
            clip_out = str(Path(config.storage_clips_dir) / f"{tag}_brush_clip.mp4")
            if stream.extract_clip_segment(full_clip, best_brush[0], best_brush[1], clip_out, padding=3.0):
                evidence_clips.append(clip_out)
                print(f"  Brush clip: {clip_out}")

        if analysis["facewash_segments"]:
            best_fw = max(analysis["facewash_segments"], key=lambda s: s[1] - s[0])
            clip_out = str(Path(config.storage_clips_dir) / f"{tag}_facewash_clip.mp4")
            if stream.extract_clip_segment(full_clip, best_fw[0], best_fw[1], clip_out, padding=3.0):
                evidence_clips.append(clip_out)
                print(f"  Facewash clip: {clip_out}")

        try:
            Path(full_clip).unlink()
            print(f"  Deleted full clip")
        except Exception as e:
            print(f"  Warning: could not delete full clip: {e}")

    # Save to DB
    print("[6/6] Saving result to DB and sending email...")
    evidence_frame = frame_paths.get("brush") or frame_paths.get("facewash")
    evidence_clip = evidence_clips[0] if evidence_clips else None

    result_id = db.insert_result(
        date="2026-05-03",
        window="test",
        start_time="test",
        end_time="test",
        status="success",
        toothbrush_grade=analysis["toothbrush_grade"],
        facewash_grade=analysis["facewash_grade"],
        toothbrush_seconds=analysis["toothbrush_seconds"],
        facewash_seconds=analysis["facewash_seconds"],
        summary_text=analysis["summary_text"],
        evidence_frame_path=evidence_frame,
        evidence_clip_path=evidence_clip,
    )
    print(f"  DB record id: {result_id}")

    # Send test email
    attachments = [Path(p) for p in frame_paths.values()] + [Path(c) for c in evidence_clips]
    sent = loop.run_until_complete(notifier.notify_result(
        window_name="测试窗口",
        window_start="now",
        window_end="+60s",
        toothbrush_grade=analysis["toothbrush_grade"],
        facewash_grade=analysis["facewash_grade"],
        summary=analysis["summary_text"],
        evidence_frame_path=evidence_frame,
        attachments=attachments,
    ))
    print(f"  Email sent: {'YES' if sent else 'FAILED'}")

    print("\n=== Test Complete ===")
    loop.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
