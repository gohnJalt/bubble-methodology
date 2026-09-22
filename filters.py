"""Causal filters, and whether any of them rescues the Asia signal.

THE CONSTRAINT THAT DECIDES EVERYTHING HERE: the textbook HP filter is two-sided.
Its trend at month t is fitted using months after t. Detrending with it and then
correlating against forward returns leaks the future into the signal and produces
a spectacular, meaningless result. So every filter here is ONE-SIDED: the value
at month t is computed from months <= t only, exactly like trend_z. `_selfcheck`
asserts this directly by mutating the future and checking the past does not move.

Two distinct hypotheses about why Asia fails, tested separately:

  A. "the price is noisy"      -> smooth p, then run the ordinary trend_z on it.
  B. "a line is the wrong trend" -> replace the rolling linear trend with an HP
                                  trend and standardise the cycle.

Run: .venv/bin/python filters.py
"""
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spl
from scipy import stats

import bubble
import data
import evaluate as E

LAMBDAS = (1600, 14400, 129600)   # monthly HP: 14400 is the Ravn-Uhlig convention
STD_WIN = 120                     # trailing window for standardising an HP cycle


def hp_trend(y, lam):
    """Two-sided HP trend. Used ONLY as the engine inside hp_onesided."""
    n = len(y)
    if n < 5:
        return np.full(n, np.nan)
    e = np.ones(n - 2)
    # second-difference operator, shape (n-2, n): row i is [.. 1, -2, 1 ..] at i, i+1, i+2.
    # sp.diags (not spdiags) takes each diagonal as its own array of the right length.
    D = sp.diags([e, -2 * e, e], offsets=[0, 1, 2], shape=(n - 2, n))
    A = (sp.eye(n) + lam * (D.T @ D)).tocsc()
    return spl.spsolve(A, y)


def hp_onesided(p, lam, min_obs=60):
    """Causal HP trend: at each t, fit on p[:t+1] and keep only the last point.

    O(n) solves of a banded system. Slower than the two-sided filter and that is
    the point -- the two-sided one is unusable here.
    """
    v = p.to_numpy(float)
    out = np.full(len(v), np.nan)
    for t in range(min_obs - 1, len(v)):
        out[t] = hp_trend(v[:t + 1], lam)[-1]
    return pd.Series(out, index=p.index)


def causal_z(cycle, win=STD_WIN, min_obs=60):
    """Standardise a cycle by its own TRAILING sd. No future information."""
    sd = cycle.rolling(win, min_periods=min_obs).std()
    return (cycle / sd.where(sd > 0)).rename("z")


def signal(p, kind, window=120):
    """-> a z-like series for the given configuration, or None if unusable."""
    if kind == "baseline":
        return bubble.score(p, window)[0]["z"]
    if kind.startswith("ma"):                       # hypothesis A: smooth, then trend_z
        k = int(kind[2:])
        sm = p.rolling(k, min_periods=k).mean().dropna()
        return bubble.score(sm, window)[0]["z"]
    if kind.startswith("hp"):                       # hypothesis B: HP as the trend
        lam = int(kind[2:])
        tr = hp_onesided(p, lam)
        return causal_z((p - tr).dropna())
    raise ValueError(kind)


def rho(sig, real, h=24, start=None):
    """Spearman(signal, forward h-month real return). Same metric as the window study."""
    sig = sig.dropna()
    fr = E.fwd_logret(real.reindex(sig.index), h)
    d = pd.DataFrame({"s": sig, "f": fr}).dropna()
    if start is not None:
        d = d[d.index >= start]
    if len(d) < 40:
        return np.nan, len(d)
    return float(stats.spearmanr(d["s"], d["f"]).statistic), len(d)


def run():
    kinds = ["baseline", "ma3", "ma6", "ma12"] + [f"hp{l}" for l in LAMBDAS]
    rows = []
    for key in data.MARKETS:
        m = data.load(key)
        p, real, w = m["df"]["p"], m["df"]["real"], m["window"]
        mid = p.index[len(p) // 2]
        for kind in kinds:
            try:
                s = signal(p, kind, w)
            except Exception as e:
                print(f"  {key}/{kind}: {type(e).__name__}: {e}")
                continue
            full, n = rho(s, real)
            mod, n05 = rho(s, real, start="2005-01")
            sec, nsec = rho(s.loc[s.index >= mid], real)
            rows.append(dict(market=key, filter=kind, window=w, n=n,
                             rho_full=full, rho_2005=mod, rho_2nd_half=sec,
                             rho_12=rho(s, real, 12)[0], rho_36=rho(s, real, 36)[0]))
    return pd.DataFrame(rows)


def _selfcheck():
    rng = np.random.default_rng(0)
    idx = pd.period_range("1990-01", periods=200, freq="M").to_timestamp("M")
    y = pd.Series(np.linspace(0, 2, 200) + rng.normal(0, 0.1, 200), index=idx)

    # HP endpoints: tiny lambda tracks the data, huge lambda approaches a line
    assert np.allclose(hp_trend(y.to_numpy(), 1e-8), y.to_numpy(), atol=1e-4)
    big = hp_trend(y.to_numpy(), 1e10)
    line = np.polyval(np.polyfit(np.arange(200), y.to_numpy(), 1), np.arange(200))
    assert np.abs(big - line).max() < 1e-2, np.abs(big - line).max()
    # and the penalty must actually bite: more lambda = smoother trend
    rough = [np.abs(np.diff(hp_trend(y.to_numpy(), l), 2)).sum() for l in (1600, 129600)]
    assert rough[0] > rough[1] * 5, rough

    # THE ONE THAT MATTERS: the one-sided filter must not see the future.
    a = hp_onesided(y, 14400)
    y2 = y.copy()
    y2.iloc[150:] += 10.0                      # wreck the future
    b = hp_onesided(y2, 14400)
    assert np.allclose(a.iloc[:150].dropna(), b.iloc[:150].dropna()), "look-ahead leak"
    # and the two-sided one must fail that same test, or the test proves nothing
    t1 = hp_trend(y.to_numpy(), 14400)
    t2 = hp_trend(y2.to_numpy(), 14400)
    assert not np.allclose(t1[:150], t2[:150]), "two-sided HP should leak; test is broken"

    # causal_z uses only trailing information
    c = causal_z(y)
    y3 = y.copy(); y3.iloc[180:] *= 5
    assert np.allclose(c.iloc[:180].dropna(), causal_z(y3).iloc[:180].dropna())
    print("filters.py selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
    df = run()
    import os
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(out, exist_ok=True)
    df.to_csv(os.path.join(out, "filter_study.csv"), index=False)
    for col in ("rho_full", "rho_2005", "rho_2nd_half", "rho_12", "rho_36"):
        df.pivot(index="filter", columns="market", values=col).round(3).to_csv(
            os.path.join(out, f"filter_{col}.csv"))
    pd.set_option("display.width", 250)
    for col, label in [("rho_full", "full sample"), ("rho_2005", "2005 onward"),
                       ("rho_2nd_half", "second half")]:
        print(f"\n=== rho(signal, fwd 24m real return) — {label} ===")
        print(df.pivot(index="filter", columns="market", values=col)
                .reindex(["baseline", "ma3", "ma6", "ma12",
                          *(f"hp{l}" for l in LAMBDAS)]).round(3))
