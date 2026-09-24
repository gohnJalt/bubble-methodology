# Bubble Methodology

Rolling statistical test for whether an equity index trades above what its own
history implies, across New York, London, Asia and Turkey.

Verified data series: **SERIES.md**.

## Run

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # add keys for Asia + Turkey
.venv/bin/python build.py     # runs the model, writes site/data.json
python3 -m http.server -d site 8000   # http://localhost:8000
```

New York and London need no credentials. Asia needs `ESTAT_APP_ID`, Turkey needs
`EVDS_API_KEY`. A market whose key is missing shows an error card; the rest of the
site works normally.

`FRED_API_KEY` is not used: FRED's CSV endpoint is public.

## Deploy

Static site on **Cloudflare** (Workers static assets, `wrangler.jsonc`). `.github/workflows/deploy.yml` runs daily, on
every push to `main` and on demand: it rebuilds `site/data.json` from the live
feeds and runs `wrangler deploy`. The parquet cache carries over between
runs, so a feed that fails is served stale and flagged on the page.

Repository secrets it needs: `CLOUDFLARE_API_TOKEN` (template "Edit Cloudflare
Workers", or a custom token with *Workers Scripts: Edit*), `CLOUDFLARE_ACCOUNT_ID`,
`EVDS_API_KEY`, `ESTAT_APP_ID`.

## Files

| File | What |
|---|---|
| `bubble.py` | the model: `price_index`, `zcrit`, `trend_z`, `score` |
| `overlay.py` | macro overlay score — a separate signal, never mixed into z |
| `data.py` | market registry + fetch/parquet cache (yfinance, FRED, ONS, e-Stat, EVDS) |
| `build.py` | runs every market × window, writes `site/data.json` |
| `site/index.html` | the whole UI: static HTML + Plotly.js, reads `data.json` |
| `evaluate.py` | window study — regenerates every table in `results/` |
| `filters.py` | filter study (one-sided HP, moving averages) |
| `draft/` | the original notebook this was ported from |

## Findings
Raw tables for both window and filter studies are in `results/`.

Every module runs its own self-check: `.venv/bin/python <bubble|overlay|data|evaluate|filters>.py`.

## Not built yet

- Turkey's USD-converted context series.
