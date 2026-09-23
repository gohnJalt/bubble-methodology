# Bubble Methodology — Design Doc

Status: implemented. All four markets live.
Written and built 2026-09-22. Verified series live in SERIES.md.
Audience: the agents and coders who build this. Read it all before writing code.

---

## 1. What this is

A rolling statistical test for whether an equity index is trading above what its
own recent history implies, run over four markets, served as a web UI.

The draft (`draft/bubble-methodology.ipynb`) already contains the working core and
it is correct. **Do not rewrite the math.** Port `price_index`, `zcrit` and
`trend_z` out of the notebook substantially as they are. The notebook's docstrings
explain non-obvious choices (leverage correction, CPI hole interpolation, partial
last month); keep them.

What is new: four markets instead of one, real data pipelines instead of a CSV on
disk, a macro overlay score, and a UI.

### The four markets

| Market   | Index  | Ticker   | Local CPI source | Currency |
|----------|--------|----------|------------------|----------|
| New York | Nasdaq Composite | `^IXIC` | FRED `CPIAUCSL` | USD |
| London   | FTSE 100 | `^FTSE` | ONS `D7BT` (§3.2) | GBP |
| Asia     | Nikkei 225 | `^N225` | e-Stat (§3.2) | JPY |
| Turkey   | BIST 100 | `XU100.IS` | CBRT EVDS `TP.FG.J0` | TRY |

Every market is treated identically: **local index deflated by local CPI**. No
special cases. Turkey's USD-converted series (`XU100.IS / USDTRY=X`, deflated by
US CPI) is computed and plotted as *context only* — it never produces a z-score
or a bubble state. This is a deliberate decision: consistency across markets
beats per-market cleverness, and the moment one market gets a bespoke deflator
the cross-market comparison on the landing page becomes meaningless.

---

## 2. Methodology

### 2.1 Real price index — `price_index(price, cpi)`

Port unchanged from notebook cell 3. Recap of what it does and why:

1. Resample daily nominal close to month-end mean (`'ME'`, `.mean()`). Mean, not
   last — a single day's close is noise; the month's mean is the month's level.
2. Drop the final month if the price series ends mid-month (its mean would be a
   partial month, biased by whatever happened in the first half).
3. Resample CPI to month-end (`.last()`; FRED stamps CPI on the 1st).
4. Reindex both onto a **contiguous** monthly `period_range` over the overlap.
   Contiguity is load-bearing — `trend_z` uses `sliding_window_view` over a raw
   numpy array and has no notion of dates; a gap silently corrupts the time axis.
5. Interpolate interior CPI holes (`limit_area='inside'`) and log which months
   were filled. Real gaps exist (e.g. 2025-10 CPIAUCSL was never published during
   the shutdown). Dropping the month would shorten the time axis every rolling
   window sees; interpolating one month of a smooth series is the lesser evil.
6. Return a frame with columns `nom`, `cpi`, `real` (= nom/cpi), `p` (= log real).

**Turkey caveat for implementers:** CBRT EVDS returns CPI with a different base
year and index convention than FRED. `price_index` does not care about the base —
a constant scale factor on CPI is an additive constant in `p`, and `trend_z`
detrends it away. Do not "normalise" bases. Do check the EVDS series is monthly
and not already YoY.

### 2.2 Rolling detrended z — `trend_z(p, window, k)`

Port unchanged from notebook cell 5. What it computes, per month *t*:

- Fit a linear trend to the `window` months **ending at** *t*. No look-ahead
  anywhere in this model. Every number shown for month *t* was computable at *t*.
- Measure *t* against that trend **with *t* deleted from the fit**. This is the
  part people get wrong. The last point of a linear fit is its highest-leverage
  point; an in-sample residual there is shrunk by `sqrt(1-h)`, which is ~16% at
  a 12-month window and <1% at 240. Uncorrected, z is not comparable across
  window lengths — and comparing window lengths is a headline feature of the UI.
- `z = (p_t − trend_t) / sd_t`, distributed **t(window−3)** under a
  trend-stationary null.
- Returns `trend`, `sd`, `z`, `upper` (= trend + k·sd).

### 2.3 Threshold — `zcrit(window, sigma=2.0)`

`stats.t.isf(stats.norm.sf(sigma), window - 3)`. The threshold that carries the
same tail area as `sigma` on a normal, at this window's degrees of freedom. A
flat 2.0 is a looser test on short windows. **Always pass `k=zcrit(window)`** —
never hardcode 2.0. Ranges from 2.32 (w=12) to 2.01 (w=360).

### 2.4 Bubble state

`z > zcrit(window)`. An **entry** is a month where the state flips False→True
(`bub & ~bub.shift(1)`). Entries are what the UI marks and lists, not every
individual bubble month — a 30-month episode is one event, not 30.

### 2.5 Window choice — settled, see WINDOW-STUDY.md

**Per-market defaults: New York 84m, London / Asia / Turkey 120m.** Set as
`window` in the `data.MARKETS` registry. The UI still exposes
12/24/36/60/84/120/240/360, because the window is the single biggest judgement
call in the model and hiding it would be dishonest.

240m was the original default and **is not defensible**. On Nasdaq it is
wrong-signed (ρ = +0.08 against forward 24m real returns) while flagging 14.5% of
months — 6.4x the rate its own threshold claims. On London and Turkey it never
fires at all. Windows <=36m carry no information anywhere.

The choice was made on criteria fixed in `evaluate.py` before results were read,
led by a threshold-free measure (rank correlation of z against forward real
return). Nasdaq's 84m preference survives removing the entire dot-com era — it
gets *stronger* — and holds in every subsample and at every horizon.

Do not re-tune the window to make a particular episode look right. Any agent that
finds itself selecting a window because the output "looks more correct" has left
statistics and entered curve-fitting; stop and flag it instead. If the window is
revisited, re-run `evaluate.py` and argue from its tables.

**Asia is restricted to 1990 onward and is still the weakest market.** The
Nikkei's 1970-89 secular re-rating made z wrong-signed over the full sample
(WINDOW-STUDY.md §5, FILTER-STUDY.md §3), so `MARKETS["asia"]["start"]` cuts the
history at 1990-01.

The cut is applied in `data.load` **before** `bubble.score`, deliberately: a
display-only trim would leave the excluded era setting the trend for the readings
immediately after it. The cost is that readings begin `window` months after the
start (1999-12 at 120m).

Restricting removes the wrong sign but does not make Asia comparable
(rho -0.17 vs -0.26 to -0.38 elsewhere), so it keeps `weak=True` and a `note`.
Both are rendered on the overview rail and the market page. **The restriction was
chosen after seeing the result**; that is recorded in the UI, not hidden. Any
market may carry `start`/`note`/`weak` the same way -- it is not an Asia special
case in the code.

### 2.6 Macro overlay score — NEW, must not touch z

A **separate, independently-labelled** signal. It is never blended into z, never
changes the bubble state, and is never averaged with it into one number. Two
signals shown side by side; the user does the synthesis.

Rationale for its existence: z says "price is far above its own trend". It cannot
say "and credit is cheap and leverage is building", which is what distinguishes a
melt-up from a bubble. The overlay carries that, separately, so neither signal
contaminates the other.

**Definition.** Three components, each monthly, each oriented so that **higher =
looser / more bubble-supportive**:

| Component | Formula | Orientation |
|-----------|---------|-------------|
| Real policy rate | `policy_rate − cpi_yoy` | negated (low real rate → high score) |
| Credit growth | YoY % change in domestic credit to private sector | as-is |
| Curve slope | `10y − 3m` | as-is |

Each component is z-scored against its **own trailing 10-year window** (120m,
expanding until 120 observations exist, `NaN` before 60). Overlay score is the
**mean of available component z-scores** — components missing for a market simply
drop out of the mean. Do not
impute a missing macro series with zero; a missing series is missing, not neutral.

Presented as a −3..+3 dial with a 24-month history sparkline. Bands: `< −1` tight,
`−1..+1` neutral, `> +1` loose. These bands are presentational, not statistical
claims.

Open, deliberately deferred: no backtest of whether the overlay adds predictive
power. It is a context panel, and it is labelled as one. If it is ever promoted
to a signal that changes decisions, it needs validation first.

### 2.7 Filters — tested and rejected, see FILTER-STUDY.md

Trailing moving averages (3/6/12m) and a **one-sided** HP filter (lambda =
1600/14400/129600) were tested on all four markets as both a smoother and a
replacement detrender. **None is adopted.**

HP is structurally the wrong tool: as lambda grows its trend converges to a
straight line, so its best case is to approximate the linear detrend already in
use, and at small lambda it tracks price too closely to leave any bubble signal.

**If anyone revisits this: the standard HP filter is two-sided and uses data
after month t.** Using it here would violate the no-look-ahead rule in section 7
and produce a large, fake improvement. `filters.py` is one-sided throughout and
its self-check proves it by mutating the future and asserting the past does not
move.

---

## 3. Data pipeline

### 3.1 Shape

```
data/
  cache/
    px_^IXIC.parquet        # daily nominal close
    px_^FTSE.parquet
    px_^N225.parquet
    px_XU100.IS.parquet
    px_USDTRY=X.parquet
    fred_CPIAUCSL.parquet   # one file per FRED series
    fred_<...>.parquet
    evds_TP.FG.J0.parquet   # one file per EVDS series
```

**Fetch on demand with a staleness check.** On request, if the parquet is absent
or its mtime is older than the refresh interval, refetch and rewrite; otherwise
read it. No scheduler, no database, no cron, no migration story. Identical
behaviour on localhost and in a container.

Refresh intervals: prices 1 day, CPI and macro 7 days (these are monthly series;
hitting FRED hourly for a number that changes twelve times a year is pointless).

**Cache misses must degrade, not crash.** If a fetch fails and a stale parquet
exists, serve the stale data and surface a visible "data as of <date>, refresh
failed" banner in the UI. A market whose data cannot be loaded at all renders as
an explicit error card — the other three markets still render. One dead API must
never take the page down.

### 3.2 Sources

**yfinance** — all five price series. No key. Known to rate-limit; the cache is
the mitigation. Fetch full history (`period='max'`), not a fixed start date — a
240-month window discards the first 20 years before producing anything.

**FRED** — via the **public CSV endpoint**
(`fred.stlouisfed.org/graph/fredgraph.csv?id=...`), which needs **no API key**.
`fredapi` and `FRED_API_KEY` were in the original plan and have been dropped:
one fewer dependency and one fewer credential. Note FRED 403s nothing, but see
the ONS gotcha below for the general user-agent problem.

> ✅ **Verification was run (2026-09-22) and it found exactly the failure it was
> looking for.** Every OECD "Main Economic Indicators" CPI series on FRED is
> dead: `JPNCPIALLMINMEI` stops at **2021-06**, `GBRCPIALLMINMEI` at **2025-03**,
> and the whole `CPALTT01*` family with them. Had these been wired in unchecked,
> the app would have served Japanese CPI five years stale and called it current.
> Full results, including the sources tried and rejected, are in **SERIES.md**.
> Re-run this check before trusting any series; providers retire them silently.

Replacements found:

- **UK CPI** → **ONS**, the `MM23`/`D7BT` all-items index, via the public CSV
  generator. No key, current to 2026-08. The old `api.ons.gov.uk` was
  decommissioned 2024-11-25. ONS **403s urllib's default user-agent**, so
  `pd.read_csv(url)` fails — fetch with `requests` and a browser UA. The CSV
  mixes annual, quarterly and monthly rows; keep only `^\d{4} [A-Z]{3}$`.
- **Japan CPI** → **e-Stat** (`api.e-stat.go.jp`), key `ESTAT_APP_ID`, free
  registration. The `statsDataId` in the registry is **a guess until the key
  exists** — e-Stat retires table ids at each CPI rebasing. Verify before trusting.
- **UK/Japan rates** → the non-MEI FRED series survived and are live:
  `IRSTCI01{GB,JP}M156N` (short) and `IRLTLT01{GB,JP}M156N` (long). No ready-made
  spread exists for these, so the registry supports a derived spec,
  `"fred:A - fred:B"`, for the curve slope.

Macro components per market, as actually wired (see SERIES.md for last-observation
dates): US has all three; UK and Japan have real rate + curve and run on **2 of 3**;
Turkey is specced for real rate + credit, also 2 of 3. A market with fewer
components is not penalised — the overlay averages what exists and the UI states
the count.

**CBRT EVDS** — direct REST, no pytuik. Key from env `EVDS_API_KEY`, sent as the
`key` header. **The endpoint in the original draft of this doc was wrong** — CBRT
migrated to EVDS3 and retired it. Correct shape, from github.com/fatihmete/evds:
base `https://evds3.tcmb.gov.tr/igmevdsms-dis/` with the params appended as a raw
path string, not a query string. Full details and the discovery endpoints are in
SERIES.md; do not re-derive them.

Turkish CPI needed a **splice**: TURKSTAT's 2025 rebasing stranded the obvious
series id at 2026-01. The registry supports `"evds:NEW | evds:OLD"` to chain-link
a retired index onto the current one. This is the one place a market needed
machinery the others did not, and it is generic rather than Turkey-specific —
any agency can rebase.

API keys are read from env, never committed. `.env.example` lists the two that
remain (`EVDS_API_KEY`, `ESTAT_APP_ID`); `.env` is gitignored. A missing key
produces a clear error naming the variable, and degrades that market to an error
card rather than taking the page down.

### 3.3 Registry

One declarative dict/TOML describing each market: name, ticker, CPI source+ID,
macro component source+IDs, currency, timezone, default window. Everything else
reads from it. Adding a fifth market must be a registry entry plus verified
series IDs — not a code change. This is the one abstraction worth having up
front, because the whole app is four instances of the same thing.

---

## 4. UI

Streamlit + Plotly. One command to localhost, containerises for deploy, no JS,
no build step, no API layer. If something external ever needs the numbers, a
read-only FastAPI endpoint bolts on later — do not build it now.

### 4.1 Landing — cross-market overview

Four cards, one per market, each showing:

- **Index name** — the index is the market's label throughout the UI; the city
  (New York / London / Asia / Turkey) is an internal registry key only. Plus
  currency and **current state** (`BUBBLE` / `elevated` / `normal`), colour
  coded. `elevated` = z within 1 of the threshold.
- Current `z` to 2dp, and the threshold it is being tested against.
- Macro overlay band and score (−3..+3). The component count is not shown: it is
  a property of the data sources, not a reading, and it competed with the score
  for the same glance.
- A small sparkline of z over the last 10 years with the threshold line.
- "Data as of <month>" — and the stale-data banner if the refresh failed.

Below: a single overlaid chart of z across all four markets, same window, so the
cross-market question ("is this one market or everything?") is answerable at a
glance. This chart is the reason the project has four markets instead of one.

### 4.2 Market detail page

The notebook's `plot_trend_z` figure, ported to Plotly, as the centrepiece:

- **Top panel**: log real price, rolling trend, `+k·sd` upper band with fill
  between trend and band, red shading where the bubble state is on, vertical
  rules at entries.
- **Bottom panel** (shared x, ~1:3 height): the z series, threshold line, zero
  line, fill above threshold.
- Keep the draft's palette: `#534AB7` price, `#888780` trend, `#BA7517` band,
  `#FAC775` fill, `#E24B4A` bubble shading, `#1D9E75` z.
- Plotly gets hover (date, price, trend, z), range selector, and zoom. That is
  the entire reason for porting rather than serving a static matplotlib PNG.

Controls: window selector (12…360), date range, toggle for the nominal series,
and — Turkey only — a toggle for the USD-converted context series, labelled
"context only, not scored".

Also on the page:

- **Entry table**: every bubble entry with date, z at entry, duration of the
  episode, and drawdown from the episode's peak to the next 24-month trough.
- **Macro overlay panel**: the three components as separate small charts with
  their raw values and trailing z-scores. Raw values matter — a reader needs to
  see "real policy rate is −4%", not just "component z = 1.8".
- **Window comparison**: the bubble state as a heat strip (months × window),
  8 rows. Makes the window's influence visible instead of a hidden parameter,
  and directly surfaces the §2.5 behaviour.

### 4.3 Methodology page

Static markdown: the model in plain language, the leverage correction explained,
the t-distribution and threshold, the known behaviour of short and long windows,
the explicit statement that the macro overlay does not enter z, and the
limitations section (§6). Every number in the app should be traceable to a
paragraph here. If a reader cannot work out what the app did from this page, the
page is wrong.

### 4.4 Non-negotiables

- Every chart states its window and threshold on the chart. A z-score without its
  window is meaningless.
- No "BUY"/"SELL"/"CRASH IMMINENT" framing anywhere. The model detects statistical
  deviation from trend. It does not forecast returns, and 1996 was four years
  early. The UI says what the model measured, never what to do about it.
- Currency and deflator are labelled on every real-price chart.
- Accessibility: state is never communicated by colour alone — the card carries
  the word `BUBBLE`, not just a red border.

---

## 5. Build order

1. ~~**Verify every series ID against the live APIs.** Write `SERIES.md`.~~
   **Done 2026-09-22** — and it caught dead Japanese and UK CPI before they
   shipped. See SERIES.md.
2. ~~Port `price_index`, `zcrit`, `trend_z` into a single module.~~ **Done** —
   `bubble.py`, self-check passing.
3. ~~Market registry + fetch/cache layer, with degrade-on-failure.~~ **Done** —
   `data.py`.
4. ~~Wire New York end to end and reproduce the notebook's entries exactly.~~
   **Done — exact match on all eight windows.** The port is verified.
5. London **done** (entries 1997-12 and 2025-10). Asia **done** via e-Stat, with
   history back to 1970 — it flags **1989-12**, the actual peak of the Japanese
   bubble, which is useful independent validation of the method.
   Turkey **done** — EVDS3 endpoint resolved and all three series ids replaced
   after the originals turned out archived or stale (SERIES.md). Real BIST covers
   1997-07 onward via a CPI splice back to 1987.
6. ~~Macro overlay.~~ **Done** — `overlay.py`, self-check passing.
7. ~~Streamlit UI.~~ **Done** — `app.py`. All pages render clean under
   `streamlit.testing.v1.AppTest`.
8. `.env.example` done. **Remaining: Dockerfile and deploy**, plus Turkey's
   USD-converted context series (§1), which is still not built.

## 6. Limitations — state these in the app, not just here

- A trend-stationary null is a strong assumption. Real equity indices have
  structural breaks, and the test cannot distinguish "bubble" from "regime change"
  or "genuine repricing of earnings power".
- z > threshold is not a timing signal. On Nasdaq at w=240 the state turns on in
  1995 — four years and a 4x before the peak.
- No multiple-testing correction across markets, windows or months. Running eight
  windows × four markets × 600 months and reporting the ones that fired is
  exactly how false positives are manufactured. The window-comparison view exists
  to make this visible rather than to let the reader shop for a result.
- Deflating by headline CPI is a choice. Asset prices and consumer prices are
  different objects.
- Turkey's CPI is contested. The model uses the official series; the app says so.

## 6b. Validation artefacts

- `evaluate.py` -> `results/` — window study: calibration, rank information by
  horizon, subsample and split-half stability, common-period comparison, Asia era
  breakdown, conditional returns and drawdowns. Report: **WINDOW-STUDY.md**.
- `filters.py` -> `results/filter_*.csv` — filter study. Report: **FILTER-STUDY.md**.

Both regenerate every table from source; the reports quote them, nothing is
transcribed by hand. Re-run both after any change to the methodology or the data
pipeline, and update the reports if the numbers move.

## 7. Conventions

- No look-ahead. Any new feature that uses information after month *t* to produce
  month *t*'s number is a bug, however good it makes the chart look.
- One self-check per non-trivial module — `assert`-based `demo()`/`__main__`, no
  test framework. The methodology module's check must include: (a) a synthetic
  series with a known linear trend plus a known spike returns the right z at the
  spike, (b) `zcrit` is monotonically decreasing in window, (c) a series with a
  month gap raises rather than silently mis-indexing.
- The reference check that matters most: **Nasdaq w=240 must reproduce the
  notebook's entry list** (1995-08, 1995-11, 1996-02, 1996-04, 1996-10, 1997-05,
  1998-11, 2020-12, 2021-11) on the same data vintage. Pin it as an assert.
- Deliberate shortcuts get a `ponytail:` comment naming the ceiling and the
  upgrade path.
- Secrets in env only. No keys, no `.env`, no cached parquet in git.

## 8. Explicitly out of scope

No auth, no user accounts, no alerting, no email, no database, no ML, no
backtest engine, no portfolio construction, no intraday data, no options-implied
anything. If one of these becomes necessary, it gets its own design doc.
