# Bubble Methodology

Rolling statistical test for whether an equity index trades above what its own
history implies, across New York, London, Asia and Turkey.

Design and rationale: **DESIGN.md**. Verified data series: **SERIES.md**.

## Run

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # add keys for Asia + Turkey
.venv/bin/streamlit run app.py
```

Or in a container (keys are read from `.env` at run time, never baked in):

```sh
docker compose up --build     # http://localhost:8501
```

The parquet cache lives in a named volume, so a restart does not refetch.

New York and London need no credentials. Asia needs `ESTAT_APP_ID`, Turkey needs
`EVDS_API_KEY`. A market whose key is missing shows an error card; the rest of the
app works normally.

`FRED_API_KEY` is not used: FRED's CSV endpoint is public.

## Files

| File | What |
|---|---|
| `bubble.py` | the model: `price_index`, `zcrit`, `trend_z`, `score` |
| `overlay.py` | macro overlay score — a separate signal, never mixed into z |
| `data.py` | market registry + fetch/parquet cache (yfinance, FRED, ONS, e-Stat, EVDS) |
| `app.py` | Streamlit UI |
| `theme.py` | design tokens, CSS, chart styling |
| `evaluate.py` | window study — regenerates every table in `results/` |
| `filters.py` | filter study (one-sided HP, moving averages) |
| `draft/` | the original notebook this was ported from |

## Findings
Raw tables for both window and filter studies are in `results/`.

Every module runs its own self-check: `.venv/bin/python <bubble|overlay|data|evaluate|filters>.py`.

## Not built yet

- Turkey's USD-converted context series (DESIGN.md §1).
- Dockerfile / deployment.
