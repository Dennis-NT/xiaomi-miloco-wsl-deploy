import asyncio
import logging
import signal
import sys
from pathlib import Path

# Ensure project root on path for config.yaml discovery
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.config import Config
from analyzer.db import Database
from analyzer.notifier_email import EmailNotifier
from analyzer.scheduler import Scheduler
from analyzer.stream_reader import StreamReader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class AnalyzerApp:
    def __init__(self):
        self.config = Config("config.yaml")
        self.db = Database(self.config.storage_db_path)
        self.notifier = EmailNotifier(
            smtp_host=self.config.email_smtp_host,
            smtp_port=self.config.email_smtp_port,
            smtp_user=self.config.email_smtp_user,
            smtp_password=self.config.email_smtp_password,
            from_addr=self.config.email_from_addr,
            to_addr=self.config.email_to_addr,
            use_tls=self.config.email_use_tls,
            enabled=self.config.email_enabled,
        )
        self.stream = StreamReader(
            rtsp_url=self.config.stream_rtsp_url,
            sample_fps=self.config.analysis_sample_fps,
            reconnect_retries=self.config.stream_reconnect_retries,
            frames_dir=self.config.storage_frames_dir,
        )
        self.scheduler = Scheduler(
            config=self.config,
            db=self.db,
            notifier=self.notifier,
            stream_reader=self.stream,
        )
        self._shutdown_event = asyncio.Event()

    def _on_signal(self):
        logger.info("Shutdown signal received")
        self._shutdown_event.set()

    async def run(self):
        logger.info("Analyzer starting...")
        logger.info("Timezone: %s", self.config.timezone)
        logger.info("RTSP URL: %s", self.config.stream_rtsp_url)
        logger.info("Email enabled: %s", self.config.email_enabled)

        self.scheduler.start()

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        await self.scheduler.stop()
        logger.info("Analyzer stopped")


def main():
    app = AnalyzerApp()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, app._on_signal)

    try:
        loop.run_until_complete(app.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
