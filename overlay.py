"""Macro overlay score. See DESIGN.md section 2.6.

A SEPARATE signal. It never enters z, never changes the bubble state, and is
never averaged with z into one number. Two signals, shown side by side.
"""
import numpy as np
import pandas as pd

WIN, MIN_OBS = 120, 60          # trailing 10y z-score, needs 5y before it says anything
# higher score = looser / more bubble-supportive
SIGN = {"real_rate": -1, "credit": +1, "curve": +1}
BANDS = [(-1.0, "tight"), (1.0, "neutral"), (np.inf, "loose")]


def _monthly(s):
    return s.resample("ME").last()


def _tz(s):
    """z against own trailing window, excluding nothing -- this is context, not a test."""
    r = s.rolling(WIN, min_periods=MIN_OBS)
    sd = r.std()
    return ((s - r.mean()) / sd.where(sd > 0)).rename(s.name)


def components(cpi, policy=None, credit=None, curve=None):
    """Raw monthly component values, oriented so higher = looser.

    cpi is the same CPI series used for the deflator; real rate needs its YoY.
    Any component may be None -- it is simply absent, never imputed as zero.
    """
    out = {}
    if policy is not None and cpi is not None:
        c = _monthly(cpi)
        out["real_rate"] = (_monthly(policy) - c.pct_change(12) * 100).dropna()
    if credit is not None:
        out["credit"] = (_monthly(credit).pct_change(12) * 100).dropna()
    if curve is not None:
        out["curve"] = _monthly(curve).dropna()
    return {k: v.rename(k) for k, v in out.items() if not v.empty}


def score(comps):
    """-> (score series, per-component z frame). Mean of whatever is present.

    A missing component drops out of the mean. It is NOT imputed as zero: a
    series we do not have is unknown, not neutral.
    """
    if not comps:
        return pd.Series(dtype=float), pd.DataFrame()
    zs = pd.concat([_tz(v) * SIGN[k] for k, v in comps.items()], axis=1)
    return zs.mean(axis=1, skipna=True).rename("overlay"), zs


def band(x):
    if x is None or not np.isfinite(x):
        return "n/a"
    return next(label for hi, label in BANDS if x < hi)


def _selfcheck():
    idx = pd.period_range("1990-01", periods=300, freq="M").to_timestamp("M")
    rng = np.random.default_rng(1)

    cpi = pd.Series(100 * 1.002 ** np.arange(300), index=idx, name="cpi")
    policy = pd.Series(4 + rng.normal(0, 0.5, 300), index=idx, name="policy")
    credit = pd.Series(100 * 1.004 ** np.arange(300), index=idx, name="credit")

    c = components(cpi, policy=policy, credit=credit, curve=None)
    assert set(c) == {"real_rate", "credit"}, set(c)

    s, zs = score(c)
    assert list(zs.columns) == ["real_rate", "credit"]
    # cutting a policy rate (real rate falls) must RAISE the score, not lower it
    loose = policy.copy()
    loose.iloc[-24:] -= 5
    s2, _ = score(components(cpi, policy=loose, credit=credit))
    assert s2.iloc[-1] > s.iloc[-1], (s2.iloc[-1], s.iloc[-1])

    # a missing component drops out of the mean rather than dragging it to zero
    one, _ = score(components(cpi, policy=policy))
    assert one.notna().any() and len(score(components(cpi))[0]) == 0

    # nothing is said before MIN_OBS observations
    assert s.iloc[:MIN_OBS - 1].isna().all()

    assert band(-2) == "tight" and band(0) == "neutral" and band(2) == "loose"
    assert band(np.nan) == "n/a"
    print("overlay.py selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
