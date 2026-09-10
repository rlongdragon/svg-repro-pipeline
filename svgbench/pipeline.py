"""Iterative image-to-SVG loops: V1 (diff self-repair) and V2 (gen/critic).

Generator keeps SESSION memory: a persistent messages list that accumulates its
own prior SVG source + each round's feedback, so it edits its last attempt
instead of regenerating from scratch. Old images are pruned to text stubs to
bound tokens; only the newest turn carries live images.

Reviewer (V2) is STATELESS: judged fresh each round, no memory, so its verdict
is not biased by the conversation.
"""
import os
import json
import time
from . import llm, render, imgdiff

_P = os.path.join(os.path.dirname(__file__), os.pardir, "prompts")


def _load(name):
    with open(os.path.join(_P, name), encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _render_and_score(svg, target_png, out_dir, it, scale):
    pngp = os.path.join(out_dir, f"iter{it}.png")
    diffp = os.path.join(out_dir, f"iter{it}_diff.png")
    render.render_svg(svg, pngp, scale)
    metrics = imgdiff.compare(target_png, pngp, diffp)
    return pngp, diffp, metrics


# ----------------------------------------------------------------- V1: diff
def run_diff(cfg, target_png, model, out_dir, max_iters=5, thr=0.92, session=True):
    os.makedirs(out_dir, exist_ok=True)
    client = llm.client_from_cfg(cfg)
    system = _load(cfg["run"].get("generator_prompt", "generator_system.txt"))
    tmpl = _load("generator_iter_diff.txt")
    scale = cfg["run"].get("render_scale", 1.0)
    mt = cfg["run"].get("max_tokens", 40000)
    temp = cfg["run"].get("temperature", 0.1)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            llm.text_part("Reproduce this TARGET image as an SVG. Output ONLY the SVG."),
            llm.img_part(target_png)]},
    ]
    history, best = [], None

    for it in range(max_iters):
        t0 = time.time()
        raw = llm.chat_messages(client, model, messages, mt, temp)
        messages.append({"role": "assistant", "content": raw})
        svg = llm.extract_svg(raw)
        _write(os.path.join(out_dir, f"iter{it}.svg"), svg or raw)

        rec = {"iter": it}
        try:
            if not svg:
                raise ValueError("no <svg> found in model output")
            pngp, diffp, m = _render_and_score(svg, target_png, out_dir, it, scale)
            rec.update(m)
        except Exception as e:
            rec.update({"ssim": 0.0, "error": str(e), "regions": []})
            pngp = diffp = None
        rec["seconds"] = round(time.time() - t0, 1)
        history.append(rec)
        print(f"  [{model}] diff iter {it}: ssim={rec.get('ssim')} ({rec['seconds']}s)",
              flush=True)
        if best is None or rec["ssim"] > best["ssim"]:
            best = {"iter": it, "ssim": rec["ssim"],
                    "svg": os.path.join(out_dir, f"iter{it}.svg")}
        if rec["ssim"] >= thr or it == max_iters - 1:
            break

        # build next feedback turn (generator keeps memory)
        if session:
            llm.prune_old_images(messages)
        if pngp is None:
            fb = [llm.text_part(
                f"Your previous output failed to render: {rec.get('error')}. "
                "Re-emit a valid, complete SVG for this TARGET (only the ```svg block)."),
                llm.text_part("TARGET:"), llm.img_part(target_png)]
        else:
            regtxt = "\n".join(
                f"- ~({r['x']},{r['y']}) size {r['w']}x{r['h']}" for r in rec["regions"][:10]
            ) or "(no large clusters; refine text/colors/positions)"
            fb = [llm.text_part(tmpl.format(ssim=rec["ssim"], regions=regtxt)),
                  llm.text_part("IMAGE 1 = TARGET:"), llm.img_part(target_png),
                  llm.text_part("IMAGE 2 = YOUR CURRENT RENDER:"), llm.img_part(pngp),
                  llm.text_part("IMAGE 3 = DIFF (red = mismatch):"), llm.img_part(diffp)]
        messages.append({"role": "user", "content": fb})
        if not session:  # stateless: drop history, keep system + fresh turn
            messages = [messages[0], messages[-1]]

    summary = {"model": model, "mode": "diff", "target": target_png,
               "session": session, "best": best, "history": history}
    _write(os.path.join(out_dir, "metrics.json"),
           json.dumps(summary, ensure_ascii=False, indent=2))
    return {"model": model, "mode": "diff", "best_ssim": best["ssim"],
            "iters": len(history), "out_dir": out_dir}


# ------------------------------------------------------------- V2: gen/critic
def run_critic(cfg, target_png, gen_model, review_model, out_dir, max_iters=5, session=True):
    os.makedirs(out_dir, exist_ok=True)
    client = llm.client_from_cfg(cfg)
    gsys = _load(cfg["run"].get("generator_prompt", "generator_system.txt"))
    rsys = _load("reviewer_system.txt")
    ctmpl = _load("generator_iter_critic.txt")
    scale = cfg["run"].get("render_scale", 1.0)
    mt = cfg["run"].get("max_tokens", 40000)
    temp = cfg["run"].get("temperature", 0.1)

    # generator conversation (session memory)
    messages = [
        {"role": "system", "content": gsys},
        {"role": "user", "content": [
            llm.text_part("Reproduce this TARGET image as an SVG. Output ONLY the SVG."),
            llm.img_part(target_png)]},
    ]
    history, best, passed = [], None, False

    for it in range(max_iters):
        t0 = time.time()
        raw = llm.chat_messages(client, gen_model, messages, mt, temp)
        messages.append({"role": "assistant", "content": raw})
        svg = llm.extract_svg(raw)
        _write(os.path.join(out_dir, f"iter{it}.svg"), svg or raw)

        rec = {"iter": it}
        try:
            if not svg:
                raise ValueError("no <svg> found in model output")
            pngp, diffp, m = _render_and_score(svg, target_png, out_dir, it, scale)
            rec.update(m)
        except Exception as e:
            rec.update({"ssim": 0.0, "error": str(e), "regions": []})
            pngp = None

        # STATELESS reviewer: fresh judgment each round
        verdict = {"pass": False, "score": 0, "issues": []}
        if pngp is not None:
            rc = [llm.text_part("Compare the TARGET and CANDIDATE and judge fidelity."),
                  llm.text_part("IMAGE 1 = TARGET:"), llm.img_part(target_png),
                  llm.text_part("IMAGE 2 = CANDIDATE RENDER:"), llm.img_part(pngp)]
            rraw = llm.chat(client, review_model, rsys, rc, max_tokens=2000, temperature=0.0)
            verdict = llm.extract_json(rraw) or verdict
            _write(os.path.join(out_dir, f"iter{it}_review.json"),
                   json.dumps(verdict, ensure_ascii=False, indent=2))
        rec["review"] = {"pass": bool(verdict.get("pass")),
                         "score": verdict.get("score", 0),
                         "n_issues": len(verdict.get("issues", []))}
        rec["seconds"] = round(time.time() - t0, 1)
        history.append(rec)
        print(f"  [{gen_model}|review:{review_model}] critic iter {it}: "
              f"pass={rec['review']['pass']} score={rec['review']['score']} "
              f"ssim={rec.get('ssim')} ({rec['seconds']}s)", flush=True)

        score_key = verdict.get("score", 0) or 0
        if best is None or score_key > best.get("score", -1):
            best = {"iter": it, "score": score_key, "ssim": rec.get("ssim", 0),
                    "svg": os.path.join(out_dir, f"iter{it}.svg")}
        if verdict.get("pass") or it == max_iters - 1:
            passed = bool(verdict.get("pass"))
            break

        # feedback into generator's own conversation (keeps memory)
        if session:
            llm.prune_old_images(messages)
        if pngp is None:
            fb = [llm.text_part(
                f"Your previous output failed to render: {rec.get('error')}. "
                "Re-emit a valid, complete SVG (only the ```svg block)."),
                llm.text_part("TARGET:"), llm.img_part(target_png)]
        else:
            issues = verdict.get("issues", [])
            itxt = "\n".join(
                f"{i+1}. [{x.get('region','')}] {x.get('problem','')} -> {x.get('fix','')}"
                for i, x in enumerate(issues)) or "(improve overall fidelity to the target)"
            fb = [llm.text_part(ctmpl.format(score=verdict.get("score", 0), issues=itxt)),
                  llm.text_part("IMAGE 1 = TARGET:"), llm.img_part(target_png),
                  llm.text_part("IMAGE 2 = YOUR CURRENT RENDER:"), llm.img_part(pngp)]
        messages.append({"role": "user", "content": fb})
        if not session:
            messages = [messages[0], messages[-1]]

    summary = {"gen_model": gen_model, "review_model": review_model, "mode": "critic",
               "target": target_png, "session": session, "passed": passed,
               "best": best, "history": history}
    _write(os.path.join(out_dir, "metrics.json"),
           json.dumps(summary, ensure_ascii=False, indent=2))
    return {"model": gen_model, "reviewer": review_model, "mode": "critic",
            "passed": passed, "best_score": best.get("score"),
            "best_ssim": best.get("ssim"), "iters": len(history), "out_dir": out_dir}
