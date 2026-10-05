# JurisMon Design System & UI Specification

> **Audience**: AI coding agents adding or modifying frontend interfaces (`frontend/*.html`).  
> **Source of Truth**: Extracted directly from `frontend/index.html`, `frontend/admin.html`, and `frontend/account.html`.  
> **Rule**: Match the existing visual system strictly. Never invent new color palettes, component classes, or typography paradigms.

---

## 1. Color Tokens

JurisMon uses a restrained, utilitarian legal/finance palette built on cool slate tones:

```css
:root {
  /* Surfaces & Canvas */
  --bg:           #f8fafc;  /* Page canvas background (slate-50) */
  --surface:      #ffffff;  /* Cards, modals, topbar, dropdowns */
  --hover:        #f1f5f9;  /* Table row and button hover state (slate-100) */

  /* Text & Inks */
  --ink:          #0f172a;  /* Primary headings, titles, solid button fills (slate-900) */
  --text:         #334155;  /* Standard body copy (slate-700) */
  --muted:        #64748b;  /* Metadata, captions, timestamps, placeholder text (slate-500) */

  /* Borders & Dividers */
  --line:         #e2e8f0;  /* Card borders, table dividers, hairlines (slate-200) */
  --line-strong:  #cbd5e1;  /* Form input borders, outline button borders (slate-300) */

  /* Brand Accents */
  --primary:      #154da8;  /* Brand blue accent */
  --primary-hover:#0f3c85;  /* Dark blue hover */

  /* Regulatory Diff Engine Colors */
  --add-bg:       #ecfdf5;  /* Added text background (emerald-50) */
  --add-ink:      #065f46;  /* Added text ink (emerald-800) */
  --add-bar:      #6ee7b7;  /* Added diff bar accent (emerald-300) */
  --del-bg:       #fff1f2;  /* Deleted text background (rose-50) */
  --del-ink:      #9f1239;  /* Deleted text ink (rose-800) */
  --del-bar:      #fda4af;  /* Deleted diff bar accent (rose-300) */
  --mix-bar:      #94a3b8;  /* Neutral change bar */

  /* Functional Alert Colors */
  --success:      #16a34a;  /* Healthy/Active indicators */
  --warning:      #d97706;  /* Paused/Degraded indicators (amber-600) */
  --danger:       #dc2626;  /* Critical errors, delete actions (red-600) */
  --danger-ink:   #b91c1c;  /* Error text headings (red-700) */
}
```

---

## 2. Typography

### Font Stack
```css
font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
```
*Monospace for IDs, hashes, and code blocks*:
```css
font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
```

### Type Scale & Weights
| Size | Weight | Usage & Components |
| :--- | :--- | :--- |
| **11px** | 600 (Semibold, uppercase) | Property labels (`.prop-label`), metric captions (`.stat-lbl`) |
| **12px** | 500 / 600 (Medium) | Status badges (`.badge`), search metadata chips |
| **13px** / **13.5px** | 500 (Medium) | Buttons (`.btn`), nav links, footer text, secondary values |
| **14px** | 400 (Regular) | Default body text, form input values, table data cells |
| **15px** / **16px** | 500 / 600 | Card descriptions, section subheadings, list titles |
| **18px** | 600 (Semibold) | Card titles (`.card-title`), modal headers (`.modal-title`) |
| **20px** / **24px** | 600 / 700 | Page headers, main view headlines |
| **28px** / **32px** | 700 (Bold) | Hero search headline, prominent metric numbers (`.stat-val`) |

---

## 3. Spacing & Radius Scales

### Spacing Scale
- `4px`: Micro-gap between icons and text.
- `8px`: Dense item spacing, badge padding, grid item gaps.
- `12px`: Form field vertical spacing, header item padding.
- `16px`: Standard card internal padding on mobile, row gaps.
- `20px`: Desktop form gaps, modal internal padding.
- `24px` / `28px`: Desktop card padding, topbar height offset.
- `32px` / `48px`: Section margins, empty state vertical padding.

### Border Radii
```css
--r-sm: 4px;   /* Inline code, small tags, keyboard shortcuts */
--r-md: 6px;   /* Standard buttons, input fields, dropdown menus */
--r-lg: 10px;  /* Cards, modals, search box container */
--r-full: 999px; /* Pill badges, status chips, user avatars */
```

---

## 4. Component Library & Class Names

### 1. Cards & Property Grids
- **Card Container**: `.card` (background: `var(--surface)`, border: `1px solid var(--line)`, border-radius: `var(--r-lg)`, padding: `24px`).
- **Card Header**: `<h2 class="card-title">` (font-size: `18px`, color: `var(--ink)`), `<p class="card-desc">` (font-size: `14px`, color: `var(--muted)`).
- **Property Grid**: `.prop-grid` (CSS grid with 2 columns on desktop, 1 on mobile, gap: `16px`).
  - Item: `.prop-item`
  - Label: `.prop-label` (font-size: `11px`, font-weight: `600`, text-transform: `uppercase`, color: `var(--muted)`)
  - Value: `.prop-val` (font-size: `14px`, font-weight: `500`, color: `var(--ink)`)

### 2. Buttons
Base class: `.btn` (height: `36px`, border-radius: `var(--r-md)`, font-size: `13.5px`, font-weight: `500`, padding: `0 14px`, display: `inline-flex`, align-items: `center`, justify-content: `center`).
- **`.btn-primary`**: Solid dark ink fill (`background: var(--ink); color: #fff; border: 1px solid var(--ink)`). Hover: `#1e293b`.
- **`.btn-outline`**: Bordered white button (`background: #fff; color: var(--ink); border: 1px solid var(--line-strong)`). Hover: `var(--hover)`.
- **`.btn-amber`**: Warning/pause button (`background: #fef3c7; color: #92400e; border: 1px solid #fde68a`).
- **`.btn-danger`**: Outline danger button (`background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5`).
- **`.btn-danger-solid`**: Destructive confirmation button (`background: #dc2626; color: #fff; border: 1px solid #dc2626`).

### 3. Status Badges (`.badge`)
Base class: `.badge` (display: `inline-flex`, padding: `2px 8px`, border-radius: `999px`, font-size: `12px`, font-weight: `500`).
- **Active**: `.badge-active` (bg: `#dcfce7`, color: `#15803d`).
- **Paused**: `.badge-paused` (bg: `#fef3c7`, color: `#b45309`).
- **Cancelled**: `.badge-cancelled` (bg: `#fee2e2`, color: `#b91c1c`).
- **Expired**: `.badge-expired` (bg: `#f1f5f9`, color: `#475569`).
- **Trial**: `.badge-trial` (bg: `#dbeafe`, color: `#1d4ed8`).
- **Operational / Healthy**: `.badge-healthy` or `.badge.ok` (bg: `#dcfce7`, color: `#16a34a`).
- **Degraded**: `.badge-degraded` (bg: `#fef3c7`, color: `#d97706`).
- **Failing**: `.badge-failing` (bg: `#fee2e2`, color: `#dc2626`).

### 4. Notices & Banners
Container `.notice` with colored left-accent or tinted background:
- **`.notice-blue`**: Blue background (`#eff6ff`), border (`#bfdbfe`), text (`#1e40af`) for active trial banners.
- **`.notice-amber`**: Amber background (`#fffbeb`), border (`#fde68a`), text (`#92400e`) for paused subscription warnings.
- **`.notice-rose`**: Rose background (`#fff1f2`), border (`#fecdd3`), text (`#9f1239`) for cancellation/expiration alerts.

### 5. Modals
- **Backdrop**: `.modal-backdrop` (`position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 1000;`).
- **Card**: `.modal-card` (`background: #fff; border-radius: 12px; width: 100%; max-width: 460px; padding: 24px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);`).
- **Header**: `.modal-title` (`font-size: 18px; font-weight: 600; color: var(--ink);`).
- **Actions Bar**: `.modal-actions` (`display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px;`).

### 6. Loading & Error States
- **Loading Spinner**: `.spinner` (width: `28px`, height: `28px`, border: `2px solid var(--line)`, border-top-color: `var(--ink)`, border-radius: `50%`, animation: `spin 0.8s linear infinite`).
- **Loading State Container**: `#state-loading` (centered card with spinner and muted status text).
- **Error State Container**: `#state-error` (card with `#b91c1c` headline and retry action button).

### 7. Toast Notifications
- **`.toast`**: Fixed position (`position: fixed; bottom: 24px; right: 24px; background: var(--ink); color: #fff; padding: 10px 16px; border-radius: var(--r-md); font-size: 13.5px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2); z-index: 2000;`).

---

## 5. Logo Lockup & Brand Asset Rules

- **Brand Name**: `JurisMon` (Inter font, semibold/bold, color: `var(--ink)`).
- **Logo Mark**: The geometric blue crest located at `/static/assets/logo.png` or inline SVG crest.
- **Lockup Standard**:
  ```html
  <a href="/" class="brand">
    <img src="/static/assets/logo.png" alt="JurisMon Logo" class="brand-logo" height="30">
    <span class="brand-name">JurisMon</span>
  </a>
  ```
- **Favicon Path**: `/static/favicon.ico`.

---

## 6. Breakpoints & Viewport Resilience

```css
/* Breakpoints */
Desktop:      1024px and above (max-width: 1200px container; account/auth views max-width: 800px)
Tablet:       768px - 1023px
Mobile:       480px - 767px
Small Mobile: 375px (iPhone SE baseline)
```

### ⚠️ The 375px Viewport Regression Hazard
- In commit `79237ab`, top navigation button layouts broke on 375px viewports: long emails and buttons caused horizontal scrolling or button overlapping.
- **Rules for mobile resilience**:
  1. Header containers (`.topbar-inner`, `.header-inner`) **MUST** declare `flex-wrap: wrap; gap: 8px;`.
  2. Buttons in `.actions-bar` on small screens should use `flex-wrap: wrap` or stack full-width (`width: 100%`).
  3. Long strings (emails, URLs, subscription IDs) must declare `overflow: hidden; text-overflow: ellipsis; white-space: nowrap;` or break words cleanly.
  4. Never use hardcoded pixel widths (`width: 400px`); use `max-width: 100%` and relative units.
