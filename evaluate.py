"""Window-length study: is the bubble flag informative, and at which window?

Criteria are fixed here BEFORE looking at results (DESIGN.md 2.5). Two of the
four are threshold-free, so they cannot be gamed by moving the threshold.

  1. calibration  -- share of months flagged vs the 2.3% the 2-sigma test claims.
                     Threshold-dependent but nominal-anchored: a window whose
                     flag fires 6x its own stated rate is mis-sized, full stop.
  2. rank-info    -- Spearman(z_t, forward real return). THRESHOLD-FREE. If high
                     z carries no information about what happens next, nothing
                     downstream matters. Should be NEGATIVE to be useful.
  3. conditional  -- forward real return when flagged minus when not, with a
                     block-bootstrap CI (overlapping windows, so no p-values).
  4. consistency  -- does the same window win in all four markets? A window that
                     only works on Nasdaq is a curve fit, not a finding.

Run: .venv/bin/python evaluate.py
"""
import os

import numpy as np
import pandas as pd
from scipy import stats

import bubble
import data

WINDOWS = (12, 24, 36, 60, 84, 120, 240, 360)
HORIZONS = (12, 24, 36)
MIN_Z = 120          # fewer z observations than this and the row is not evidence
MIN_FLAGS = 12       # fewer flagged months and conditional means are noise
NOMINAL = float(stats.norm.sf(2.0))   # 0.0228, the rate the test claims


def fwd_logret(real, h):
    """Log real return over the next h months. NaN in the last h months."""
    return np.log(real.shift(-h) / real)


def fwd_trough(real, h):
    """Worst drawdown from today's level over the next h months, as a fraction."""
    lead = real.shift(-1)
    m = lead[::-1].rolling(h, min_periods=h).min()[::-1]
    return m / real - 1.0


def block_boot(x, y, flag, n=2000, block=24, seed=0):
    """CI for mean(y|flag) - mean(y|~flag) under circular block resampling.

    Forward windows overlap, so observations are massively autocorrelated and
    ordinary standard errors are meaningless. Circular blocks of `block` months
    preserve that dependence. This is a crude interval, not a p-value.
    """
    rng = np.random.default_rng(seed)
    ok = np.isfinite(y) & np.isfinite(flag)
    y, flag = y[ok], flag[ok].astype(bool)
    N = len(y)
    if N < block * 4 or flag.sum() < MIN_FLAGS or (~flag).sum() < MIN_FLAGS:
        return np.nan, np.nan
    nb = int(np.ceil(N / block))
    out = []
    for _ in range(n):
        starts = rng.integers(0, N, nb)
        idx = (starts[:, None] + np.arange(block)) % N
        idx = idx.ravel()[:N]
        yy, ff = y[idx], flag[idx]
        if ff.sum() < 3 or (~ff).sum() < 3:
            continue
        out.append(yy[ff].mean() - yy[~ff].mean())
    if len(out) < 100:
        return np.nan, np.nan
    return float(np.percentile(out, 5)), float(np.percentile(out, 95))


def episodes(flag):
    runs, start = [], None
    for t, on in flag.items():
        if on and start is None:
            start = t
        elif not on and start is not None:
            runs.append((start, t)); start = None
    if start is not None:
        runs.append((start, flag.index[-1]))
    return runs


def evaluate(key, window, df):
    p, real = df["p"], df["real"]
    if len(p) < window + 30:      # not enough history to produce usable z
        return None
    tz, crit, ent = bubble.score(p, window)
    z = tz["z"].dropna()
    if len(z) < 30:
        return None
    real_z = real.reindex(z.index)
    flag = (z > crit)

    row = dict(market=key, window=window, n_z=len(z), crit=round(crit, 2),
               flag_pct=100 * flag.mean(), n_entries=len(ent),
               ratio_vs_nominal=flag.mean() / NOMINAL)
    durs = [len(z.loc[a:b]) for a, b in episodes(flag)]
    row["median_episode_m"] = float(np.median(durs)) if durs else np.nan

    for h in HORIZONS:
        fr = fwd_logret(real_z, h)
        ok = np.isfinite(fr)
        # threshold-free: does z rank forward outcomes at all?
        if ok.sum() > 30:
            rho = stats.spearmanr(z[ok], fr[ok]).statistic
        else:
            rho = np.nan
        row[f"rho_{h}"] = rho
        # conditional means, annualised for readability
        f, nf = flag & ok, (~flag) & ok
        if f.sum() >= MIN_FLAGS and nf.sum() >= MIN_FLAGS:
            a = 12 / h
            row[f"ret_flag_{h}"] = 100 * a * fr[f].mean()
            row[f"ret_norm_{h}"] = 100 * a * fr[nf].mean()
            row[f"diff_{h}"] = row[f"ret_flag_{h}"] - row[f"ret_norm_{h}"]
            if h == 24:
                lo, hi = block_boot(z.values, fr.values, flag.values)
                row["diff_24_lo"] = np.nan if lo != lo else 100 * 0.5 * lo
                row["diff_24_hi"] = np.nan if hi != hi else 100 * 0.5 * hi
        else:
            for k in (f"ret_flag_{h}", f"ret_norm_{h}", f"diff_{h}"):
                row[k] = np.nan

    dd = fwd_trough(real_z, 24)
    ok = np.isfinite(dd)
    f = flag & ok
    row["dd24_flag"] = 100 * dd[f].mean() if f.sum() >= MIN_FLAGS else np.nan
    row["dd24_base"] = 100 * dd[ok].mean() if ok.sum() > 30 else np.nan
    return row


def run():
    frames = {}
    for key in data.MARKETS:
        try:
            m = data.load(key, 240)
            frames[key] = m["df"]
        except Exception as e:
            print(f"skip {key}: {type(e).__name__}: {e}")
    rows = [r for key, df in frames.items() for w in WINDOWS
            if (r := evaluate(key, w, df)) is not None]
    return pd.DataFrame(rows)


def _selfcheck():
    idx = pd.period_range("1990-01", periods=200, freq="M").to_timestamp("M")
    real = pd.Series(np.arange(200, dtype=float) + 100, index=idx)

    # forward return of a known series
    fr = fwd_logret(real, 12)
    assert np.isclose(fr.iloc[0], np.log(112 / 100)), fr.iloc[0]
    assert fr.iloc[-12:].isna().all()

    # a monotonically rising series never draws down
    assert (fwd_trough(real, 12).dropna() > 0).all()
    # a falling one draws down to its h-month-ahead low
    fall = pd.Series(np.linspace(200, 100, 200), index=idx)
    tr = fwd_trough(fall, 12)
    assert np.isclose(tr.iloc[0], fall.iloc[12] / fall.iloc[0] - 1), tr.iloc[0]

    # bootstrap recovers a planted difference
    rng = np.random.default_rng(0)
    y = rng.normal(0, 1, 600); flag = np.zeros(600, bool); flag[200:300] = True
    y[flag] -= 2.0
    lo, hi = block_boot(np.zeros(600), y, flag, n=500)
    assert lo < -2.0 < hi, (lo, hi)
    print("evaluate.py selfcheck ok")


# --------------------------------------------------------------- table dumps
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _rho(key, w, h, mask=None, start=None):
    """Uses the shipped market (data.load), so the study measures what the app shows:
    the trend fits on all available history, the reported range may be shorter."""
    try:
        m = data.load(key, w)
    except Exception:
        return np.nan
    z = m["tz"]["z"].dropna()
    fr = fwd_logret(m["df"]["real"].reindex(z.index), h)
    ok = np.isfinite(fr)
    if mask is not None:
        ok &= mask(z.index)
    if start is not None:
        ok &= (z.index >= start)
    if ok.sum() < 40:
        return np.nan
    return float(stats.spearmanr(z[ok], fr[ok]).statistic)


def dump_all(frames):
    """Every table in results/, regenerated from source."""
    os.makedirs(OUT, exist_ok=True)
    def save(df, name, r=3):
        df.round(r).to_csv(os.path.join(OUT, name))
        return df

    # 1. rho by window x market, per horizon
    for h in HORIZONS + (60, 84, 120):
        t = pd.DataFrame({k: {w: _rho(k, w, h) for w in WINDOWS} for k in frames})
        save(t, f"rho_h{h}.csv")

    # 2. Nasdaq subsample stability
    tests = {"full": None,
             "excl_1995_2003": lambda i: ~((i >= "1995-01") & (i <= "2003-12")),
             "pre_1995": lambda i: i < "1995-01",
             "post_2003": lambda i: i >= "2004-01",
             "excl_2018_on": lambda i: i < "2018-01"}
    save(pd.DataFrame({n: {w: _rho("new_york", w, 24, m) for w in WINDOWS}
                       for n, m in tests.items()}), "nasdaq_subsamples.csv")

    # 3. split-half per market
    rows = {}
    for k, df in frames.items():
        mid = df["p"].index[len(df["p"]) // 2]
        for lab, m in [("first", lambda i, x=mid: i < x), ("second", lambda i, x=mid: i >= x)]:
            rows[(k, lab)] = {w: _rho(k, w, 24, m) for w in WINDOWS}
    save(pd.DataFrame(rows), "split_half.csv")

    # 4. common calendar period
    for start in ("2005-01", "2010-01"):
        save(pd.DataFrame({k: {w: _rho(k, w, 24, start=start) for w in WINDOWS}
                           for k in frames}), f"common_from_{start[:4]}.csv")

    # 5. Asia eras -- the reason the Nikkei signal fails
    eras = {"1970_1989_bull": ("1970-01", "1989-12"), "1990_2003_bust": ("1990-01", "2003-12"),
            "2004_2012": ("2004-01", "2012-12"), "2013_2026": ("2013-01", "2026-12")}
    save(pd.DataFrame({n: {h: _rho("asia", 120, h,
                                   lambda i, a=a, b=b: (i >= a) & (i <= b))
                           for h in (12, 24, 36, 60)} for n, (a, b) in eras.items()}),
         "asia_eras.csv")

    # 6. horizon sweep at each market's chosen default window
    save(pd.DataFrame({k: {f"h{h}": _rho(k, data.MARKETS[k]["window"], h)
                           for h in (12, 24, 36, 60, 84, 120)}
                       for k in frames}), "horizon_sweep.csv")


if __name__ == "__main__":
    _selfcheck()
    frames = {}
    for key in data.MARKETS:
        try:
            frames[key] = data.load(key)["df"]
        except Exception as e:
            print(f"skip {key}: {type(e).__name__}: {e}")
    os.makedirs(OUT, exist_ok=True)
    df = run()
    df.to_csv(os.path.join(OUT, "window_study.csv"), index=False)
    for name, col, r in [("calibration", "ratio_vs_nominal", 1),
                         ("flag_rate_pct", "flag_pct", 1),
                         ("n_entries", "n_entries", 0),
                         ("n_z", "n_z", 0),
                         ("conditional_diff_24", "diff_24", 1)]:
        df.pivot(index="window", columns="market", values=col).round(r).to_csv(
            os.path.join(OUT, f"{name}.csv"))
    dump_all(frames)
    pd.set_option("display.width", 250, "display.max_columns", 50)
    print("\n=== calibration (flag rate vs the 2.28% the test claims) ===")
    print(df.pivot(index="window", columns="market", values="ratio_vs_nominal").round(1))
    print("\n=== rank information: Spearman(z, forward 24m real return) ===")
    print(df.pivot(index="window", columns="market", values="rho_24").round(3))
    print(f"\nall tables -> {OUT}/")
