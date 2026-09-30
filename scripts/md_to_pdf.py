"""Renders a Markdown document to a print-quality PDF via headless Chromium.

Documentation tooling, not part of the runtime. Playwright is already a project
dependency; the Markdown parser is not, so install it before running:

    pip install markdown

Usage:
    python scripts/md_to_pdf.py docs/JurisMon_Client_Action_Guide.md                                 docs/JurisMon_Client_Action_Guide.pdf
"""

import sys
import os
import pathlib
import markdown
from playwright.sync_api import sync_playwright

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }

:root {
  --ink:      #1a1d23;
  --muted:    #5b6472;
  --rule:     #dde1e7;
  --accent:   #1f4e79;
  --accent-bg:#eef3f9;
  --code-bg:  #f5f6f8;
}

* { box-sizing: border-box; }

body {
  font-family: "Segoe UI", -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.6;
  color: var(--ink);
  margin: 0;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

/* ---- Headings ---- */
h1 {
  font-size: 19pt;
  font-weight: 600;
  color: var(--accent);
  margin: 0 0 4pt;
  padding-bottom: 6pt;
  border-bottom: 2.5px solid var(--accent);
  letter-spacing: -0.2pt;
  break-after: avoid;
}
h1:not(:first-of-type) { margin-top: 26pt; }

h2 {
  font-size: 13.5pt;
  font-weight: 600;
  color: var(--accent);
  margin: 20pt 0 7pt;
  padding-bottom: 3pt;
  border-bottom: 1px solid var(--rule);
  break-after: avoid;
}

h3 {
  font-size: 11.5pt;
  font-weight: 600;
  color: var(--ink);
  margin: 15pt 0 5pt;
  break-after: avoid;
}

p { margin: 0 0 8pt; orphans: 3; widows: 3; }

strong { font-weight: 600; color: var(--ink); }

/* ---- Lists ---- */
ul, ol { margin: 0 0 9pt; padding-left: 19pt; }
li { margin-bottom: 4pt; }
li > ul, li > ol { margin-top: 4pt; margin-bottom: 2pt; }

/* ---- Tables ---- */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 10pt 0 14pt;
  font-size: 9.5pt;
  break-inside: avoid;
}
thead { background: var(--accent); }
th {
  color: #fff;
  font-weight: 600;
  text-align: left;
  padding: 6pt 8pt;
  border: 1px solid var(--accent);
}
td {
  padding: 5.5pt 8pt;
  border: 1px solid var(--rule);
  vertical-align: top;
}
tbody tr:nth-child(even) { background: #f8f9fb; }

/* ---- Code ---- */
code {
  font-family: Consolas, "SF Mono", Menlo, monospace;
  font-size: 9pt;
  background: var(--code-bg);
  border: 1px solid var(--rule);
  border-radius: 3px;
  padding: 1pt 4pt;
  color: #9a2b2b;
  word-break: break-all;
}
pre {
  background: var(--code-bg);
  border: 1px solid var(--rule);
  border-left: 3px solid var(--accent);
  border-radius: 3px;
  padding: 9pt 11pt;
  margin: 8pt 0 11pt;
  overflow-wrap: anywhere;
  break-inside: avoid;
}
pre code {
  background: none;
  border: none;
  padding: 0;
  color: var(--ink);
  font-size: 9pt;
  line-height: 1.5;
}

/* ---- Callouts ---- */
blockquote {
  margin: 10pt 0;
  padding: 9pt 13pt;
  background: var(--accent-bg);
  border-left: 3.5px solid var(--accent);
  border-radius: 0 3px 3px 0;
  break-inside: avoid;
}
blockquote p { margin: 0; }
blockquote p + p { margin-top: 6pt; }

/* ---- Rules ---- */
hr {
  border: none;
  border-top: 1px solid var(--rule);
  margin: 17pt 0;
}

/* ---- Cover block ---- */
.meta {
  color: var(--muted);
  font-size: 9.5pt;
  margin: 0 0 18pt;
  padding-bottom: 12pt;
  border-bottom: 1px solid var(--rule);
}
.meta div { margin-bottom: 2pt; }

a { color: var(--accent); text-decoration: none; }
"""

FOOTER_TEMPLATE = """
<div style="width:100%;font-size:7.5pt;color:#8a929e;padding:0 16mm;
            font-family:'Segoe UI',Arial,sans-serif;display:flex;
            justify-content:space-between;">
  <span>__TITLE__</span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>
"""


def document_title(markdown_text: str, fallback: str) -> str:
    """Takes the title from the document's first h1, so the footer matches."""
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def convert(md_path: str, pdf_path: str) -> None:
    text = pathlib.Path(md_path).read_text(encoding="utf-8")
    title = document_title(text, pathlib.Path(md_path).stem.replace("_", " "))

    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
    )

    import html as _html
    html_escape = _html.escape

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{html_escape(title)}</title>
<style>{CSS}</style></head>
<body>{body}</body></html>"""

    tmp_html = os.path.join(os.path.dirname(pdf_path) or ".", "_guide_tmp.html")
    tmp_html = os.path.abspath(tmp_html)
    pathlib.Path(tmp_html).write_text(html, encoding="utf-8")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(pathlib.Path(tmp_html).as_uri(), wait_until="networkidle")
            page.pdf(
                path=pdf_path,
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=FOOTER_TEMPLATE.replace("__TITLE__", html_escape(title)),
                margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"},
            )
            browser.close()
    finally:
        if os.path.exists(tmp_html):
            os.remove(tmp_html)


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
    print(f"Written: {sys.argv[2]}")
