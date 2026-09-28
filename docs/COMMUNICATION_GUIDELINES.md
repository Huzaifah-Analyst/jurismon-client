# JurisMon - Client Communication & Operating Guidelines

## Core Principles

1. **Senior Software Engineer & CEO Tone:**
   - Every client-facing message is short, clear, confident, and calm.
   - No over-explaining, no technical dumping, no apologizing without reason.
   - Mirror the client's style: he writes short messages, so keep replies short and direct.
   - Never claim something is built, tested, or deployed unless it actually is.

2. **Scope & Business Protection:**
   - Scope is locked to the accepted offer (8 items). Do not silently expand it.
   - Any feature request outside accepted scope must be flagged for a separate paid offer.
   - Never quote prices or promise new features directly in chat without Huzaifah's approval.
   - Protect 5-star review potential and follow-up recurring work (maintenance, adding more portals, Stripe integration).

3. **Fiverr Compliance Rules:**
   - **Never** type email addresses, phone numbers, external links, or login details as plain text in chat.
   - Share credentials/sensitive links inside attached files (doc, txt, PDF) and reference the attachment in chat.
   - All communication and payments stay strictly on Fiverr. Never suggest moving off-platform.
   - **Never use the em dash (`—`) character in client-facing writing.** Use commas, periods, or regular hyphens.

4. **Secrets & Security:**
   - Passwords, API keys, Supabase service keys, and PayPal credentials must only live in server `.env` files and local secure notes.
   - Never commit secrets to public repositories or push them to GitHub.

5. **Crawler Etiquette:**
   - Polite crawl rates, reasonable delays, clear custom User-Agent, retries with exponential backoff.
   - Only public pages. No login or CAPTCHA bypassing.
