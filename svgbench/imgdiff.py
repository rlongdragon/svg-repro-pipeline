"""Compare candidate render vs target: SSIM + diff heatmap + mismatch regions."""
import numpy as np
from PIL import Image, ImageDraw
from skimage.metrics import structural_similarity as ssim
from skimage.measure import label, regionprops


def compare(target_png, cand_png, out_diff, pixel_thresh=30, min_area=120, max_regions=12):
    tgt = Image.open(target_png).convert("RGB")
    cand = Image.open(cand_png).convert("RGB").resize(tgt.size)

    ta = np.asarray(tgt).astype(np.float32)
    ca = np.asarray(cand).astype(np.float32)
    gt = np.asarray(tgt.convert("L"))
    gc = np.asarray(cand.convert("L"))

    score = float(ssim(gt, gc))
    diff = np.abs(ta - ca).mean(axis=2)
    mse = float((diff ** 2).mean())
    mask = diff > pixel_thresh

    regions = []
    lbl = label(mask)
    for r in sorted(regionprops(lbl), key=lambda x: -x.area):
        if r.area < min_area:
            continue
        minr, minc, maxr, maxc = r.bbox
        regions.append({"x": int(minc), "y": int(minr),
                        "w": int(maxc - minc), "h": int(maxr - minr),
                        "area": int(r.area)})
        if len(regions) >= max_regions:
            break

    # heatmap overlay on target: red where mismatch + region boxes
    red = np.zeros((*mask.shape, 4), dtype=np.uint8)
    red[mask] = [255, 0, 0, 120]
    base = tgt.convert("RGBA")
    base.alpha_composite(Image.fromarray(red, "RGBA"))
    dr = ImageDraw.Draw(base)
    for reg in regions:
        dr.rectangle([reg["x"], reg["y"], reg["x"] + reg["w"], reg["y"] + reg["h"]],
                     outline=(255, 0, 0, 255), width=3)
    base.convert("RGB").save(out_diff)

    return {"ssim": round(score, 4), "mse": round(mse, 2), "regions": regions}
