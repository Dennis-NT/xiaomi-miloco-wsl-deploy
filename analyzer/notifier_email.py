import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_addr: str,
        to_addr: str,
        use_tls: bool = True,
        enabled: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.use_tls = use_tls
        self.enabled = enabled

    def _send_sync(
        self,
        subject: str,
        body_text: str,
        attachments: Optional[List[Path]] = None,
    ) -> bool:
        if not self.enabled:
            logger.info("Email notifier is disabled, skipping send.")
            return True

        msg = MIMEMultipart()
        msg["From"] = self.from_addr
        msg["To"] = self.to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        attachments = attachments or []
        for filepath in attachments:
            if not filepath.exists():
                logger.warning("Attachment not found, skipping: %s", filepath)
                continue
            part = MIMEBase("application", "octet-stream")
            with open(filepath, "rb") as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{filepath.name}"',
            )
            msg.attach(part)

        try:
            # Port 465 uses SMTP_SSL (immediate TLS), 587 uses STARTTLS
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)

            with server:
                if self.use_tls and self.smtp_port != 465:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info("Email sent successfully to %s (%d attachments)", self.to_addr, len(attachments))
            return True
        except Exception as e:
            logger.error("Failed to send email: %s", e)
            return False

    async def send(
        self,
        subject: str,
        body_text: str,
        attachments: Optional[List[Path]] = None,
    ) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._send_sync, subject, body_text, attachments
        )

    async def notify_result(
        self,
        window_name: str,
        window_start: str,
        window_end: str,
        toothbrush_grade: str,
        facewash_grade: str,
        summary: str,
        evidence_frame_path: Optional[str] = None,
        attachments: Optional[List[Path]] = None,
    ) -> bool:
        subject = f"【洗漱监督结果】{window_name} ({window_start}–{window_end})"
        body = f"""今日{window_name}洗漱结果（{window_start}–{window_end}）

刷牙：{toothbrush_grade}
洗脸：{facewash_grade}
说明：{summary}
"""
        all_attachments = list(attachments) if attachments else []
        if evidence_frame_path:
            p = Path(evidence_frame_path)
            if p.exists() and p not in all_attachments:
                all_attachments.append(p)
        return await self.send(subject, body, all_attachments)

    async def notify_error(
        self,
        window_name: str,
        window_start: str,
        window_end: str,
        status: str,
        description: str,
    ) -> bool:
        subject = f"【洗漱系统异常】{window_name}"
        body = f"""【洗漱系统异常】
时间窗：{window_name} {window_start}–{window_end}
状态：{status}
说明：{description}
"""
        return await self.send(subject, body)
