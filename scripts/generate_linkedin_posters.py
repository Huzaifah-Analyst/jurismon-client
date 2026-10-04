"""Generates three high-impact LinkedIn poster graphics for JurisMon project showcases."""

import os
from PIL import Image, ImageDraw, ImageFont

# Ensure target directory exists
os.makedirs("docs/context/posters", exist_ok=True)

# Color Palette (Dark Theme / Slate Modern)
BG_COLOR = (11, 17, 32)         # Slate 950
CARD_BG = (17, 24, 39)          # Slate 900
CARD_BORDER = (31, 41, 55)      # Slate 800
TEXT_WHITE = (248, 250, 252)    # Slate 50
TEXT_MUTED = (148, 163, 184)    # Slate 400
TEXT_DIM = (100, 116, 139)      # Slate 500
ACCENT_GREEN = (16, 185, 129)   # Emerald 500
ACCENT_BLUE = (59, 130, 246)    # Blue 500
ACCENT_AMBER = (245, 158, 11)   # Amber 500
ACCENT_PURPLE = (139, 92, 246)  # Purple 500

# Typography
f_badge = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 16)
f_h1 = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 36)
f_sub = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 20)
f_card_title = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 19)
f_card_desc = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)
f_num = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 46)
f_num_sub = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)
f_footer = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18)
f_mono = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 17)


# ==============================================================================
# POSTER 1: Client Review & Delivery Highlights
# ==============================================================================
def generate_poster_1():
    img = Image.new("RGB", (1200, 1200), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Frame border
    draw.rectangle([(0, 0), (1199, 1199)], outline=(30, 41, 59), width=2)

    # Pill Badge
    draw.rounded_rectangle([(70, 50), (430, 92)], radius=21, fill=(6, 78, 59), outline=ACCENT_GREEN, width=1)
    draw.text((95, 62), "★ VERIFIED CLIENT REVIEW • FIVERR", fill=(167, 243, 208), font=f_badge)

    # Headline & Subtitle
    draw.text((70, 115), '"I wish there\'s another rating above 5 stars."', fill=TEXT_WHITE, font=f_h1)
    draw.text((70, 170), "Delivering an automated regulatory monitoring platform for a US legal client.", fill=TEXT_MUTED, font=f_sub)

    # Clean Review Card
    rev_img = Image.open("docs/context/review_card_clean.png")
    target_w = 1060
    scale = target_w / rev_img.width
    target_h = int(rev_img.height * scale)
    rev_resized = rev_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    draw.rounded_rectangle([(68, 228), (68 + target_w + 4, 228 + target_h + 4)], radius=14, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
    img.paste(rev_resized, (70, 230))

    # Divider
    sep_y = 230 + target_h + 35
    draw.line([(70, sep_y), (1130, sep_y)], fill=(30, 41, 59), width=1)

    # Metrics Grid
    grid_top = sep_y + 25
    box_w, box_h = 515, 175

    boxes = [
        ("41", "Operational Sources", "Monitored daily across North America & UK planning portals", (70, grid_top), ACCENT_BLUE),
        ("915", "Legal Documents", "Extracted, cleaned, OCR-processed & full-text searchable", (615, grid_top), ACCENT_GREEN),
        ("226", "Regulatory Diffs", "Paragraph-level statutory amendments detected & redlined", (70, grid_top + 200), ACCENT_AMBER),
        ("255", "Automated Tests", "Comprehensive test suite with zero live production regressions", (615, grid_top + 200), ACCENT_PURPLE),
    ]

    for val, title, desc, (bx, by), col in boxes:
        draw.rounded_rectangle([(bx, by), (bx + box_w, by + box_h)], radius=14, fill=CARD_BG, outline=CARD_BORDER, width=2)
        # Accent indicator
        draw.rounded_rectangle([(bx, by), (bx + 8, by + box_h)], radius=4, fill=col)
        draw.text((bx + 30, by + 22), val, fill=col, font=f_num)
        draw.text((bx + 140, by + 32), title, fill=TEXT_WHITE, font=f_card_title)
        draw.text((bx + 30, by + 98), desc, fill=TEXT_MUTED, font=f_num_sub)

    # Footer
    draw.line([(70, 1130), (1130, 1130)], fill=(30, 41, 59), width=1)
    draw.text((70, 1150), "Built & Deployed by Huzaifah Naseer", fill=TEXT_WHITE, font=f_footer)
    draw.text((810, 1150), "Python • FastAPI • PostgreSQL • Playwright", fill=TEXT_MUTED, font=f_footer)

    out_path = "docs/context/posters/poster_1_client_review.png"
    img.save(out_path)
    print(f"Poster 1 generated: {out_path}")


# ==============================================================================
# POSTER 2: Live UI & System Capabilities
# ==============================================================================
def generate_poster_2():
    img = Image.new("RGB", (1200, 1200), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Border
    draw.rectangle([(0, 0), (1199, 1199)], outline=(30, 41, 59), width=2)

    # Badge
    draw.rounded_rectangle([(70, 45), (460, 87)], radius=21, fill=(30, 58, 138), outline=ACCENT_BLUE, width=1)
    draw.text((95, 57), "SYSTEM ARCHITECTURE • PRODUCTION READY", fill=(191, 219, 254), font=f_badge)

    # Headline & Subtitle
    draw.text((70, 105), "Automated Regulatory Drift Detection Platform", fill=TEXT_WHITE, font=f_h1)
    draw.text((70, 160), "From daily municipal portal crawling to paragraph-level statutory redlines.", fill=TEXT_MUTED, font=f_sub)

    # Window 1: Diff Viewer Modal (Top screenshot)
    # Crop central area of diff viewer showing the redline diff
    diff_shot = Image.open("delivery_screenshots/04_diff_viewer_modal.png")
    # 1440x900 -> crop modal area (x: 220 to 1220, y: 100 to 800)
    diff_crop = diff_shot.crop((200, 80, 1240, 820))
    diff_crop = diff_crop.resize((1060, 420), Image.Resampling.LANCZOS)

    # Window frame
    draw.rounded_rectangle([(68, 218), (1132, 652)], radius=12, fill=(15, 23, 42), outline=CARD_BORDER, width=2)
    # Window header bar
    draw.rounded_rectangle([(68, 218), (1132, 255)], radius=12, fill=(30, 41, 59))
    draw.ellipse([(85, 232), (97, 244)], fill=(239, 68, 68))
    draw.ellipse([(105, 232), (117, 244)], fill=(245, 158, 11))
    draw.ellipse([(125, 232), (137, 244)], fill=(34, 197, 94))
    draw.text((160, 228), "Regulatory Diff Engine — Statutory Redline Viewer", fill=TEXT_MUTED, font=f_card_desc)
    img.paste(diff_crop.crop((0, 37, 1060, 420)), (70, 255))

    # Window 2: Admin Monitoring Console (Bottom screenshot)
    admin_shot = Image.open("delivery_screenshots/13_admin_sources.png")
    # crop sources table and stats
    admin_crop = admin_shot.crop((180, 100, 1420, 800))
    admin_crop = admin_crop.resize((1060, 260), Image.Resampling.LANCZOS)

    draw.rounded_rectangle([(68, 678), (1132, 952)], radius=12, fill=(15, 23, 42), outline=CARD_BORDER, width=2)
    draw.rounded_rectangle([(68, 678), (1132, 715)], radius=12, fill=(30, 41, 59))
    draw.ellipse([(85, 692), (97, 704)], fill=(239, 68, 68))
    draw.ellipse([(105, 692), (117, 704)], fill=(245, 158, 11))
    draw.ellipse([(125, 692), (137, 704)], fill=(34, 197, 94))
    draw.text((160, 688), "Administrative Monitoring Console — 41/65 Sources Active Daily", fill=TEXT_MUTED, font=f_card_desc)
    img.paste(admin_crop.crop((0, 37, 1060, 260)), (70, 715))

    # Feature Highlights Pills
    pills = [
        ("7 Crawler Adapters", (70, 975), ACCENT_BLUE),
        ("Tesseract OCR Pipeline", (310, 975), ACCENT_GREEN),
        ("PostgreSQL Full-Text Search", (570, 975), ACCENT_AMBER),
        ("PayPal Webhook Billing", (880, 975), ACCENT_PURPLE),
    ]
    for ptext, (px, py), pcol in pills:
        draw.rounded_rectangle([(px, py), (px + 235, py + 45)], radius=10, fill=CARD_BG, outline=pcol, width=1)
        draw.text((px + 15, py + 12), ptext, fill=TEXT_WHITE, font=f_card_desc)

    pills_2 = [
        ("Section § Splitter Engine", (70, 1035), TEXT_MUTED),
        ("Automated Systemd Crawl Lock Recovery", (350, 1035), TEXT_MUTED),
        ("14-Day Gated Free Trial Access", (770, 1035), TEXT_MUTED),
    ]
    for ptext, (px, py), pcol in pills_2:
        draw.rounded_rectangle([(px, py), (px + 270 if "Systemd" not in ptext else px + 395, py + 45)], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)
        draw.text((px + 15, py + 12), ptext, fill=TEXT_MUTED, font=f_card_desc)

    # Footer
    draw.line([(70, 1120), (1130, 1120)], fill=(30, 41, 59), width=1)
    draw.text((70, 1145), "Designed & Engineered by Huzaifah Naseer", fill=TEXT_WHITE, font=f_footer)
    draw.text((810, 1145), "FastAPI • Supabase • Playwright • Systemd", fill=TEXT_MUTED, font=f_footer)

    out_path = "docs/context/posters/poster_2_system_architecture.png"
    img.save(out_path)
    print(f"Poster 2 generated: {out_path}")


# ==============================================================================
# POSTER 3: Engineering Discipline & Bug Post-Mortem
# ==============================================================================
def generate_poster_3():
    img = Image.new("RGB", (1200, 1200), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Border
    draw.rectangle([(0, 0), (1199, 1199)], outline=(30, 41, 59), width=2)

    # Badge
    draw.rounded_rectangle([(70, 45), (470, 87)], radius=21, fill=(88, 28, 135), outline=ACCENT_PURPLE, width=1)
    draw.text((95, 57), "POST-MORTEM & TESTING • RELIABILITY", fill=(233, 213, 255), font=f_badge)

    # Headline & Subtitle
    draw.text((70, 105), "Why 255 Passing Tests Weren't Enough", fill=TEXT_WHITE, font=f_h1)
    draw.text((70, 160), "Real production traps we caught, solved, and permanently guarded against.", fill=TEXT_MUTED, font=f_sub)

    # Terminal Screenshot Evidence (top left & top right)
    term_shot = Image.open("delivery_screenshots/19_tests_passing.png")
    term_crop = term_shot.crop((50, 50, 1390, 850)).resize((1060, 240), Image.Resampling.LANCZOS)

    draw.rounded_rectangle([(68, 208), (1132, 462)], radius=12, fill=(15, 23, 42), outline=CARD_BORDER, width=2)
    draw.rounded_rectangle([(68, 208), (1132, 245)], radius=12, fill=(30, 41, 59))
    draw.ellipse([(85, 222), (97, 234)], fill=(239, 68, 68))
    draw.ellipse([(105, 222), (117, 234)], fill=(245, 158, 11))
    draw.ellipse([(125, 222), (137, 234)], fill=(34, 197, 94))
    draw.text((160, 218), "Terminal: pytest test suite passing with schema contract validation", fill=TEXT_MUTED, font=f_card_desc)
    img.paste(term_crop.crop((0, 37, 1060, 240)), (70, 245))

    # Three Big Engineering Lessons (Cards)
    lessons = [
        (
            "1. SQLite hides what PostgreSQL enforces",
            "Local unit tests passed because SQLite creates columns on the fly. Production crashed three times with missing column errors. Solution: We built an automated schema-parity contract test that halts builds if any SQLite column lacks a matching Postgres migration.",
            ACCENT_BLUE,
            490
        ),
        (
            "2. Pushing is not deploying",
            "Five successive bug fixes sat on GitHub while production ran week-old code, because 'git push' doesn't update a VPS. Solution: Rigorous staged deploy runbook with dependency sync, migration application, and automated health checks.",
            ACCENT_AMBER,
            680
        ),
        (
            "3. Null guards turn fatal bugs into silence",
            "An #auth-gate element was placed after the closing script tag. A defensive 'if (authGate)' guard swallowed the error silently, leaving the login screen permanently hidden after logout. Solution: Test all 5 lifecycle states: signed-in, signed-out, expired, loading, and error.",
            ACCENT_GREEN,
            870
        ),
    ]

    for title, desc, col, ly in lessons:
        draw.rounded_rectangle([(70, ly), (1130, ly + 160)], radius=14, fill=CARD_BG, outline=CARD_BORDER, width=2)
        draw.rounded_rectangle([(70, ly), (78, ly + 160)], radius=4, fill=col)
        draw.text((105, ly + 20), title, fill=TEXT_WHITE, font=f_card_title)
        
        # Word wrap description
        words = desc.split()
        lines = []
        cur_line = []
        for w in words:
            cur_line.append(w)
            # test line width
            if len(" ".join(cur_line)) > 92:
                cur_line.pop()
                lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))
            
        for line_idx, line_str in enumerate(lines[:3]):
            draw.text((105, ly + 60 + line_idx * 26), line_str, fill=TEXT_MUTED, font=f_card_desc)

    # Footer
    draw.line([(70, 1120), (1130, 1120)], fill=(30, 41, 59), width=1)
    draw.text((70, 1145), "Engineering Memory & Standards by Huzaifah Naseer", fill=TEXT_WHITE, font=f_footer)
    draw.text((780, 1145), "Reliability Engineering • Zero Silent Failures", fill=TEXT_MUTED, font=f_footer)

    out_path = "docs/context/posters/poster_3_engineering_process.png"
    img.save(out_path)
    print(f"Poster 3 generated: {out_path}")


if __name__ == "__main__":
    generate_poster_1()
    generate_poster_2()
    generate_poster_3()
    print("All 3 LinkedIn posters generated successfully!")
