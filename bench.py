#!/usr/bin/env python3
"""Benchmark a matrix of (generator, reviewer) pairs on one target.

Examples:
  # AA self-pairs (gen == reviewer) for every model in models.txt, critic mode:
  python bench.py --target targets/image.png --mode critic --pairs self

  # cross pairs (gen != reviewer) for a chosen subset:
  python bench.py --target targets/image.png --mode critic --pairs cross \
      --gens gpt-4o,gemini-2.5-flash \
      --revs claude-sonnet-4,gpt-4o

  # explicit pair list (gen|reviewer, comma-separated):
  python bench.py --target ... --pairs list \
      --pairs-list "gpt-4o|claude-sonnet-4,gemini-2.5-flash|gpt-4o"

  # diff mode: each model alone (reviewer ignored):
  python bench.py --target ... --mode diff --pairs self

Results stream to runs/matrix_<stamp>_<target>_<mode>_<tag>.md (+ .json),
rewritten after every pair so you can watch partial results.
"""
import os
import time
import json
import itertools
import argparse
import yaml
from svgbench import pipeline


def label(m):
    return m.rsplit("/", 1)[-1] if m else "-"


def read_models(path):
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def build_pairs(mode, gens, revs, kind, listspec):
    if mode == "diff":
        return [(g, None) for g in gens]
    if kind == "all":
        return list(itertools.product(gens, revs))
    if kind == "cross":
        return [(g, r) for g in gens for r in revs if g != r]
    if kind == "list":
        out = []
        for tok in listspec.split(","):
            g, r = tok.split("|")
            out.append((g.strip(), r.strip()))
        return out
    return [(g, g) for g in gens]  # self


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--target", required=True)
    ap.add_argument("--mode", choices=["critic", "diff"], default="critic")
    ap.add_argument("--models", default="models.txt")
    ap.add_argument("--gens", help="csv subset of generator models (default: all)")
    ap.add_argument("--revs", help="csv subset of reviewer models (default: all)")
    ap.add_argument("--pairs", choices=["self", "all", "cross", "list"], default="self")
    ap.add_argument("--pairs-list", default="")
    ap.add_argument("--max-iters", type=int)
    ap.add_argument("--no-session", action="store_true")
    ap.add_argument("--gen-prompt", help="generator system prompt filename in prompts/ (e.g. generator_system_v2.txt)")
    ap.add_argument("--out", default="runs")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    if a.gen_prompt:
        cfg.setdefault("run", {})["generator_prompt"] = a.gen_prompt
    allmodels = read_models(a.models)
    gens = a.gens.split(",") if a.gens else allmodels
    revs = a.revs.split(",") if a.revs else allmodels
    max_iters = a.max_iters or cfg["run"]["max_iters"]
    thr = cfg["run"].get("ssim_threshold", 0.92)
    session = cfg["run"].get("session", True) and not a.no_session
    pairs = build_pairs(a.mode, gens, revs, a.pairs, a.pairs_list)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    tname = os.path.splitext(os.path.basename(a.target))[0]
    tag = a.tag or a.pairs
    os.makedirs(a.out, exist_ok=True)
    mpath = os.path.join(a.out, f"matrix_{stamp}_{tname}_{a.mode}_{tag}")
    rows = []

    def flush():
        md = [f"# bench {tname} | mode={a.mode} | pairs={a.pairs} | session={session} | {stamp}",
              f"({len(rows)}/{len(pairs)} done)", ""]
        if a.mode == "critic":
            md += ["| # | generator | reviewer | passed | best_score | best_ssim | iters | sec | error |",
                   "|---|---|---|---|---|---|---|---|---|"]
            for i, r in enumerate(rows):
                md.append(f"| {i+1} | {label(r['gen'])} | {label(r['rev'])} | {r['passed']} "
                          f"| {r['score']} | {r['ssim']} | {r['iters']} | {r['sec']} | {r['err']} |")
        else:
            md += ["| # | model | best_ssim | iters | sec | error |",
                   "|---|---|---|---|---|---|"]
            for i, r in enumerate(rows):
                md.append(f"| {i+1} | {label(r['gen'])} | {r['ssim']} | {r['iters']} | {r['sec']} | {r['err']} |")
        with open(mpath + ".md", "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        with open(mpath + ".json", "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"bench: {len(pairs)} pairs, mode={a.mode}, session={session} -> {mpath}.md", flush=True)
    for idx, (g, r) in enumerate(pairs):
        od = os.path.join(a.out, f"{stamp}_{tname}_{a.mode}_{label(g)}__rev_{label(r)}")
        print(f"[{idx+1}/{len(pairs)}] gen={g} rev={r}", flush=True)
        t0 = time.time()
        try:
            if a.mode == "diff":
                res = pipeline.run_diff(cfg, a.target, g, od, max_iters, thr, session)
                row = {"gen": g, "rev": "-", "passed": "-", "score": "-",
                       "ssim": res["best_ssim"], "iters": res["iters"]}
            else:
                res = pipeline.run_critic(cfg, a.target, g, r, od, max_iters, session)
                row = {"gen": g, "rev": r, "passed": res["passed"], "score": res.get("best_score"),
                       "ssim": res.get("best_ssim"), "iters": res["iters"]}
            row["err"] = ""
        except Exception as e:
            row = {"gen": g, "rev": r, "passed": None, "score": None, "ssim": None,
                   "iters": None, "err": str(e)[:150].replace("\n", " ")}
        row["sec"] = round(time.time() - t0, 1)
        rows.append(row)
        flush()
        print(f"    -> ssim={row.get('ssim')} score={row.get('score')} "
              f"passed={row.get('passed')} ({row['sec']}s) err={row['err'][:60]}", flush=True)

    print(f"DONE -> {mpath}.md", flush=True)


if __name__ == "__main__":
    main()
