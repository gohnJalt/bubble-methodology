"""Bubble methodology: CPI-deflated log real price vs its own rolling trend.

Ported from draft/bubble-methodology.ipynb. See DESIGN.md section 2.
"""
import numpy as np
import pandas as pd
from scipy import stats

CARRY_MAX = 3   # months the last published CPI may be carried forward (see price_index)


def price_index(price, cpi, warn=True):
    """
    Deflate a price series by CPI and return a monthly log real price index.

    price (df/series): daily nominal price.
    cpi   (df/series): CPI, stamped at month start (FRED CPIAUCSL convention).

    Returns a frame indexed by month end with columns nom, cpi, real, p (= log real)
    and prov. The index is contiguous monthly, which trend_z relies on.

    The series runs to the current month. CPI publishes a month or two behind price,
    and the current month is still trading, so the last row or two are PROVISIONAL and
    `prov` marks them:

    - CPI past its last published month is carried forward, up to CARRY_MAX months.
      Those months are deflated as if inflation were zero, which overstates real price
      by exactly the inflation that has not printed yet -- negligible at 2%/yr, not
      negligible in Turkey. Past CARRY_MAX the month is dropped instead: a dead CPI
      feed must not quietly turn a nominal rally into a real one (London's FRED CPI
      died in 2025-03, so this is an observed failure mode, not a hypothetical).
    - The current month's mean is a partial month, over however many sessions have
      traded so far. It is a noisier estimate of the same quantity, not a different
      one, and it uses no information from after month t.

    Nothing here looks ahead: every value was computable at the month it is stamped on.

    CPI base year is irrelevant: a constant scale on cpi is an additive constant
    on p, which trend_z detrends away. Do not renormalise bases across markets.
    """
    price, cpi = price.squeeze(), cpi.squeeze()

    px = price.resample('ME').agg("mean")
    partial = price.index.max() < px.index.max()   # the current month is still running
    cp = cpi.resample('ME').last()

    months = pd.period_range(max(px.index.min(), cp.index.min()).to_period('M'),
                             px.index.max().to_period('M'),
                             freq='M').to_timestamp('M')
    px, cp = px.reindex(months), cp.reindex(months)

    # Oct-2025 is genuinely absent from CPIAUCSL (never published). Dropping an interior
    # hole would silently shorten the time axis every rolling window sees, so fill it.
    filled = cp.interpolate(limit_area='inside')
    holes = cp.index[cp.isna() & filled.notna()]
    if len(holes) and warn:
        print("CPI missing:", ", ".join(holes.strftime('%Y-%m')), "-> interpolated")
    tail = filled.isna()                           # price has printed, CPI has not yet
    cp = filled.ffill(limit=CARRY_MAX)

    df = pd.concat([px.rename("nom"), cp.rename("cpi")], axis=1).dropna()
    df["real"] = df["nom"] / df["cpi"]
    df["p"] = np.log(df["real"])
    df["prov"] = tail.reindex(df.index, fill_value=False)
    if partial and len(df):
        df.loc[df.index[-1], "prov"] = True
    return df


def zcrit(window, sigma=2.0):
    """Threshold carrying the same tail area as `sigma` on a normal, at this window length.

    z is t-distributed with window-3 df, so a flat 2.0 is a slightly looser test on
    short windows. Use this when comparing windows against each other.
    """
    return float(stats.t.isf(stats.norm.sf(sigma), window - 3))


def trend_z(p, window=240, k=2.0):
    """Rolling detrend of monthly log real price -> trend, sd, z, upper.

    For each month t, fit a linear trend to the `window` months ENDING at t
    (no look-ahead), then measure t against that trend with t itself deleted
    from the fit. trend/sd/upper are therefore what the rest of the window
    implies for month t, and z is t's deviation in units of its own standard
    error -- distributed t(window-3) under a trend-stationary null.

    Deleting t matters because the endpoint of a linear fit is its highest
    leverage point: an in-sample residual there is shrunk by sqrt(1-h), which
    is 16% at window=12 and under 1% at window=240. Left uncorrected that
    makes z incomparable across window lengths.
    """
    n, v = window, p.to_numpy(float)
    if n < 5:
        raise ValueError("window must be >= 5")
    step = p.index.to_period('M')
    if len(step) and (np.diff(step.astype('int64')) != 1).any():
        raise ValueError("p must be contiguous monthly; gaps break the time axis")

    tc = np.arange(n) - (n - 1) / 2          # centred time, so intercept = window mean
    denom = (tc ** 2).sum()
    h = 1 / n + tc[-1] ** 2 / denom          # leverage of the last point in the window

    Y = np.lib.stride_tricks.sliding_window_view(v, n)
    slope = (Y @ tc) / denom
    fit = Y.mean(1)[:, None] + slope[:, None] * tc
    r = Y - fit
    r_end = r[:, -1]

    # scale from the window with month t deleted -> not inflated by the point being tested
    s2 = np.maximum(((r ** 2).sum(1) - r_end ** 2 / (1 - h)) / (n - 3), 0.0)
    sd = np.sqrt(s2) / np.sqrt(1 - h)        # std error of the out-of-sample deviation
    trend = (fit[:, -1] - h * Y[:, -1]) / (1 - h)     # trend excluding month t

    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sd > 0, (Y[:, -1] - trend) / sd, np.nan)

    return pd.DataFrame({"trend": trend, "sd": sd, "z": z, "upper": trend + k * sd},
                        index=p.index[n - 1:])


def entries(z, crit):
    """Months where the bubble state flips off->on. An episode is one event, not N."""
    bub = z > crit
    return z.index[bub & ~bub.shift(1, fill_value=False)]


def score(p, window=240):
    """The whole model for one market: trend_z at its own threshold, plus entries."""
    k = zcrit(window)
    tz = trend_z(p, window, k=k)
    return tz, k, entries(tz["z"], k)


def _selfcheck():
    idx = pd.period_range("1990-01", periods=400, freq="M").to_timestamp("M")

    # a clean linear trend is predicted exactly by the window that excludes it.
    # (z itself is meaningless here: sd is float noise, so z is a ratio of two
    # ~1e-16 numbers. The deviation is what carries the claim.)
    flat = pd.Series(np.arange(400) * 0.01 + 5.0, index=idx)
    tz = trend_z(flat, 120, k=zcrit(120))
    dev = (flat.reindex(tz.index) - tz["trend"]).abs().max()
    assert dev < 1e-9, dev

    # a spike is caught at the spike, and dominates. Note it is NOT the only entry:
    # at zcrit(120) ~= 2.02, pure noise exceeds the threshold ~2% of months, so a
    # 400-month sample throws several false entries. That is the model behaving as
    # specified, not a bug -- see DESIGN.md section 6 on multiple testing.
    rng = np.random.default_rng(0)
    noisy = flat + rng.normal(0, 0.02, 400)
    noisy.iloc[300] += 1.0
    tz, k, ent = score(noisy, 120)
    assert tz["z"].idxmax() == idx[300], tz["z"].idxmax()
    assert idx[300] in set(ent), list(ent)
    others = tz["z"].drop(idx[300]).max()
    assert tz["z"].max() > 3 * others, (tz["z"].max(), others)

    # threshold tightens on short windows, converges to 2 on long ones
    ks = [zcrit(w) for w in (12, 24, 60, 120, 240, 360)]
    assert ks == sorted(ks, reverse=True), ks
    assert ks[0] > 2.3 and abs(ks[-1] - 2.0) < 0.02, ks

    # deleting the tested point matters: uncorrected z would be ~16% smaller at w=12
    assert trend_z(noisy, 12, k=2.0)["sd"].mean() > 0

    # a gap in the monthly index must raise, not silently mis-index
    gapped = noisy.drop(idx[200])
    try:
        trend_z(gapped, 60)
        raise AssertionError("gap in index did not raise")
    except ValueError:
        pass

    # price_index: CPI base is irrelevant, p shifts by a constant only
    px = pd.Series(np.exp(np.linspace(2, 6, 4000)),
                   index=pd.date_range("1990-01-01", periods=4000, freq="B"))
    cpi = pd.Series(np.linspace(100, 300, 400),
                    index=pd.period_range("1990-01", periods=400, freq="M").to_timestamp())
    a = price_index(px, cpi, warn=False)
    b = price_index(px, cpi * 7.3, warn=False)
    assert np.allclose(a["p"] - b["p"], (a["p"] - b["p"]).iloc[0])
    assert (a.index.to_period("M").astype("int64").diff().dropna() == 1).all()

    # an interior CPI hole is filled, not dropped
    holed = cpi.copy()
    holed.iloc[200] = np.nan
    assert len(price_index(px, holed, warn=False)) == len(a)

    # CPI lagging price: the index still runs to the last priced month, the carried
    # months are flagged, and the carry is bounded so a dead feed cannot run forever.
    # cpi2 ends exactly where px does, so trimming it creates a real publication lag.
    pm = pd.period_range("1990-01", px.index.max().to_period("M"), freq="M")
    cpi2 = pd.Series(np.linspace(100, 300, len(pm)), index=pm.to_timestamp())
    base = price_index(px, cpi2, warn=False)
    lag2 = price_index(px, cpi2.iloc[:-2], warn=False)
    assert lag2.index.max() == base.index.max(), (lag2.index.max(), base.index.max())
    assert len(lag2) == len(base)                             # no month lost to the lag
    assert lag2["prov"].iloc[-2:].all() and not lag2["prov"].iloc[:-2].any()
    assert (lag2["cpi"].iloc[-3:] == cpi2.iloc[-3]).all()     # last published, held flat
    dead = price_index(px, cpi2.iloc[:-24], warn=False)
    assert len(dead) == len(base) - 24 + CARRY_MAX, len(dead)  # dropped past the cap

    # a still-running current month is kept and flagged, not silently dropped
    cut = px.index[px.index.to_period("M") == pm[-3]][8]      # mid-month cutoff
    lv = price_index(px.loc[:cut], cpi2, warn=False)
    assert lv.index.max().to_period("M") == pm[-3], lv.index.max()
    assert bool(lv["prov"].iloc[-1]) and not lv["prov"].iloc[:-1].any()
    assert np.isclose(lv["nom"].iloc[-1], px.loc[pm[-3].start_time:cut].mean())

    print("bubble.py selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
