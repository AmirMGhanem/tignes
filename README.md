# Tignes 2027

Trip plan + interactive piste map for Tignes / Val d'Isère, 8–21 January 2027.

**Live:** https://amirmghanem.github.io/tignes

- `template.html` — the page
- `build.py` — fetches runs & lifts (OpenStreetMap via OpenSkiData / SkiNavIndexes), computes length, drop,
  steepness 1–5 and a snow-holding estimate 1–5, then writes `_site/index.html`
- `.github/workflows/pages.yml` — builds and deploys to GitHub Pages on every push

Piste & lift data © OpenStreetMap contributors (ODbL), via OpenSkiData. Satellite imagery © Esri.
