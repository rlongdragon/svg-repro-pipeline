# svg-repro-pipeline

Turn a raster figure into a clean, **editable** SVG with a vision LLM, refined
with automated feedback.

Two feedback modes:

- **`diff`** — scores the render against the target and feeds the differences back.
- **`critic`** — a separate reviewer model judges the render and feeds its notes
  back; the reviewer can be a different model.

Models are called through an **OpenAI-compatible** endpoint, so any provider works —
just set `base_url` + model ids.

## Pairs with figprompt

This pipeline is the vectorizing back end for
[rlongdragon/paperbanana-figprompt](https://github.com/rlongdragon/paperbanana-figprompt):

1. **figprompt** compiles your method text + caption into one dense figure prompt.
2. Hand that prompt to an image model to render the figure (a raster PNG).
3. **svg-repro-pipeline** turns that PNG into a clean, **editable** SVG you can tweak.

Full chain: *method text → figure prompt → rendered figure → editable SVG*.
Drop the rendered figure into `targets/` and run the commands below.

## Choosing models

Benchmark your own models with `bench.py` and read the matrix it writes to
`runs/matrix_*.md`, then:

- Pick the **generator** with the best SSIM. A stronger general vision model wins;
  the cheaper/faster ones trade fidelity for speed.
- Gate quality with an **independent reviewer**, not the generator grading itself —
  self-review tends to pass weak output.
- The **generator choice** matters more than the loop settings.

## Layout
```
config.example.yaml   # copy to config.yaml, set base_url + models
prompts/              # generator_system, generator_iter_diff, reviewer_system, generator_iter_critic
svgbench/
  llm.py        # OpenAI-compatible client, vision messages, svg/json extraction
  render.py     # SVG -> PNG via headless Chromium (faithful CJK)
  imgdiff.py    # SSIM + diff heatmap + mismatch regions
  pipeline.py   # the diff and critic loops
run.py          # CLI: run one target across a list of models
bench.py        # matrix runner: (generator, reviewer) pairs, streaming results
ping.py         # check which models in models.txt are reachable
selftest.py     # verify render+diff without an API key
```

## Setup (Linux)
```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
sudo python -m playwright install-deps chromium      # system libs
sudo apt-get install -y fonts-noto-cjk               # CJK glyphs for Chromium
cp config.example.yaml config.yaml                   # set the `models:` list
cp .env.example .env                                 # then fill endpoint + key:
#   SVGBENCH_BASE_URL=https://your-relay/v1
#   SVGBENCH_API_KEY=sk-...
```
`.env` is auto-loaded (python-dotenv) and overrides `config.yaml`'s `api:` block.

## Verify (no API needed)
```bash
python selftest.py path/to/any.svg     # renders + self-diffs; SSIM ~1.0 => render+diff OK
```

## Run
Model ids below are examples — use whatever your endpoint calls them
(and list them in `models.txt` / `config.yaml`).

```bash
# check reachable models first
python ping.py

# critic mode
python run.py --target targets/figure.png --mode critic --models gpt-4o

# diff mode
python run.py --target targets/figure.png --mode diff --models gpt-4o

# benchmark a matrix of models (self-review), streaming results to runs/matrix_*.md
python bench.py --target targets/figure.png --mode critic --pairs self

# cross-review: an independent reviewer grades each generator
python bench.py --target targets/figure.png --mode critic --pairs cross \
    --gens claude-sonnet-4,gemini-2.5-flash --revs gpt-4o
```

Outputs per run in `runs/<stamp>_<target>_<mode>_<model>/`:
`iter{N}.svg`, `iter{N}.png`, `iter{N}_diff.png`, `iter{N}_review.json`, `metrics.json`.
A cross-model `summary_*.md` table is written to `runs/`.

## Metrics
- **SSIM** (0–1): structural similarity of the render to the target.
- **reviewer score / pass**: the reviewer model's judgment (critic mode).

## Prompt design
The generator/reviewer prompts follow a structured spec discipline (ROLE, ELEMENTS,
CONNECTIONS, TYPOGRAPHY, LAYOUT, CONSTRAINTS, self-critique) adapted for *reproduction*
(fidelity to the target wins over any style rule). Figure-literacy vocabulary in
`prompts/style_guide.md` is summarized/adapted from
[rlongdragon/paperbanana-figprompt](https://github.com/rlongdragon/paperbanana-figprompt)
(condensed from PaperBanana's NeurIPS diagram style guide, Google LLC, Apache-2.0).

## Notes
- The target is a raster image (PNG/JPG). Put your originals in `targets/`.
- `render.py` sizes the viewport to the SVG's own width/height; keep those explicit.
- Everything the generator makes is semantic SVG (real `<text>`, shapes), so a passing
  result is also **editable**, not a traced blob.
