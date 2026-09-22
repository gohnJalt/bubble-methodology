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

## Deploy (Streamlit Community Cloud)

1. Point Community Cloud at this repo, main file `app.py`, Python **3.13**.
2. Paste the two keys into the app's **Secrets** box (Settings → Secrets):

   ```toml
   EVDS_API_KEY = "..."
   ESTAT_APP_ID = "..."
   ```

   They are read through `st.secrets` and never live in the repo. FRED, ONS and
   yfinance need no key.
3. There is nothing to seed. A cold start refetches all four markets in ~18s and
   builds a ~1 MB parquet cache in the container. No API data is committed here,
   which also keeps CBRT and e-Stat terms of use out of the picture.

Cloud storage is ephemeral: the cache rebuilds after a restart, which costs that
same ~18s on the next page load.

## Findings

| Doc | What it settles |
|---|---|
| `WINDOW-STUDY.md` | Window defaults: **New York 84m, others 120m**. Why 240m was dropped. |
| `FILTER-STUDY.md` | No filter adopted; why Asia is weak and smoothing does not fix it. |
| `SERIES.md` | Which data series are live, dead, and how each API actually behaves. |

Raw tables for both studies are in `results/`.

Every module runs its own self-check: `.venv/bin/python <bubble|overlay|data|evaluate|filters>.py`.

## Not built yet

- Turkey's USD-converted context series (DESIGN.md §1).
- Dockerfile / deployment.
