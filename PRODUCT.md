# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The owner and a small desk (a few colleagues, occasionally leadership). They open the
site after the Borsa Istanbul close, most days, to answer two questions quickly: how
much can we lose tomorrow and is Turkish stress building (daily risk), and is any major
index stretched far above its own real trend (monthly valuation). They are
finance people but not quantitative specialists (2026-10-02): main pages say in plain
language what each chart or table shows; model names, validation and caveats live on
Methodology for technical readers.

## Product Purpose

One site that brings several independently validated market models together, so the
desk reads them side by side instead of in separate reports. It is growing from a
single bubble test into a market overview: **many models, few markets**. The overview
adds analytical lenses over a small, fixed set of markets rather than widening coverage.
Turkey is the deepest market because it is the only one with a daily risk model.

Success: the post-close check takes under a minute, and every number can be traced to
the model and the validation behind it.

## Positioning

Each lens is a separately validated statistical model with its pass and fail results
published next to it. The site never blends models into a composite score and never
turns a reading into advice. Two lenses today:

- **Valuation (monthly):** the Bubble Methodology. It measures each market's
  CPI-deflated real index against its own rolling trend, using a leverage-corrected z,
  a t-threshold and a separate macro overlay. It covers Nasdaq Composite, FTSE 100,
  Nikkei 225 and BIST 100.
- **Risk (daily):** the XU100 jump-diffusion risk monitor (repo `../jump-model`). It
  models XU100 in TRY and USDTRY jointly. It shows 1-day VaR/ES (MSGJ1-t) for
  XU100 TRY, USDTRY (long USD) and XU100 USD; 10-day VaR/ES for XU100 TRY and USD
  only (§8.7, not blind, with a live kill rule); a stress flag (MSGJ1, the XU100-USD
  volatility percentile, which turns on after 3 sessions above the 92.5th percentile);
  jump probabilities; and the FX share of USD risk.

## Operating Context

- Live URL: https://marketpanel.breezeblocks.workers.dev (Cloudflare Worker `marketpanel`, renamed from
  `bubble-methodology` on 2026-09-30).
- Valuation data is built in GitHub Actions (`build.py` writes `site/data.json`) every day
  at 06:30 UTC, on every push and on demand, and deployed as an assets-only Cloudflare
  Worker.
- Risk data is produced on the owner's Mac by launchd (`scripts/daily.sh`, weekdays
  19:30 and 22:30 GMT+3), because USDTRY comes from a local Bloomberg BFIX CSV. **Decided:**
  after a successful run, the Mac exports a compact derived JSON (from
  `reports/history.csv` and `reports/daily.csv`) into this repo and pushes, which
  triggers the deploy. Only derived numbers and returns are published, never the raw
  BFIX file.
- The two lenses update on different clocks: risk daily after the close, valuation
  monthly (with a provisional current month). The UI must show each lens's own as-of
  date.

## Capabilities and Constraints

- Static site: plain HTML and JS with Plotly from a CDN. No build step, no framework, and
  all maths stays in Python. Views are hash routes.
- The risk lens publishes only what `daily.py` reports: lower-tail VaR/ES only. The USDTRY
  10-day figures failed §8.6 and must never be shown. The lira-depreciation tail was not
  backtested and is not reported.
- The holdout period (2020 onward) is labelled as such, and live readings since
  2026-09-28 are labelled live. `history.csv` carries `period` =
  validation/holdout/live.
- Either lens can fail independently. Each degrades to a visible stale or error state
  without taking the other down.
- The site is named **Market Readings** for now. It is undecided, so keep the name
  swappable in one place. The valuation lens keeps the name "Bubble Methodology" as its
  model name.

## Brand Commitments

- Voice: plain, exact and self-limiting. It states what the model measured, never what to do.
  No BUY/SELL/CRASH framing (Bubble DESIGN §4.4).
- State is never shown by colour alone.
- Every chart states its window or horizon, its threshold or level, and its model.
- Each model's limitations are shown in the app, not only in docs.

## Evidence on Hand

- `site/data.json`: four markets × eight windows, episodes and macro overlay.
- `../jump-model/reports/history.csv`: one real-time row per session since 2013-01-02,
  about 3,400 rows. `../jump-model/reports/daily.csv`: the latest forecasts, including 10-day ones.
- Validation results: `results/*.csv` (bubble). Holdout §13, robustness §8.8 (12 of 16 pass,
  jumps not supported) and the executive brief are in `../jump-model`.
- No testimonials, users or performance claims beyond these published results.

## Product Principles

1. Separate lenses, never a blend. Put them side by side and let the reader do the synthesis.
2. Every number carries its model, horizon and as-of date.
3. Publish the failures next to the passes.
4. The post-close glance comes first; depth is one click away.
5. Adding a lens or a market means a registry entry, not a redesign.

## Accessibility & Inclusion

WCAG AA contrast. Keyboard-navigable routes and controls. Charts get text equivalents
for the headline reading.
