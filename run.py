#!/usr/bin/env python3
"""Benchmark VLMs on iterative image-to-SVG reproduction.

Examples:
  export SVGBENCH_API_KEY=sk-...
  python run.py --target targets/fig4.png --mode diff
  python run.py --target targets/fig4.png --mode critic --models gpt-4o,gemini-2.5-pro --reviewer gpt-4o
"""
import os
import time
import json
import argparse
import yaml
from svgbench import pipeline


def main():
    ap = argparse.ArgumentParser(description="image->SVG VLM benchmark")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--target", required=True, help="target PNG/JPG to reproduce")
    ap.add_argument("--mode", choices=["diff", "critic"], help="override config.run.mode")
    ap.add_argument("--models", help="comma list of generator models (overrides config)")
    ap.add_argument("--reviewer", help="critic reviewer model (V2)")
    ap.add_argument("--max-iters", type=int, help="max repair iterations")
    ap.add_argument("--no-session", action="store_true",
                    help="disable generator conversation memory (stateless per iter)")
    ap.add_argument("--out", default="runs", help="output root dir")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    mode = args.mode or cfg["run"]["mode"]
    models = args.models.split(",") if args.models else cfg["models"]
    max_iters = args.max_iters or cfg["run"]["max_iters"]
    thr = cfg["run"].get("ssim_threshold", 0.92)
    session = cfg["run"].get("session", True) and not args.no_session
    reviewer = args.reviewer or cfg.get("reviewer_model")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    tname = os.path.splitext(os.path.basename(args.target))[0]
    results = []
    for model in models:
        safe = model.replace("/", "_").replace(":", "_")
        out_dir = os.path.join(args.out, f"{stamp}_{tname}_{mode}_{safe}")
        print(f"== {mode} | {model} -> {out_dir}")
        if mode == "diff":
            r = pipeline.run_diff(cfg, args.target, model, out_dir, max_iters, thr, session)
        else:
            r = pipeline.run_critic(cfg, args.target, model, reviewer or model,
                                    out_dir, max_iters, session)
        results.append(r)

    # summary table
    os.makedirs(args.out, exist_ok=True)
    md = [f"# svgbench results — {tname} — mode={mode} — {stamp}", ""]
    if mode == "diff":
        md += ["| model | best SSIM | iters | out |", "|---|---|---|---|"]
        for r in results:
            md.append(f"| {r['model']} | {r['best_ssim']:.4f} | {r['iters']} | {r['out_dir']} |")
    else:
        md += ["| gen model | reviewer | passed | best score | best SSIM | iters | out |",
               "|---|---|---|---|---|---|---|"]
        for r in results:
            md.append(f"| {r['model']} | {r['reviewer']} | {r['passed']} | "
                      f"{r.get('best_score')} | {r.get('best_ssim')} | {r['iters']} | {r['out_dir']} |")
    summary_path = os.path.join(args.out, f"summary_{stamp}_{tname}_{mode}.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nsummary -> {summary_path}")
    with open(os.path.join(args.out, f"summary_{stamp}_{tname}_{mode}.json"),
              "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
