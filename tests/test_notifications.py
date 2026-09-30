"""Tests for operational email.

Email is a side path: it reports on the crawl rather than doing it. So the
behaviour that matters most here is what happens when sending fails - a mail
outage, a missing API key or an unverified sending domain must never turn a
successful crawl into a failed one.
"""

import unittest
from unittest.mock import patch, MagicMock

import requests

from notifications.mailer import Mailer
from notifications.crawl_report import build_report, send_crawl_report, _should_send


def _ok(status=200):
    res = MagicMock()
    res.status_code = status
    res.text = ""
    return res


class TestMailerConfiguration(unittest.TestCase):

    def test_not_configured_without_an_api_key(self):
        self.assertFalse(Mailer(api_key="", mail_from="a@b.com").is_configured())

    def test_not_configured_without_a_sender(self):
        self.assertFalse(Mailer(api_key="re_x", mail_from="").is_configured())

    def test_configured_with_both(self):
        self.assertTrue(Mailer(api_key="re_x", mail_from="a@b.com").is_configured())

    def test_unconfigured_mailer_declines_quietly(self):
        """A server without email set up must not raise on every crawl."""
        mailer = Mailer(api_key="", mail_from="", default_to="ops@example.com")
        with patch("notifications.mailer.requests.post") as post:
            self.assertFalse(mailer.send("Subject", "<p>body</p>"))
        post.assert_not_called()

    def test_declines_when_there_is_no_recipient(self):
        mailer = Mailer(api_key="re_x", mail_from="a@b.com", default_to="")
        with patch("notifications.mailer.requests.post") as post:
            self.assertFalse(mailer.send("Subject", "<p>body</p>"))
        post.assert_not_called()


class TestMailerSending(unittest.TestCase):

    def setUp(self):
        self.mailer = Mailer(
            api_key="re_test", mail_from="JurisMon <noreply@jurismon.com>",
            default_to="admin@jurismon.com",
        )

    def test_posts_the_expected_payload(self):
        with patch("notifications.mailer.requests.post", return_value=_ok(200)) as post:
            self.assertTrue(self.mailer.send("Crawl failed", "<p>detail</p>"))

        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["from"], "JurisMon <noreply@jurismon.com>")
        self.assertEqual(kwargs["json"]["to"], ["admin@jurismon.com"])
        self.assertEqual(kwargs["json"]["subject"], "Crawl failed")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test")

    def test_explicit_recipients_override_the_default(self):
        with patch("notifications.mailer.requests.post", return_value=_ok(200)) as post:
            self.mailer.send("S", "<p>b</p>", to=["someone@example.com"])
        self.assertEqual(post.call_args.kwargs["json"]["to"], ["someone@example.com"])

    def test_unverified_domain_is_reported_not_raised(self):
        """Resend answers 403 until the sending domain is verified."""
        res = MagicMock()
        res.status_code = 403
        res.text = '{"message":"The jurismon.com domain is not verified."}'

        with patch("notifications.mailer.requests.post", return_value=res):
            with self.assertLogs("jurismon.mailer", level="ERROR") as captured:
                self.assertFalse(self.mailer.send("S", "<p>b</p>"))

        self.assertTrue(any("403" in line for line in captured.output))

    def test_network_failure_is_contained(self):
        with patch("notifications.mailer.requests.post",
                   side_effect=requests.ConnectionError("dns failure")):
            self.assertFalse(self.mailer.send("S", "<p>b</p>"))


class TestReportContent(unittest.TestCase):

    def test_failure_count_leads_the_subject(self):
        r = build_report(succeeded=38, failed=3, documents=120, diffs=4, duration_seconds=95)
        self.assertEqual(r["subject"], "JurisMon: 3 of 41 sources failed")

    def test_clean_run_reads_as_clean(self):
        r = build_report(succeeded=41, failed=0, documents=120, diffs=4, duration_seconds=95)
        self.assertIn("clean", r["subject"])

    def test_body_carries_the_run_figures(self):
        body = build_report(41, 0, 137, 9, 212.4)["html"]
        for value in ("41", "137", "9", "212s"):
            self.assertIn(value, body)

    def test_failures_are_named_with_their_error(self):
        body = build_report(
            38, 1, 100, 2, 60,
            failures=[{"source_name": "City of Austin", "error": "HTTP 404 Not Found"}],
        )["html"]
        self.assertIn("City of Austin", body)
        self.assertIn("HTTP 404", body)

    def test_error_text_is_escaped(self):
        """Error strings come from remote servers, so they are not trusted."""
        body = build_report(
            1, 1, 0, 0, 5,
            failures=[{"source_name": "<script>alert(1)</script>", "error": "<img onerror=x>"}],
        )["html"]
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_long_failure_lists_are_truncated(self):
        failures = [{"source_name": f"Source {i}", "error": "down"} for i in range(60)]
        body = build_report(5, 60, 0, 0, 30, failures=failures)["html"]
        self.assertIn("and 35 more", body)
        self.assertNotIn("Source 40", body)


class TestSendPolicy(unittest.TestCase):

    def test_clean_runs_stay_quiet_by_default(self):
        """Alerts that arrive every day stop being read."""
        with patch.dict("os.environ", {}, clear=False):
            with patch("notifications.crawl_report.os.getenv", return_value=""):
                self.assertFalse(_should_send(0))
                self.assertTrue(_should_send(1))

    def test_every_crawl_can_be_reported_on_request(self):
        with patch("notifications.crawl_report.os.getenv", return_value="true"):
            self.assertTrue(_should_send(0))

    def test_no_mail_is_sent_for_a_clean_run(self):
        mailer = MagicMock()
        with patch("notifications.crawl_report._should_send", return_value=False):
            self.assertFalse(send_crawl_report(41, 0, 10, 1, 60, mailer=mailer))
        mailer.send.assert_not_called()

    def test_failures_trigger_a_send(self):
        mailer = MagicMock()
        mailer.send.return_value = True
        self.assertTrue(send_crawl_report(38, 3, 10, 1, 60, failures=[], mailer=mailer))
        mailer.send.assert_called_once()

    def test_a_broken_mailer_does_not_fail_the_crawl(self):
        """The crawl has already finished by the time this runs."""
        mailer = MagicMock()
        mailer.send.side_effect = Exception("mail server exploded")
        self.assertFalse(send_crawl_report(38, 3, 10, 1, 60, mailer=mailer))


if __name__ == "__main__":
    unittest.main()
