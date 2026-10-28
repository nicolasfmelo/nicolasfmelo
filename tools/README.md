# Profile assets generator

Builds every SVG in `../assets` with the nicolasfmelo.org identity. Text is converted to vector paths, so nothing depends on fonts in the browser.

```sh
# 1. fonts (Google Fonts, variable TTFs)
mkdir -p fonts
curl -sL -o fonts/Outfit.ttf  "https://github.com/google/fonts/raw/main/ofl/outfit/Outfit%5Bwght%5D.ttf"
curl -sL -o fonts/JBMono.ttf  "https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf"
curl -sL -o fonts/Inter.ttf   "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf"

# 2. (optional) re-export the LiDAR car from the portfolio repo
bun dump.ts car.json

# 3. build
uv run --with fonttools --with uharfbuzz build.py fonts ../assets
```

Copy lives in `build.py` (cards, stack, path). The banner car is the same point cloud as the portfolio hero (`lib/particles/car.ts`, seed 11).
