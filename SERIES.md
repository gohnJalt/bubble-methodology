# Verified data series

Checked **2026-09-22** against the live APIs, with all three keys present. Re-check before trusting any of
this: providers retire series silently, which is exactly what bit the original
plan (see "Dead" below).

A series is "live" only if its last observation is within ~3 months of today.

## Live and in use

| Market | What | Spec | Last obs | Key? |
|---|---|---|---|---|
| New York | CPI | `fred:CPIAUCSL` | 2026-08 | no |
| New York | policy rate | `fred:FEDFUNDS` | current | no |
| New York | curve | `fred:T10Y3M` | current | no |
| New York | credit | `fred:TOTBKCR` | current | no |
| London | CPI (index, MM23 D7BT) | `ons:D7BT` | 2026-08 | no |
| London | policy rate | `fred:IRSTCI01GBM156N` | 2026-08 | no |
| London | curve | `fred:IRLTLT01GBM156N - fred:IRSTCI01GBM156N` | 2026-08 | no |
| Asia | CPI (2020-base, all items, all Japan) | `estat:0003427113?cdTab=1&cdCat01=0001&cdArea=00000` | 2026-08 | `ESTAT_APP_ID` |
| Asia | policy rate | `fred:IRSTCI01JPM156N` | 2026-08 | no |
| Asia | curve | `fred:IRLTLT01JPM156N - fred:IRSTCI01JPM156N` | 2026-08 | no |
| Turkey | CPI (general, spliced) | `evds:TP.GENENDEKS.T1 \| evds:TP.FG.A01` | 2026-08 | `EVDS_API_KEY` |
| Turkey | policy rate | `evds:TP.BISPOLFAIZ.TUR` | 2026-07 | `EVDS_API_KEY` |
| Turkey | credit (loans, deposit money banks, total) | `evds:TP.KM.B33` | 2026-07 | `EVDS_API_KEY` |
| all | prices | yfinance `^IXIC ^FTSE ^N225 XU100.IS` | current | no |

FRED is read through the **public CSV endpoint**
(`fred.stlouisfed.org/graph/fredgraph.csv?id=...`), which needs **no API key**.
`fredapi` and `FRED_API_KEY` were dropped from the design for this reason.

**Asia is verified and live.** `statsDataId=0003427113` is valid and returns 792
monthly values back to **1970-01**. The filters are mandatory: unfiltered, that
table is 13.5M values (every item x every city). `cdTab=1` = index (not YoY),
`cdCat01=0001` = all items, `cdArea=00000` = all Japan. The `@time` code is 10
chars (`2026000808` = 2026-08), **not** 8 — the annual row ends `0000` and must
be dropped.

## CBRT EVDS — resolved

The documented endpoint is gone; the working one was found via
**github.com/fatihmete/evds**. Two things were wrong in the original plan:

- **Host:** `evds2.tcmb.gov.tr` 302s to `evds3.tcmb.gov.tr`. The API base is
  `https://evds3.tcmb.gov.tr/igmevdsms-dis/`.
- **Endpoint shape:** parameters are appended to the base URL **as a raw path
  string** — not a query string, and not under any `/service/evds` subpath (that
  404s). So `requests(..., params=...)` cannot be used; the string is joined by
  hand. `formulas` and `aggregationTypes` must be present even when empty. The
  key goes in a `key` header.
- **Date format:** `startDate`/`endDate` are `DD-MM-YYYY`, but at `frequency=5`
  the response stamps each row `"YYYY-M"` in `Tarih` — *not* `DD-MM-YYYY`. Parse
  with `%Y-%m`. Values are strings; there is also a `UNIXTIME` column, which is
  local midnight and will land on the wrong month if parsed as UTC.

Useful discovery endpoints under that base: `categories/type=json`,
`datagroups/mode=0&code=&type=json`, `serieList/type=json&code=<datagroup>`.
Use them rather than guessing series ids — all three of my initial guesses were
stale or archived.

### Turkish CPI is rebased, and the old id is stranded

TURKSTAT rebased CPI to 2025=100. The consequences:

- `TP.FG.J0` (2003=100) — the obvious id, and the one in the original design —
  **stops at 2026-01** and its datagroup is flagged `(Archive)`. It looks fine
  until you check the last observation.
- `TP.TUKFIY2025.GENEL` (2025=100) is current but only starts **2005-01**.
- `TP.GENENDEKS.T1` is current (**2026-08**) and starts **2003-01** — longer, so
  it is the primary.
- BIST 100 price history starts **1997-07**, so even that loses six years,
  including the 2001 crisis. `TP.FG.A01` (all items, 1987-01 → 2004-12) overlaps
  it by 24 months and is chain-linked on via `data.splice`, giving continuous CPI
  from 1987 and a real BIST series covering its entire history.

Splicing is sound because two rebasings of one index differ by a constant factor;
the scale is the mean ratio over the whole overlap, so a single revised print
cannot shift the pre-splice history. `splice` refuses fewer than 6 overlapping
months rather than rescale on noise.

## Dead — do not use

| Series | Last obs | Note |
|---|---|---|
| `JPNCPIALLMINMEI` | 2021-06 | OECD MEI, discontinued on FRED |
| `CPALTT01JPM661S` | 2021-06 | same |
| `CPALTT01JPM657N` | 2021-06 | same |
| `JPNCPIALLAINMEI` | 2020-01 | same |
| `GBRCPIALLMINMEI` | 2025-03 | OECD MEI, discontinued on FRED |
| `GBRCPALTT01IXNBM` | 2023-11 | same |
| `INTDSRJPM193N` | 2017-04 | discontinued |
| `api.ons.gov.uk` | — | decommissioned 2024-11-25; use the CSV generator |
| `evds2.tcmb.gov.tr/service/evds` | — | 302s to the evds3 SPA; use igmevdsms-dis |
| `TP.FG.J0` | 2026-01 | Turkish CPI 2003-base, archived after the 2025 rebasing |
| `TP.APIFON4` | 2026-09 | daily funding cost, not the policy rate; use `TP.BISPOLFAIZ.TUR` |
| `TP.KREDI.L001` | 2025-01 | stale; use `TP.KM.B33` |

Also tried and rejected: OECD SDMX (`sdmx.oecd.org`, returns `NoRecordsFound`
for the prices dataflow), IMF IFS SDMX (returns empty), IMF DataMapper (annual
only), Japan Statistics Bureau direct CSV (404).

## Gotchas

- **ONS 403s urllib's default user-agent**, so `pd.read_csv(url)` fails. Fetch
  with `requests` and a browser UA. The CSV mixes annual, quarterly and monthly
  rows in one column; only `^\d{4} [A-Z]{3}$` rows are monthly.
- **FRED needs no key here.** `FRED_API_KEY` is in `.env` and is unused: the CSV
  endpoint is public. Keep the key if you later want the JSON API's search, which
  does require one.
- **CPI base years differ** across these sources and do not need reconciling: a
  constant scale on CPI is an additive constant on log real price, which the
  rolling detrend removes. Do not renormalise.
