"""Builds and sends the daily crawl report.

An unattended daily crawl fails silently by default: the log is on the server
and nobody reads it. This turns a failed run into something that reaches the
operator.

By default a report is only sent when something needs attention, so a healthy
run stays quiet and the alerts keep meaning something. Set
ALERT_ON_EVERY_CRAWL=true to receive a report from every run.
"""

import os
import html
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from notifications.mailer import Mailer

logger = logging.getLogger("jurismon.crawl_report")

STYLES = {
    "body": "font-family:-apple-system,Segoe UI,Arial,sans-serif;color:#1a1d23;line-height:1.5;",
    "h": "margin:0 0 4px;font-size:18px;color:#1f4e79;",
    "muted": "color:#5b6472;font-size:13px;margin:0 0 18px;",
    "cell": "padding:6px 10px;border:1px solid #dde1e7;font-size:13px;",
    "head": "padding:6px 10px;border:1px solid #1f4e79;background:#1f4e79;color:#fff;"
            "font-size:13px;text-align:left;",
}


def _should_send(failed: int, partial: int = 0) -> bool:
    if os.getenv("ALERT_ON_EVERY_CRAWL", "").strip().lower() in ("1", "true", "yes"):
        return True
    return failed > 0 or partial > 0


def build_report(
    succeeded: int,
    failed: int,
    documents: int,
    diffs: int,
    duration_seconds: float,
    failures: Optional[List[Dict[str, str]]] = None,
    partial: int = 0,
    filtered: int = 0,
) -> Dict[str, str]:
    """Returns the subject and HTML body for a crawl report."""
    total = succeeded + partial + failed
    when = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    # The subject counts sources that stored nothing. A source that stored most
    # of its documents and errored on one belongs in the body, not in a subject
    # line the operator reads as an outage.
    if failed:
        subject = f"JurisMon: {failed} of {total} sources captured nothing"
    elif partial:
        subject = f"JurisMon: {partial} of {total} sources partly captured"
    else:
        subject = f"JurisMon: daily crawl clean ({succeeded} sources)"

    rows = "".join(
        f"<tr><td style='{STYLES['cell']}'>{label}</td>"
        f"<td style='{STYLES['cell']}'><strong>{value}</strong></td></tr>"
        for label, value in [
            ("Sources fully captured", succeeded),
            ("Sources partly captured", partial),
            ("Sources captured nothing", failed),
            ("Documents processed", documents),
            ("Filtered as non-documents", filtered),
            ("Statutory diffs created", diffs),
            ("Duration", f"{duration_seconds:.0f}s"),
        ]
    )

    detail = ""
    if failures:
        # Truncated because a broad outage would otherwise produce an email
        # too long to be read at all.
        shown = failures[:25]
        items = "".join(
            f"<tr><td style='{STYLES['cell']}'>{html.escape(str(f.get('source_name', 'Unknown')))}</td>"
            f"<td style='{STYLES['cell']};color:{'#9a2b2b' if f.get('outcome') != 'partial' else '#8a6100'}'>"
            f"{'Partly captured' if f.get('outcome') == 'partial' else 'Captured nothing'}</td>"
            f"<td style='{STYLES['cell']};color:#9a2b2b'>{html.escape(str(f.get('error', ''))[:160])}</td></tr>"
            for f in shown
        )
        more = (
            f"<p style=\"{STYLES['muted']}\">and {len(failures) - len(shown)} more.</p>"
            if len(failures) > len(shown) else ""
        )
        detail = f"""
        <h3 style="{STYLES['h']};font-size:15px;margin-top:22px;">What needs attention</h3>
        <table style="border-collapse:collapse;width:100%;">
          <tr><th style="{STYLES['head']}">Source</th><th style="{STYLES['head']}">Outcome</th>
              <th style="{STYLES['head']}">Detail</th></tr>
          {items}
        </table>{more}"""

    body = f"""<div style="{STYLES['body']}">
      <h2 style="{STYLES['h']}">JurisMon daily crawl</h2>
      <p style="{STYLES['muted']}">{when}</p>
      <table style="border-collapse:collapse;">{rows}</table>
      {detail}
      <p style="{STYLES['muted']};margin-top:24px;">
        Sent automatically by JurisMon. Full logs are on the server at
        /var/log/jurismon/.
      </p>
    </div>"""

    return {"subject": subject, "html": body}


def send_crawl_report(
    succeeded: int,
    failed: int,
    documents: int,
    diffs: int,
    duration_seconds: float,
    failures: Optional[List[Dict[str, str]]] = None,
    mailer: Optional[Mailer] = None,
    partial: int = 0,
    filtered: int = 0,
) -> bool:
    """Sends the report when it is worth sending. Never raises."""
    try:
        if not _should_send(failed, partial):
            logger.info("Crawl clean; no report sent.")
            return False

        report = build_report(
            succeeded, failed, documents, diffs, duration_seconds, failures,
            partial=partial, filtered=filtered,
        )
        return (mailer or Mailer()).send(subject=report["subject"], html=report["html"])
    except Exception as exc:
        # The crawl has already done its work by this point; reporting on it
        # must not turn a successful run into a failed one.
        logger.error("Could not send crawl report: %s", exc)
        return False
