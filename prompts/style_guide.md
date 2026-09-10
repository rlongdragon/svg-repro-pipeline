# Figure style literacy (reference)

Adapted/summarized from **rlongdragon/paperbanana-figprompt**
(`skills/figprompt/style-guide.md`, itself condensed from PaperBanana's
NeurIPS diagram style guide, Google LLC, Apache-2.0). This file is REFERENCE
vocabulary for reading and precisely describing a figure. For *reproduction*,
the target image is ground truth — if it deviates from any point here, match
the target, not the guide.

## Color (as status, not component type)
- Zone/container backgrounds: very light desaturated pastels (cream, ice blue,
  mint, lavender), or white with a colored **dashed** border (minimalist/theory).
- Functional nodes: medium saturation, paired hues (blue/orange, green/purple,
  teal/pink). Color encodes STATUS: trainable = warm (red/orange/pink),
  frozen/static = cool (grey/ice-blue/cyan).
- High saturation (primary red, gold): reserved for error/loss, ground truth,
  or final output — nothing else.

## Shapes
- Processes/steps: rounded rectangles (radius ~5-10px) — the dominant shape.
- Tensors: 3D stacks/cuboids for volume; flat grids for matrices/tokens.
- Cylinders: databases / buffers / memory only.
- Macro-micro: a light container holds the overview, with a zoomed breakout box.
- Borders: solid = physical component; dashed = logical stage / optional path / scope.

## Lines & arrows
- Orthogonal/elbow for network architectures; curved/bezier for system logic
  and feedback loops.
- Solid = forward data flow; dashed = auxiliary (gradients, skip, loss, leaders).
- Operators sit ON the line/intersection: (+) add, (×) concat/multiply, ≥, →, ⇔.
- Never reuse one line style for both data flow and gradient/auxiliary flow.

## Typography
- Module labels: sans-serif (Arial/Roboto/Helvetica; here Noto Sans CJK for 中文).
  Bold headers, regular details.
- Math variables/symbols: **serif italic** (x, θ, Δ, q, E_flip, cos, margin).
  If it's in an equation, it's serif italic in the figure.

## Icons (keep conventional meaning)
- Trainable: flame/lightning. Frozen: snowflake/padlock/greyed stop.
- Inspect: magnifier. Compute: gear/monitor. Prompt: document/chat bubble.

## Amateur tells to avoid
- PowerPoint-default blue/orange with heavy black outlines.
- Font mixing (serif on a plain label; upright sans on a math variable).
- Randomly mixing flat 2D and 3D isometric shapes.
- Saturated yellow/blue grouping backgrounds.
- Identical arrow style for data vs gradient flow.
- The caption baked into the image; a redundant color legend.
