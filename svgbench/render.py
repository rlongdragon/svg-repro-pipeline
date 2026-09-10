"""Render an SVG string to PNG with headless Chromium (faithful CJK)."""
from playwright.sync_api import sync_playwright
from .utils import svg_dimensions


def render_svg(svg_text, out_png, scale=1.0, timeout_ms=15000):
    w, h = svg_dimensions(svg_text)
    W, H = int(w * scale), int(h * scale)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>*{margin:0;padding:0}html,body{background:#fff}"
        "svg{display:block}</style></head><body>" + svg_text + "</body></html>"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--force-color-profile=srgb"])
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(350)  # let webfonts settle
        page.screenshot(path=out_png, clip={"x": 0, "y": 0, "width": W, "height": H})
        browser.close()
    return out_png, (W, H)
