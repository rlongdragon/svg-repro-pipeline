import re

_DIM = re.compile(r'<svg[^>]*?\bwidth="([\d.]+)"[^>]*?\bheight="([\d.]+)"', re.I)
_VB = re.compile(r'viewBox="[\d.\s-]*?([\d.]+)\s+([\d.]+)"', re.I)


def svg_dimensions(svg_text, default=(1200, 800)):
    """Return (W, H) ints from width/height attrs, else viewBox, else default."""
    m = _DIM.search(svg_text)
    if m:
        return int(round(float(m.group(1)))), int(round(float(m.group(2))))
    m = _VB.search(svg_text)
    if m:
        return int(round(float(m.group(1)))), int(round(float(m.group(2))))
    return default


def clamp(v, lo, hi):
    return max(lo, min(hi, v))
