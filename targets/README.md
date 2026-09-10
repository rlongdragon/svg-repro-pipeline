# targets/

Put the raster figures you want reproduced here (PNG/JPG), then point the
runner at them:

```bash
python run.py  --target targets/your_figure.png --mode critic
python bench.py --target targets/your_figure.png --mode critic --pairs self
```

Image files in this folder are git-ignored (they are usually private). Only this
README is tracked.
