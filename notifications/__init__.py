"""JurisMon notifications: transactional email for operational alerts."""

from notifications.mailer import Mailer
from notifications.crawl_report import build_report, send_crawl_report

__all__ = ["Mailer", "build_report", "send_crawl_report"]
