# ORDER P2-13 — Subscription Lifecycle Confirmation Emails

> **From**: Lead engineer
> **To**: Implementing agent (Antigravity)
> **Repo**: `jurismon-client` · **Branch**: `claude/sweet-babbage-fz7sbz`
> **Read first**: `docs/ai/rules.md` (Rule 7 and Rule 11 both apply)
> **Type**: Backend addition. No deployment.

---

## 1. Why

Phase 2 Part 1 was sold to the client with this bullet:

> *"Clear confirmation screens and confirmation emails"*

The screens shipped. The emails did not. There are exactly three `mailer.send()` call sites in the entire codebase (`api/main.py:813`, `:909`, `:973`) and all three are account email verification or password reset. A customer who pauses or cancels a paid subscription currently receives nothing in writing.

That is a billing event with no paper trail. For a legal-sector product it is also the kind of thing a disputing customer points at.

---

## 2. Current state (scanned, do not re-derive)

| Fact | Location |
| :--- | :--- |
| Mailer class (Resend, single POST, never raises) | `notifications/mailer.py:23` |
| `send(subject, html, to=None, text=None) -> bool` | `notifications/mailer.py:53` |
| Module-level instance | `api/main.py:76` — `mailer = Mailer()` |
| Existing HTML email style to match | `api/main.py:845-860` (OTP email) |
| Pause endpoint | `api/main.py:1220` |
| Resume endpoint | `api/main.py:1294` |
| Cancel endpoint | `api/main.py:1362` |
| Repo setters called after PayPal confirms | `db/repository.py:730`, `:761`, `:790` |
| Production | `b0d8bd4`, migrations through `007` applied |

---

## 3. Required work

### 3.1 Three emails

Send after — never before — PayPal has confirmed the action and the repository setter has succeeded. The existing endpoints already order it this way; keep that order.

| Trigger | Subject | Must state |
| :--- | :--- | :--- |
| Pause | `Your JurisMon subscription is paused` | Billing is suspended; access continues until the date in `access_until`; how to resume (link to `/account`); that no further charges will be taken while paused. |
| Resume | `Your JurisMon subscription is active again` | Billing has restarted; the next billing date; the amount and interval. |
| Cancel | `Your JurisMon subscription is cancelled` | Billing has stopped; access continues until the date in `access_until`; what happens after that date (search returns teaser results); that they can subscribe again any time. |

Every email must carry the real figures — plan name, amount, currency, the actual dates from the subscription row. **Rule 3**: no placeholder dates, no "soon", no invented amounts. Resolve plan metadata through the existing dynamic catalogue accessor, not a hardcoded `$49`.

Dates in the customer's email are human-readable (`6 November 2026`), not raw ISO timestamps.

### 3.2 A send must never break the action

`Mailer.send()` already swallows its own exceptions and returns a bool — do not wrap it in logic that can raise. If the send returns `False`:

- Log at WARNING with the subscription's external id and which email failed.
- **Still return the success response to the customer.** Their subscription genuinely is paused; failing the request because Resend was down would be a lie and would leave PayPal and the site disagreeing — the exact thing Part 1 was built to prevent.
- The response body should carry the fact, e.g. `"email_sent": false`, so the account page can tell them "we couldn't email you a confirmation" rather than silently pretending.

### 3.3 Email content rules

- Plain HTML, inline styles, matching the OTP email at `api/main.py:845`. No new template engine, no new dependency.
- Supply the `text=` fallback as well as `html=`. Some legal-sector mail clients strip HTML.
- **Rule 7**: never put the PayPal subscription id, an internal user id, a token, or an admin address in a customer email. Plan name, amount, dates and a link to `/account` only.
- Support address is `support@jurismon.com`, which is already used on the legal pages.

### 3.4 Shared helper

Three near-identical blocks inline in three endpoints will rot. Put one helper in `api/main.py` (or `notifications/`) that takes the event kind and the subscription row and builds + sends the message. The endpoints call it in one line.

### 3.5 Tests

Mock the mailer — **no live Resend calls in the suite**, ever.

- Pause, resume and cancel each send exactly one email, with the right subject.
- The email is sent only after PayPal returns success: assert that a failed PayPal call sends nothing.
- The body contains the real plan name, amount and `access_until` date from the fixture.
- A mailer returning `False` still produces a 200 response, and the body reports `email_sent: false`.
- The body contains no PayPal subscription id and no internal user id — assert explicitly.

---

## 4. Out of scope

- No deployment, no SSH. Production stays at `b0d8bd4`.
- No migration. No schema change.
- No changes to the PayPal provider, the crawler, `config/`, or `frontend/` beyond what §3.2's `email_sent` flag requires on the account page (a single line of copy is acceptable; a redesign is not).
- No marketing or upsell content in these emails. They are transactional. Adding promotional copy to a transactional email is a CAN-SPAM problem and the client has not asked for it.
- No push to the `client` remote. `origin` only.

---

## 5. Acceptance criteria

1. `./venv/Scripts/python.exe -m pytest -q` → 286 + new tests, all green.
2. Pause, resume and cancel each produce one correctly addressed email with real figures.
3. A dead mailer does not fail the subscription action.
4. `git diff --stat` touches only `api/main.py`, `notifications/`, the test module, `frontend/account.html` (one line), and `docs/ai/tasks.md`.

---

## 6. Report back

- Commit SHA, `git diff --stat`, pytest tail.
- The three rendered emails as plain text, verbatim, so I can read what a paying customer will actually receive.
- Confirmation that no live email was sent during development or testing, and how you ensured it.
