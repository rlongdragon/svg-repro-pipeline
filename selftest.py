#!/usr/bin/env python3
"""Verify render + imgdiff work WITHOUT any API key.

Renders an SVG to PNG, then diffs the render against itself (SSIM should be ~1.0).
Usage:  python selftest.py path/to/some.svg
"""
import sys
import os
from svgbench import render, imgdiff


def main():
    svg_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not svg_path or not os.path.exists(svg_path):
        print("usage: python selftest.py <file.svg>")
        sys.exit(1)
    with open(svg_path, encoding="utf-8") as f:
        svg = f.read()
    os.makedirs("_selftest", exist_ok=True)
    png, size = render.render_svg(svg, "_selftest/render.png")
    print(f"rendered -> {png} size={size}")
    m = imgdiff.compare(png, png, "_selftest/diff.png")
    print(f"self-diff ssim={m['ssim']} (expect 1.0), regions={len(m['regions'])}")
    assert m["ssim"] > 0.99, "render/diff pipeline broken"
    print("SELFTEST OK: render + imgdiff working, CJK via Chromium.")


if __name__ == "__main__":
    main()
