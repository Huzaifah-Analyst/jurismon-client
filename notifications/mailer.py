"""JurisMon transactional email via Resend.

Used for operational alerts to the administrator. Sending is deliberately
fail-soft: a mail outage must never take down a crawl, because the crawl is the
product and the email is only a notification about it.

Requires RESEND_API_KEY and MAIL_FROM. Without them the module is inert and
says so once, rather than raising on every call.
"""

import os
import logging
from typing import Optional, List, Dict, Any

import requests

logger = logging.getLogger("jurismon.mailer")

RESEND_ENDPOINT = "https://api.resend.com/emails"
REQUEST_TIMEOUT = 15


class Mailer:
    """Minimal Resend client.

    Resend's REST API is a single POST, so the official SDK would be an extra
    dependency for one request.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        mail_from: Optional[str] = None,
        default_to: Optional[str] = None,
    ):
        self.api_key = (api_key if api_key is not None else os.getenv("RESEND_API_KEY", "")).strip()
        self.mail_from = (
            mail_from if mail_from is not None else os.getenv("MAIL_FROM", "")
        ).strip()
        if default_to is not None:
            # An explicit empty string means "no recipient", not "fall back to
            # the environment" - otherwise a caller cannot suppress the default.
            self.default_to = default_to.strip()
        else:
            self.default_to = (
                os.getenv("ALERT_EMAIL", "").strip()
                or os.getenv("ADMIN_EMAIL", "").strip()
            )

    def is_configured(self) -> bool:
        return bool(self.api_key and self.mail_from)

    def send(
        self,
        subject: str,
        html: str,
        to: Optional[List[str]] = None,
        text: Optional[str] = None,
    ) -> bool:
        """Sends one email. Returns True only on a confirmed send.

        Never raises: every caller is a side path to some more important job.
        """
        recipients = to or ([self.default_to] if self.default_to else [])

        if not self.is_configured():
            logger.info(
                "Email not sent (%s): RESEND_API_KEY and MAIL_FROM are not configured.",
                subject,
            )
            return False

        if not recipients:
            logger.warning("Email not sent (%s): no recipient configured.", subject)
            return False

        payload: Dict[str, Any] = {
            "from": self.mail_from,
            "to": recipients,
            "subject": subject,
            "html": html,
        }
        if text:
            payload["text"] = text

        try:
            res = requests.post(
                RESEND_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.error("Email transport failed (%s): %s", subject, exc)
            return False

        if res.status_code in (200, 201):
            logger.info("Email sent: %s", subject)
            return True

        # 403 here almost always means the sending domain is not yet verified
        # in Resend, which is a setup step rather than a code fault.
        detail = res.text[:300]
        logger.error("Resend rejected the email (%s): %s %s", subject, res.status_code, detail)
        return False
