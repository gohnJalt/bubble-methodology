# Window-length study

Run 2026-09-22 via `evaluate.py` (`.venv/bin/python evaluate.py` → `window_study.csv`).
Question: the default is 240m; Nasdaq looks better at 84m. Which window, and does
the answer hold across markets?

## How this was judged

Criteria were fixed in `evaluate.py`'s docstring **before** results were looked
at, because picking a window off eyeballed episode lists is exactly the
curve-fitting DESIGN.md §2.5 warns against.

The primary measure is **threshold-free**: Spearman ρ between `z_t` and the
**forward real return** over the next *h* months. It cannot be gamed by moving
the threshold, and it asks the only question that matters — does a high z tell
you anything about what happens next? **It should be negative.** A positive ρ
means high z predicts *higher* returns, i.e. the thing is a momentum indicator
wearing a bubble costume.

Secondary: calibration (flag rate ÷ the 2.28% a one-sided 2σ test claims),
conditional forward returns with a circular block-bootstrap CI (blocks of 24
months, because overlapping forward windows make ordinary standard errors
meaningless), and forward 24m drawdown.

## 1. Short windows carry no information

ρ(z, fwd 24m real return), full samples:

| window | New York | London | Asia | Turkey |
|---|---|---|---|---|
| 12 | +0.01 | +0.08 | +0.05 | +0.01 |
| 24 | −0.08 | +0.15 | +0.03 | −0.01 |
| 36 | −0.24 | +0.18 | +0.06 | +0.06 |

At 12–24m ρ is ≈0 or wrong-signed everywhere. These are momentum indicators.
Confirms the draft's note that w=12 fires on 4.7% of months and means nothing.

## 2. 240m — the current default — is the worst choice

| | New York | London | Asia | Turkey |
|---|---|---|---|---|
| ρ(z, fwd24) | **+0.08** | −0.47 | −0.02 | −0.66 |
| flag rate ÷ nominal | **6.4×** | **0.0×** | 3.8× | **0.0×** |
| usable z obs | 428 | 225 | 441 | **111** |

240m fails in both possible directions at once:

- **On Nasdaq it is wrong-signed** (+0.08) while flagging 14.5% of months — 6.4×
  the rate its own threshold claims. It is simultaneously trigger-happy and
  uninformative. Over 20 years a straight line is a poor model of log real price,
  so residuals are strongly persistent and the test is badly mis-sized.
- **On London and Turkey it never fires at all** (0 entries, ever).
- On Turkey it leaves 111 z observations, below the 120 threshold for treating a
  row as evidence.

Its good-looking ρ on London/Turkey comes from windows that produce no signal, so
nothing downstream can use it.

## 3. Nasdaq at 84m is real, and it is not the dot-com bubble

ρ(z, fwd24) on Nasdaq under subsampling:

| window | full | excl 1995–2003 | pre-1995 | post-2003 |
|---|---|---|---|---|
| 36 | −0.24 | −0.35 | −0.43 | −0.30 |
| 60 | −0.27 | −0.40 | −0.36 | −0.45 |
| **84** | **−0.32** | **−0.50** | **−0.43** | **−0.55** |
| 120 | −0.22 | −0.45 | −0.41 | −0.47 |
| 240 | +0.08 | +0.04 | −0.63 | +0.06 |

Removing the entire dot-com era makes 84m **stronger**, not weaker (−0.50 vs
−0.32), and it is the best window in every subsample and at every horizon
(h=12: −0.23, h=24: −0.32, h=36: −0.25). Its calibration is also the best of any
window on any market — 1.9× nominal.

Economically, on the full Nasdaq sample at 84m: forward 24m real return averages
**−14.4%/yr when flagged vs +8.7%/yr when not**, a gap of −23.1 points
(90% block-bootstrap CI −31.6 to −14.7, excludes zero). Mean forward 24m
drawdown is −28.8% when flagged against a −11.1% base rate.

**The 84m call on Nasdaq is well supported.**

## 4. But 84m does not transfer — and the reason is era, not market

On full samples, London (+0.12) and Asia (+0.19) are wrong-signed at 84m. Split
each market at its own midpoint:

| market (split) | | 36 | 60 | 84 | 120 | 240 |
|---|---|---|---|---|---|---|
| New York (1998-11) | first | −0.29 | −0.20 | −0.19 | +0.04 | +0.43 |
| | second | −0.19 | −0.34 | **−0.44** | −0.38 | −0.14 |
| London (2007-05) | first | +0.37 | +0.38 | +0.27 | −0.12 | — |
| | second | −0.15 | −0.20 | −0.25 | −0.36 | −0.47 |
| Asia (1998-05) | first | +0.15 | +0.38 | +0.38 | +0.56 | −0.86 |
| | second | −0.03 | +0.10 | +0.04 | −0.20 | −0.14 |
| Turkey (2012-02) | first | +0.25 | −0.05 | −0.28 | −0.87 | — |
| | second | −0.24 | −0.26 | −0.34 | −0.30 | −0.66 |

Every wrong-signed cell is in a **first half**. The positive correlations come
from long secular bull runs — Japan 1970–89, UK 1988–2007 — where price sat above
trend for a decade and kept rising. In the second half of all four markets the
sign is negative at 84m and 120m.

Over a **common calendar period** every cell turns negative:

ρ(z, fwd24), 2005-01 onward:

| market | 36 | 60 | 84 | 120 | 240 |
|---|---|---|---|---|---|
| New York | −0.29 | −0.43 | **−0.58** | −0.54 | −0.00 |
| London | −0.07 | −0.12 | −0.20 | −0.42 | **−0.47** |
| Asia | −0.11 | +0.05 | +0.00 | **−0.30** | −0.48 |
| Turkey | −0.19 | −0.17 | −0.37 | −0.38 | −0.66¹ |
| **pooled** | −0.17 | −0.16 | −0.29 | **−0.41** | −0.35 |

¹ n=87, below the evidence threshold.

From 2010 onward the pooled figures are −0.31 / −0.35 / −0.28 / −0.35 / −0.49,
with the 240 column again resting on Turkey's 87 observations.

## 5. Asia is the weak market regardless of window

> **Superseded in part.** Asia is now evaluated from **1990 onward** (see the
> addendum at the end of this file). The full-sample figures below are what
> motivated that change and are kept as the evidence for it; the numbers in
> `results/` are regenerated against the shipped, restricted configuration.

Nikkei is ≈0 at 84m in every modern sample (+0.00 from 2005, −0.02 from 2010) and
wrong-signed across most of its full history. The one famous call — the 1989-12
entry at the actual peak — is a single event, and single events are not evidence.
Whatever window is chosen, **Asia should not be presented as carrying the same
weight as New York.**

## 6. Calibration

Flag rate ÷ nominal 2.28%:

| window | New York | London | Asia | Turkey |
|---|---|---|---|---|
| 60 | 1.5 | 2.3 | 3.1 | 1.5 |
| 84 | **1.9** | 2.8 | 4.6 | 1.8 |
| 120 | 2.6 | 2.4 | 4.9 | 2.7 |
| 240 | 6.4 | 0.0 | 3.8 | 0.0 |

84m and 120m are the only windows well-behaved on all four. Note even 2–5× is
expected: z is highly autocorrelated, so a flagged *month* is not an independent
test, and the ratio overstates how often the model is "wrong".

## Conclusion

- **Drop 240m as the default.** It is wrong-signed and 6.4× over-firing on
  Nasdaq, and silent on two of four markets.
- **Drop ≤36m** as anything but a momentum curiosity.
- **84m and 120m are the defensible range.** 84m is clearly best for New York;
  120m is the only window in the top two for *all four* markets with adequate
  sample everywhere.
- The gap between 84 and 120 is inside the noise for three of the four markets.
  Do not read the third decimal.

**Recommended default: 120m**, on cross-market consistency, with 84m offered as
New York's per-market default if per-market defaults are acceptable at all.

## What this study does not establish

- **The effective sample is tiny.** Independent episodes at 84m: New York 6,
  London 7, Asia 13, Turkey 3. Every conditional statistic here rests on single-
  digit events. The block-bootstrap CIs account for overlap but not for the fact
  that a handful of business cycles is a small sample of history.
- **This is in-sample window selection.** Eight windows were compared on the same
  data used to judge them. The subsample and common-period tests are guards
  against the worst of it, not a substitute for out-of-sample data.
- **No forecast claim.** A negative ρ says elevated z has tended to precede weaker
  real returns. It is not a timing signal and it is not tradeable as-is.
- **Real returns exclude dividends.** Price indices only, so the level of every
  forward return is understated; the flagged-minus-normal *difference* is
  unaffected.


---

## Addendum, 2026-09-22 — Asia restricted to 1990+

Acting on §5 and FILTER-STUDY.md §3, the Nikkei is now evaluated from 1990-01.
The cut happens **before the trend is fitted**, not after. Trimming only the
display would leave the 1970–89 era setting the trend for readings taken in the
1990s — the era the restriction exists to remove. The cost is that readings begin
ten years after the cut (1999-12 at the 120m window) instead of in 1990.

Effect on ρ(z, fwd 24m real return) at the 120m window:

| variant | ρ | z observations | z begins |
|---|---|---|---|
| full history (previous) | **+0.159** | 561 | 1980-01 |
| display-only trim, fit on full history | −0.066 | 416 | 1990-01 |
| **fit on 1990+ only (shipped)** | **−0.174** | 297 | 1999-12 |

The restriction removes the wrong sign. It does **not** make Asia comparable to
the others: at the shipped window it remains the weakest of the four
(New York −0.32, Turkey −0.38, London −0.26, Asia −0.17), and at 12–84m it is
still ≈0. Both facts are stated on the market itself in the UI.

This choice was made **after** seeing the result. That is a real weakness — it is
not an out-of-sample finding, and it should not be presented as one. It is
labelled in the app and recorded here rather than absorbed silently.

Windows of 240m and 360m now look strongly negative on Asia (−0.40, −0.61), but
at a 1990 start they leave too little history to act on and 240m remains
wrong-signed on New York, so the 120m default is unchanged.
