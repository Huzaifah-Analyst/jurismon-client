# Frontend Standard

> **Purpose**: the benchmark a good frontend is measured against.
> **Use**: this document defines the target. `frontend-audit.md` scores JurisMon against it. `ORDER-P2-16.md` is the fix plan that follows.
> **Written**: Oct 7, 2026. Vanilla HTML, CSS and JS, no framework, because that is what this project uses.

---

## 1. First paint

| # | Rule | Why it matters |
| :-- | :--- | :--- |
| 1.1 | The page shell renders before any data arrives. | A blank screen while fetching feels broken. |
| 1.2 | Nothing above the fold waits on a network call. | Logo, nav and headings are static. They should never flicker. |
| 1.3 | Critical CSS is inline or in the same document. | An external stylesheet blocks paint. |
| 1.4 | Fonts use `font-display: swap` and are preconnected. | Otherwise text is invisible until the font lands. |
| 1.5 | No layout shift after data arrives (CLS near 0). | Reserve the space before you fill it. |

---

## 2. Loading states

A good frontend has **five** states per data region, not two.

| State | What the user sees |
| :--- | :--- |
| Idle | Nothing requested yet. |
| Loading | A skeleton shaped like the real content. |
| Success | Real data. |
| Empty | A plain sentence saying there is nothing, not a blank box. |
| Error | What failed and what to do next. Never a silent blank. |

Rules:

- **Skeletons, not spinners**, for anything with a known shape (cards, tables, rows).
- A spinner is only acceptable for a short action with no shape, such as a button submit.
- The skeleton must match the final layout, so nothing jumps when data lands.
- Never show stale data and a loading state at the same time.
- Loading states should appear instantly, not after a delay.

---

## 3. Stale content on refresh

This is the most common cause of "I refreshed and saw the old page".

| # | Rule |
| :-- | :--- |
| 3.1 | HTML is served with `Cache-Control: no-cache, must-revalidate`. The browser must re-check every time. |
| 3.2 | CSS, JS and images are served with a content hash in the filename and `Cache-Control: max-age=31536000, immutable`. |
| 3.3 | Never serve HTML with a long cache. The browser will keep showing yesterday's markup. |
| 3.4 | If a service worker exists, it must not serve stale HTML. |
| 3.5 | A hard refresh should never be needed to see a deploy. If it is, caching is wrong. |

---

## 4. Data fetching

| # | Rule | Why |
| :-- | :--- | :--- |
| 4.1 | One function owns one endpoint. No duplicated fetch logic. | Two copies drift apart. |
| 4.2 | Every fetch handles non-2xx explicitly. | `res.json()` on a 500 throws a confusing error. |
| 4.3 | Every fetch has a timeout and an abort path. | A hung request leaves a permanent skeleton. |
| 4.4 | Stale responses are discarded when a newer request has started. | Otherwise an old search overwrites a new one. |
| 4.5 | Independent calls run in parallel, not in sequence. | Sequential calls add up. |
| 4.6 | Auth failure (401 or 403) has one shared handler. | Each call inventing its own is how sessions break. |
| 4.7 | Never render placeholder or sample data as if it were real. | This has already caused one incident on this project. |

---

## 5. Backend contract

| # | Rule |
| :-- | :--- |
| 5.1 | The API shape is fixed and documented. The frontend never guesses a field name. |
| 5.2 | Errors return a consistent shape, for example `{"detail": "..."}`, on every endpoint. |
| 5.3 | The frontend never computes a number the backend already owns. One source of truth. |
| 5.4 | Secrets, tokens and internal ids never appear in the DOM or in a URL. |
| 5.5 | Slow endpoints are paginated or streamed, not loaded whole. |
| 5.6 | A health endpoint exists and reflects real dependency status. |

---

## 6. Assets

| # | Rule |
| :-- | :--- |
| 6.1 | The logo is SVG, so it stays sharp at every size and in dark mode. |
| 6.2 | The logo has a fixed width and height, so it does not shift during load. |
| 6.3 | Favicon set is complete: `.ico`, 16px, 32px, apple-touch-icon, webmanifest. |
| 6.4 | Images have explicit `width` and `height` attributes. |
| 6.5 | Images below the fold use `loading="lazy"`. |
| 6.6 | No image is scaled up beyond its natural size. |

---

## 7. Structure and quality

| # | Rule |
| :-- | :--- |
| 7.1 | All DOM elements a script touches exist above that script in document order. |
| 7.2 | No `if (!el) return` guards added to hide an ordering mistake. Fix the order. |
| 7.3 | Any user or API value written into HTML is escaped. |
| 7.4 | Colours, spacing and radii come from CSS variables, never hardcoded per component. |
| 7.5 | Light and dark mode are both defined, and `body` has an explicit background. |
| 7.6 | One shared stylesheet for shared components, instead of each page copying CSS. |

---

## 8. Responsive

| # | Rule |
| :-- | :--- |
| 8.1 | Works at 375px with no horizontal page scroll. |
| 8.2 | Tables either scroll inside their own container or stack into cards below the breakpoint. |
| 8.3 | Tap targets are at least 44px. |
| 8.4 | A 16px side gutter is kept on mobile. |

---

## 9. Accessibility

| # | Rule |
| :-- | :--- |
| 9.1 | Every control is reachable and operable by keyboard. |
| 9.2 | Focus is always visible. |
| 9.3 | Images have `alt`. Icon-only buttons have `aria-label`. |
| 9.4 | Text contrast is at least 4.5:1. |
| 9.5 | Loading and error regions are announced with `aria-live`. |
| 9.6 | Modals trap focus and close on Escape. |

---

## 10. Testing

Every part of the frontend needs a test. Four layers:

| Layer | What it covers | Tool |
| :--- | :--- | :--- |
| Unit | Pure functions: formatting, parsing, state machines. | Python or JS test runner |
| DOM | A function renders the right markup for each of the five states. | jsdom or Playwright |
| Contract | The markup the API expects is present, and field names match. | pytest against served HTML |
| End to end | Real browser, real flow: sign in, search, pause, cancel. | Playwright |

Rules:

- Every data region is tested in all five states, including empty and error.
- Every bug that reaches the client gets a test that would have caught it.
- Tests never hit live PayPal, live Resend, or production Supabase.
- A visual check at 375px and at desktop is part of done.

---

## 11. Definition of done

A frontend change is done when all of these are true:

- [ ] Shell paints before data
- [ ] All five states exist for every data region
- [ ] Skeleton matches final layout, no shift
- [ ] A refresh shows the new version, no hard refresh needed
- [ ] No console errors
- [ ] No horizontal scroll at 375px
- [ ] Keyboard reachable, focus visible
- [ ] Tests added for the changed region
- [ ] Verified in a real browser, not assumed
