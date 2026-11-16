"""Pawsitive Vibes — turns an issue file into email HTML.

An issue file lives in issues/ and looks like:

    ---
    subject: Your little reminder for Friday
    preview: Rest is productive. Here's why.
    status: send            # draft = preview only, send = goes out
    send_at: 2026-11-14 07:00   # Eastern time; "now" sends in ~5 minutes
    ---
    Hi friend,

    Your note goes here, in plain writing. **Bold**, *italics* and
    [links](https://kjontheair.com) all work.

    ![Melody napping](images/melody-nap.jpg)

    [[button: Read more | https://kjontheair.com]]
"""
import html
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown
import yaml

ROOT = Path(__file__).resolve().parent.parent
EASTERN = ZoneInfo("America/New_York")

# Brand colors (match kjontheair.com)
PLUM, PINK, TEAL, LAVENDER, CHARCOAL, WARM = (
    "#2B1B3F", "#E85FB7", "#2EC4C7", "#F3EEFF", "#2D2D35", "#FFFDFC")


def image_base(repo: str | None) -> str:
    """Public URL prefix for images stored in this repo."""
    if not repo:
        return "../"  # local preview lives in previews/, images in images/
    return f"https://raw.githubusercontent.com/{repo}/main/"


def parse_issue(path: Path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        raise ValueError(f"{path.name}: missing the --- settings block at the top")
    meta = yaml.safe_load(m.group(1)) or {}
    for key in ("subject", "preview"):
        if not meta.get(key):
            raise ValueError(f"{path.name}: needs a '{key}:' line")
    return meta, m.group(2).strip()


def send_time_utc(meta) -> str:
    raw = str(meta.get("send_at", "now")).strip()
    if raw.lower() == "now":
        when = datetime.now(timezone.utc) + timedelta(minutes=5)
    else:
        when = datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN)
        when = when.astimezone(timezone.utc)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


BUTTON = re.compile(r"\[\[button:\s*(.+?)\s*\|\s*(\S+?)\s*\]\]")


def body_html(md_text: str, img_prefix: str) -> str:
    def button(m):
        label, url = html.escape(m.group(1)), html.escape(m.group(2), quote=True)
        return (
            f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="margin:24px auto;"><tr><td style="background:{PINK};'
            f'border-radius:999px;"><a style="display:inline-block;'
            f'padding:14px 32px;font-family:Arial,sans-serif;font-size:16px;'
            f'font-weight:bold;color:#ffffff;text-decoration:none;" href="{url}">{label}</a>'
            f'</td></tr></table>')

    md_text = BUTTON.sub(button, md_text)
    out = markdown.markdown(md_text, extensions=["extra", "sane_lists"])

    # Email clients ignore <style> blocks, so every tag gets inline styles.
    p = (f'style="margin:0 0 18px;font-family:Georgia,serif;font-size:18px;'
         f'line-height:1.6;color:{CHARCOAL};"')
    out = re.sub(r"<p>", f"<p {p}>", out)
    out = re.sub(r"<li>", f'<li style="margin:0 0 8px;font-family:Georgia,serif;'
                          f'font-size:18px;line-height:1.6;color:{CHARCOAL};">', out)
    out = re.sub(r"<h([23])>", lambda m: (
        f'<h{m.group(1)} style="margin:28px 0 12px;font-family:Georgia,serif;'
        f'font-size:{24 if m.group(1) == "2" else 20}px;color:{PLUM};">'), out)
    out = re.sub(r'<a href="(?!mailto)', f'<a style="color:{PINK};font-weight:bold;" href="', out)
    out = re.sub(r"<blockquote>", (
        f'<blockquote style="margin:24px 0;padding:16px 20px;background:{LAVENDER};'
        f'border-left:4px solid {TEAL};border-radius:8px;">'), out)

    def img(m):
        attrs = m.group(1)
        src = re.search(r'src="([^"]+)"', attrs).group(1)
        alt = (re.search(r'alt="([^"]*)"', attrs) or [None, ""])[1]
        if not src.startswith("http"):
            src = img_prefix + src
        return (f'<img src="{src}" alt="{alt}" width="560" style="display:block;'
                f'width:100%;max-width:560px;height:auto;border-radius:12px;'
                f'margin:8px 0 22px;">')

    return re.sub(r"<img([^>]*)/?>", img, out)


def custom_design_html(meta) -> str:
    """Use a hand-designed HTML email from designs/ instead of the Pawsitive
    Vibes look (set `design: designs/<file>.html` in the issue's settings)."""
    page = (ROOT / meta["design"]).read_text(encoding="utf-8")
    style = re.search(r"<style[^>]*>.*?</style>", page, re.S)
    body = re.search(r"<body[^>]*>(.*)</body>", page, re.S)
    if not body:
        raise ValueError(f"{meta['design']}: no <body> found")
    return (style.group(0) if style else "") + body.group(1)


def email_html(meta, md_text: str, repo: str | None = None) -> str:
    if meta.get("design"):
        return custom_design_html(meta)
    prefix = image_base(repo)
    signoff_img = prefix + "images/kj-signoff.jpg"
    return f"""<div style="background:{WARM};padding:0;margin:0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
<tr><td style="background:{PLUM};padding:28px 24px;text-align:center;border-radius:16px 16px 0 0;">
  <div style="font-family:Arial,sans-serif;font-size:13px;letter-spacing:2px;text-transform:uppercase;color:{TEAL};margin-bottom:6px;">The SuPURR Community</div>
  <div style="font-family:Georgia,serif;font-size:30px;font-weight:bold;color:#ffffff;">Pawsitive Vibes</div>
</td></tr>
<tr><td style="background:#ffffff;padding:32px 24px 8px;">
{body_html(md_text, prefix)}
</td></tr>
<tr><td style="background:#ffffff;padding:8px 24px 32px;">
  <table role="presentation" cellpadding="0" cellspacing="0"><tr>
    <td style="vertical-align:middle;padding-right:16px;"><img src="{signoff_img}" alt="KJ" width="72" height="72" style="display:block;width:72px;height:72px;border-radius:50%;object-fit:cover;"></td>
    <td style="vertical-align:middle;font-family:Georgia,serif;font-size:18px;color:{PLUM};"><em>With love and purrs,</em><br><strong>KJ</strong></td>
  </tr></table>
</td></tr>
<tr><td style="background:{LAVENDER};padding:20px 24px;text-align:center;border-radius:0 0 16px 16px;font-family:Arial,sans-serif;font-size:14px;color:{CHARCOAL};">
  <a href="https://kjontheair.com" style="color:{PLUM};font-weight:bold;">kjontheair.com</a> &nbsp;·&nbsp;
  <a href="https://www.etsy.com/shop/SuPURRShop" style="color:{PLUM};font-weight:bold;">SuPURRShop</a>
</td></tr>
</table></div>"""


def preview_page(meta, md_text: str) -> str:
    """Full web page for previewing an issue before it goes out."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Preview: {html.escape(meta['subject'])}</title></head>
<body style="margin:0;background:#eee;padding:16px 0;">
<div style="max-width:600px;margin:0 auto 12px;font-family:Arial,sans-serif;font-size:14px;color:#555;padding:0 12px;">
<strong>Subject:</strong> {html.escape(meta['subject'])}<br>
<strong>Preview line:</strong> {html.escape(meta['preview'])}</div>
{email_html(meta, md_text)}
</body></html>"""


if __name__ == "__main__":
    issue = Path(sys.argv[1])
    meta, body = parse_issue(issue)
    out = ROOT / "previews" / (issue.stem + ".html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(preview_page(meta, body), encoding="utf-8")
    print(out)
