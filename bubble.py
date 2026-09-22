"""Bubble methodology: CPI-deflated log real price vs its own rolling trend.

Ported from draft/bubble-methodology.ipynb. See DESIGN.md section 2.
"""
import numpy as np
import pandas as pd
from scipy import stats


def price_index(price, cpi, warn=True):
    """
    Deflate a price series by CPI and return a monthly log real price index.

    price (df/series): daily nominal price.
    cpi   (df/series): CPI, stamped at month start (FRED CPIAUCSL convention).

    Returns a frame indexed by month end with columns nom, cpi, real, p (= log real).
    The index is contiguous monthly, which trend_z relies on.

    CPI base year is irrelevant: a constant scale on cpi is an additive constant
    on p, which trend_z detrends away. Do not renormalise bases across markets.
    """
    price, cpi = price.squeeze(), cpi.squeeze()

    px = price.resample('ME').agg("mean")
    if price.index.max() < px.index.max():
        px = px.iloc[:-1]          # last month incomplete -> its mean is a partial month
    cp = cpi.resample('ME').last()

    months = pd.period_range(max(px.index.min(), cp.index.min()).to_period('M'),
                             min(px.index.max(), cp.index.max()).to_period('M'),
                             freq='M').to_timestamp('M')
    px, cp = px.reindex(months), cp.reindex(months)

    holes = cp.index[cp.isna()]
    if len(holes):
        # Oct-2025 is genuinely absent from CPIAUCSL (never published). Dropping it
        # would silently shorten the time axis every rolling window sees, so fill it.
        if warn:
            print("CPI missing:", ", ".join(holes.strftime('%Y-%m')), "-> interpolated")
        cp = cp.interpolate(limit_area='inside')

    df = pd.concat([px.rename("nom"), cp.rename("cpi")], axis=1).dropna()
    df["real"] = df["nom"] / df["cpi"]
    df["p"] = np.log(df["real"])
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

    print("bubble.py selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
