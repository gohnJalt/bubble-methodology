# Filter study — can smoothing rescue the Asia signal?

Run 2026-09-22 via `filters.py`. Tables in `results/filter_*.csv`.
Question: Asia's z carries almost no information about forward real returns
(WINDOW-STUDY.md §5). Is that noise a filter could remove?

**Answer: no. Asia's problem is not noise, and no filter tested is worth adopting.**

## The constraint that shapes this entire study

**The textbook HP filter is two-sided.** Its trend at month *t* is fitted using
months *after* t. Detrending with it and then correlating the result against
forward returns leaks the future into the signal — it would have produced a
spectacular and completely meaningless improvement.

So every filter here is **one-sided**: the value at month *t* uses months ≤ *t*
only, exactly like `trend_z`. The one-sided HP re-solves the filter on `p[:t+1]`
at every *t* and keeps only the last point.

This is asserted, not assumed. `filters._selfcheck` mutates the future
(`y[150:] += 10`) and checks the past does not move — and also checks that the
**two-sided** filter *fails* that same test, so the test cannot pass vacuously.

## What was tested

Two competing explanations for Asia's failure, on all four markets — a filter
that only helps Asia is fitted to Asia:

- **A: "the price is noisy"** — smooth `p` with a trailing 3/6/12-month mean,
  then run the ordinary `trend_z` on the smoothed series.
- **B: "a straight line is the wrong trend"** — replace the rolling linear trend
  with a one-sided HP trend (λ = 1600 / 14400 / 129600) and standardise the cycle
  by its own trailing standard deviation.

Metric is unchanged from the window study: Spearman ρ between signal and forward
24m real return, at each market's default window. More negative is better.

## Result 1 — HP as a detrender is strictly worse

ρ(signal, fwd 24m real), 2005 onward:

| filter | New York | London | Asia | Turkey |
|---|---|---|---|---|
| **baseline (linear)** | **−0.581** | **−0.419** | **−0.303** | −0.376 |
| hp λ=1600 | −0.056 | −0.006 | −0.049 | −0.189 |
| hp λ=14400 | −0.305 | −0.112 | −0.048 | −0.261 |
| hp λ=129600 | −0.542 | −0.229 | −0.035 | **−0.395** |

HP destroys the signal at every λ on three of four markets, and the pattern
explains itself: **as λ→∞ the HP trend converges to a straight line**, so the best
HP can ever do is approach the existing linear detrend from below. Small λ tracks
the price too closely, leaving a cycle made of high-frequency wiggle with no
bubble information in it. Large λ converges back toward baseline.

There is no λ at which HP beats the rolling linear trend on the markets that
work. Turkey's marginal −0.395 vs −0.376 at λ=129600 is noise, and at that λ the
filter is nearly a straight line anyway.

## Result 2 — smoothing helps Asia a little, and costs more elsewhere

| filter | New York | London | Asia | Turkey |
|---|---|---|---|---|
| | *2005+ / 2nd half* | | | |
| baseline | −0.581 / −0.435 | −0.419 / −0.361 | −0.303 / −0.198 | −0.376 / −0.298 |
| ma3 | −0.594 / −0.462 | −0.417 / −0.352 | −0.316 / −0.213 | −0.351 / −0.303 |
| ma6 | −0.594 / −0.477 | −0.413 / −0.336 | −0.324 / −0.237 | −0.292 / −0.290 |
| ma12 | −0.536 / −0.473 | −0.359 / −0.261 | **−0.332 / −0.298** | −0.173 / −0.263 |

A trailing 12-month mean does improve Asia's second half meaningfully
(−0.198 → −0.298). But it costs Turkey badly on the full sample
(−0.376 → −0.173) and London from 2005 (−0.419 → −0.359). On the full sample
Asia is *still wrong-signed* with ma12 (+0.099 vs +0.159 baseline) — smoothing
narrows the problem, it does not fix it.

`ma3`/`ma6` are roughly free on New York and mildly positive on Asia, but the
gains are small enough to be noise and they cost Turkey.

**Nothing here earns a place in the model.** Adding a filter would mean a new
parameter, a new failure mode, and a per-market tuning argument, in exchange for
a change that is within noise on three markets.

Note the baseline is already lightly smoothed: `price_index` uses the **monthly
mean of daily closes**, not the month-end close. Some of the easy noise reduction
is already priced in, which is a likely reason further smoothing adds so little.

## Result 3 — why Asia actually fails

Asia by era, ρ(z, fwd 24m real), at the 120m window:

| era | baseline | ma6 | ma12 | hp129600 | n |
|---|---|---|---|---|---|
| **1970–1989 (bull)** | **+0.617** | +0.611 | +0.567 | +0.398 | 96 |
| 1990–2003 (bust) | −0.256 | −0.335 | −0.397 | −0.092 | 143 |
| 2004–2012 | −0.216 | −0.311 | −0.387 | +0.254 | 83 |
| 2013–2026 | −0.226 | −0.219 | −0.230 | −0.247 | 140 |

**Asia's entire failure is 1970–1989.** Every other era behaves normally, in line
with the other three markets. No filter changes this — smoothing barely dents the
+0.617, because there is nothing noisy about it.

Real Nikkei over that era (1970 = 100): 81 → 124 → **340**. Twenty years of
near-unbroken secular re-rating, during which price sat above any trailing trend
and *kept rising*. A trend-deviation model is structurally uninformative in that
regime, and it is a property of the methodology, not of Japanese data quality.

It is not simply that the signal was early. Earliness would show up as a sign
flip at longer horizons; instead 1970–89 stays positive out to 60 months
(+0.406 at 12m, +0.617 at 24m, +0.761 at 36m, +0.449 at 60m). For two decades,
high z genuinely preceded higher returns. Then 1989-12 was flagged at the exact
peak and real prices fell ~80% over the following two decades. **One correct call
after nineteen wrong years is not a signal**, and averaging over the era says so.

## Outcome

Asia was subsequently **restricted to 1990 onward** on the strength of §3 — the
era table is what motivated it. The filter conclusion is unchanged: re-running
`filters.py` against the restricted configuration still shows HP worse than the
linear detrend everywhere and no moving average worth its parameter.

## Conclusion

- **Adopt no filter.** Keep the plain CPI-deflated log real price and the rolling
  linear detrend.
- HP is the wrong tool here regardless of sidedness: its best case is to
  approximate the linear trend already in use.
- **Asia's weakness is mostly regime, not noise.** The 1970–89 melt-up is what
  makes the full-sample number wrong-signed. But the individual post-1990 era
  slices above (−0.22 to −0.26) are *not* what the restricted model delivers
  end to end: fitted on 1990+ it scores −0.17 at the 120m window, still the
  weakest of the four. Sub-period correlations do not aggregate.
- Consequence for the product: Asia is now **restricted to 1990 onward**, fitted
  on the restricted history rather than merely displayed from it. This is a
  decision made after seeing the answer, so it is labelled on the market in the
  UI and on the methodology page rather than buried. See WINDOW-STUDY.md's
  addendum for the before/after numbers.

## Caveats

- Era ρ values rest on 83–143 monthly observations with heavy overlap; treat them
  as descriptive, not inferential.
- The filter grid is small by design (3 MA lengths, 3 λ). A wider grid searched
  against the same metric would mostly measure how hard the grid was searched.
- Only the *signal construction* was filtered. Nothing here tests filtering the
  macro overlay.
