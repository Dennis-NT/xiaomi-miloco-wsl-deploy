import os
import re
import yaml
from pathlib import Path
from typing import Any


class Config:
    def __init__(self, path: str = "config.yaml"):
        self._path = path
        self._data = self._load()

    def _load(self) -> dict:
        with open(self._path, "r", encoding="utf-8") as f:
            raw = f.read()
        # Replace ${VAR} and ${VAR:-default} patterns
        raw = self._interpolate_env(raw)
        return yaml.safe_load(raw)

    @staticmethod
    def _interpolate_env(text: str) -> str:
        def replacer(match):
            key = match.group(1)
            default = match.group(2)
            return os.getenv(key, default if default is not None else "")
        return re.sub(r"\$\{(\w+)(?::-([^}]*))?\}", replacer, text)

    def get(self, *keys: str, default: Any = None) -> Any:
        d = self._data
        for key in keys:
            if isinstance(d, dict) and key in d:
                d = d[key]
            else:
                return default
        return d

    @property
    def timezone(self) -> str:
        return self.get("timezone", default="Asia/Shanghai")

    @property
    def windows(self) -> list[dict]:
        return self.get("windows", default=[])

    @property
    def stream_rtsp_url(self) -> str:
        return self.get("stream", "rtsp_url", default="rtsp://127.0.0.1:8554/xiaomi_cam")

    @property
    def stream_reconnect_retries(self) -> int:
        return int(self.get("stream", "reconnect_retries", default=3))

    @property
    def analysis_sample_fps(self) -> int:
        return int(self.get("analysis", "sample_fps", default=2))

    @property
    def analysis_roi_enabled(self) -> bool:
        return bool(self.get("analysis", "roi_enabled", default=False))

    @property
    def analysis_pose_model(self) -> str:
        return self.get("analysis", "pose_model", default="lite")

    @property
    def storage_frames_dir(self) -> str:
        return self.get("storage", "frames_dir", default="./data/frames")

    @property
    def storage_clips_dir(self) -> str:
        return self.get("storage", "clips_dir", default="./data/clips")

    @property
    def storage_db_path(self) -> str:
        return self.get("storage", "db_path", default="./data/db/app.db")

    @property
    def storage_retention_days_frames(self) -> int:
        return int(self.get("storage", "retention_days_frames", default=7))

    @property
    def storage_retention_days_clips(self) -> int:
        return int(self.get("storage", "retention_days_clips", default=7))

    @property
    def storage_retention_days_logs(self) -> int:
        return int(self.get("storage", "retention_days_logs", default=90))

    @property
    def email_enabled(self) -> bool:
        val = self.get("email", "enabled", default=True)
        if isinstance(val, bool):
            return val
        return str(val).lower() == "true"

    @property
    def email_smtp_host(self) -> str:
        return self.get("email", "smtp_host", default="")

    @property
    def email_smtp_port(self) -> int:
        return int(self.get("email", "smtp_port", default=587))

    @property
    def email_smtp_user(self) -> str:
        return self.get("email", "smtp_user", default="")

    @property
    def email_smtp_password(self) -> str:
        return self.get("email", "smtp_password", default="")

    @property
    def email_from_addr(self) -> str:
        return self.get("email", "from_addr", default="")

    @property
    def email_to_addr(self) -> str:
        return self.get("email", "to_addr", default="")

    @property
    def email_use_tls(self) -> bool:
        val = self.get("email", "use_tls", default="true")
        if isinstance(val, bool):
            return val
        return str(val).lower() == "true"

    def analysis_threshold(self, key: str) -> int:
        return int(self.get("analysis", key, default=0))

    def hands_config(self, key: str, default: Any = None) -> Any:
        return self.get("hands", key, default=default)
