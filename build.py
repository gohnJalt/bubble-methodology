"""Static site build: run the model for every market and window, write site/data.json.

The site on Cloudflare Pages is plain HTML reading this file; all the math stays
here in Python. A daily GitHub Action reruns this and redeploys (.github/workflows).

Run: python build.py        (then open site/ with any static server)
"""
import json
import os
import time

import numpy as np
import pandas as pd

import data

WINDOWS = (12, 24, 36, 60, 84, 120, 240, 360)
OUT = os.path.join(data.HERE, "site", "data.json")


def arr(s, nd):
    return [None if not np.isfinite(v) else round(float(v), nd) for v in s]


def months(idx):
    return [f"{t:%Y-%m}" for t in idx]


def episodes(flag):
    out, run = [], None
    for t, on in flag.items():
        if on and run is None:
            run = t
        elif not on and run is not None:
            out.append((run, t)); run = None
    if run is not None:
        out.append((run, flag.index[-1]))
    return out


def entry_table(m):
    """Every episode: entry month, z at entry, length, drawdown from the episode's
    real peak to the lowest point of the following 24 months."""
    tz, crit, real = m["tz"], m["crit"], m["df"]["real"]
    rows = []
    for s, e in episodes(tz["z"] > crit):
        peak = real.loc[s:e].max()
        after = real.loc[e:].head(25)
        dd = (after.min() / peak - 1) * 100 if len(after) and peak == peak else np.nan
        rows.append(dict(entered=f"{s:%Y-%m}", z=round(float(tz["z"].loc[s]), 2),
                         months=len(tz.loc[s:e]),
                         dd=None if dd != dd else round(float(dd), 1)))
    return rows


def market(key):
    m = data.load(key)
    df = m["df"]
    out = dict({k: m[k] for k in ("key", "name", "index", "ccy", "window", "start",
                                  "note", "weak")},
               months=months(df.index), p=arr(df["p"], 4),
               prov=bool(df["prov"].iloc[-1]), windows={},
               overlay=dict(months=months(m["overlay"].index), v=arr(m["overlay"], 3)),
               comps={k: dict(months=months(s.index), v=arr(s, 3))
                      for k, s in m["comps"].items()})
    for w in WINDOWS:
        try:
            mw = m if w == m["window"] else data.load(key, w)
        except ValueError:   # window longer than the history: nothing to score
            continue
        tz = mw["tz"].reindex(df.index)
        out["windows"][w] = dict(crit=round(mw["crit"], 4), z=arr(tz["z"], 3),
                                 trend=arr(tz["trend"], 4), upper=arr(tz["upper"], 4),
                                 episodes=entry_table(mw))
    return out


def build():
    markets = {}
    for key in data.MARKETS:
        try:
            markets[key] = market(key)
        except Exception as e:   # one dead API renders as an error card, not a failed build
            markets[key] = dict(key=key, index=data.MARKETS[key]["index"],
                                error=f"{type(e).__name__}: {e}")
    return dict(built=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                stale=data.stale(), markets=markets)


def _selfcheck():
    f = pd.Series([False, True, True, False, True],
                  index=pd.period_range("2000-01", periods=5, freq="M").to_timestamp("M"))
    ep = episodes(f)
    assert [(f"{a:%m}", f"{b:%m}") for a, b in ep] == [("02", "04"), ("05", "05")], ep
    assert arr([1.23456, float("nan")], 2) == [1.23, None]


if __name__ == "__main__":
    _selfcheck()
    out = build()
    ok = [k for k, v in out["markets"].items() if "error" not in v]
    if not ok:
        raise SystemExit("no market could be built; refusing to publish an empty site")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB): {', '.join(ok)}",
          "| stale:", out["stale"] or "none")
