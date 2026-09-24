"""Fetch + parquet cache for prices, CPI and macro. See DESIGN.md section 3.

No scheduler, no database: read the parquet if it is fresh, else refetch and
rewrite. A failed refetch serves stale data and says so via stale().
"""
import os
import time
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cache")
os.makedirs(CACHE, exist_ok=True)


def _load_env(path=os.path.join(HERE, ".env")):
    """Minimal .env reader. Tolerates 'K = v', quotes and comments.

    Real env vars win, so a shell export still overrides the file.
    """
    try:
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


_load_env()

PRICE_DAYS, MACRO_DAYS = 1, 7   # monthly series change 12x/year; don't poll them hourly
_STALE = {}                     # name -> reason, for the UI banner


def stale():
    """{series: reason} for everything currently being served from a failed refresh."""
    return dict(_STALE)


def _cached(name, fetch, max_age_days):
    path = os.path.join(CACHE, f"{name.replace('/', '_')}.parquet")
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400
    if fresh:
        _STALE.pop(name, None)
        return pd.read_parquet(path)["v"]
    try:
        s = fetch().rename("v").dropna()
        if s.empty:
            raise ValueError("empty series")
        s.to_frame().to_parquet(path)
        _STALE.pop(name, None)
        return s
    except Exception as e:
        if os.path.exists(path):
            # degrade, don't crash: one dead API must not take the page down
            _STALE[name] = f"{type(e).__name__}: {e}"
            return pd.read_parquet(path)["v"]
        raise


def fred(series_id):
    """FRED via the public CSV endpoint. No API key needed."""
    def go():
        df = pd.read_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
                         index_col=0, parse_dates=True)
        return pd.to_numeric(df.iloc[:, 0], errors="coerce")
    return _cached(f"fred_{series_id}", go, MACRO_DAYS)


def prices(ticker):
    """Daily nominal close, full available history."""
    def go():
        import yfinance as yf
        df = yf.download(ticker, period="max", auto_adjust=False, progress=False)
        return df["Close"].squeeze()
    return _cached(f"px_{ticker}", go, PRICE_DAYS)


def ons(series_id, dataset="mm23"):
    """UK ONS time series via the public CSV generator. No API key.

    The old api.ons.gov.uk was decommissioned 2024-11-25; this CSV endpoint is
    what replaced it. Rows are "1988 JAN",value for monthly, plus annual and
    quarterly rows in the same file -- only the monthly ones are kept.
    """
    def go():
        import io
        import requests
        url = ("https://www.ons.gov.uk/generator?format=csv&uri=/economy/"
               f"inflationandpriceindices/timeseries/{series_id.lower()}/{dataset}")
        # ONS 403s the default urllib user-agent that pd.read_csv sends
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), header=None, names=["period", "v"], skiprows=1)
        m = df["period"].astype(str).str.match(r"^\d{4} [A-Z]{3}$")
        s = df[m].copy()
        idx = pd.to_datetime(s["period"], format="%Y %b")
        return pd.Series(pd.to_numeric(s["v"], errors="coerce").values, index=idx)
    return _cached(f"ons_{series_id}", go, MACRO_DAYS)


EVDS_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"


def evds(series_id, key=None):
    """CBRT EVDS monthly series. Needs EVDS_API_KEY.

    Endpoint shape is unusual and undocumented: params are appended to the base
    URL as a raw path string, NOT as a query string and NOT under a /service/evds
    subpath (the old evds2 REST path now 302s to the evds3 web app and returns
    HTML). Hence the manual join instead of requests' params=. Worked out from
    github.com/fatihmete/evds.

    startDate/endDate are DD-MM-YYYY, but at frequency=5 the response stamps each
    row as "YYYY-M" in Tarih. formulas/aggregationTypes must be present even when
    empty.
    """
    def go():
        import requests
        k = key or os.environ.get("EVDS_API_KEY")
        if not k:
            raise RuntimeError("EVDS_API_KEY is not set (needed for Turkish CPI/macro)")
        q = "&".join(f"{a}={b}" for a, b in [
            ("series", series_id), ("startDate", "01-01-1980"),
            ("endDate", time.strftime("%d-%m-%Y")), ("type", "json"),
            ("formulas", ""), ("frequency", "5"), ("aggregationTypes", "")])
        r = requests.get(EVDS_URL + q, headers={"key": k}, timeout=90)
        r.raise_for_status()
        if "json" not in r.headers.get("content-type", ""):
            raise RuntimeError("EVDS returned HTML, not JSON — check EVDS_URL/key")
        df = pd.DataFrame(r.json()["items"])
        col = series_id.replace(".", "_")
        if col not in df:
            raise RuntimeError(f"EVDS returned no column {col}; check the series id")
        idx = pd.to_datetime(df["Tarih"], format="%Y-%m")
        return pd.Series(pd.to_numeric(df[col], errors="coerce").values, index=idx)
    return _cached(f"evds_{series_id}", go, MACRO_DAYS)


def estat(spec):
    """Japan e-Stat monthly series. Needs ESTAT_APP_ID.

    spec is "statsDataId?cdTab=..&cdCat01=..&cdArea=..". Every OECD-sourced
    Japanese CPI series on FRED stopped updating (JPNCPIALLMINMEI ends 2021-06),
    so this is the source. Table 0003427113 unfiltered is 13.5M values (every
    item x every city) -- the filters are not optional.

    e-Stat retires table ids at each CPI rebasing, so re-verify after a rebase.
    """
    def go():
        import urllib.parse
        import requests
        app_id = os.environ.get("ESTAT_APP_ID")
        if not app_id:
            raise RuntimeError("ESTAT_APP_ID is not set (needed for Japanese CPI)")
        stats_id, _, qs = spec.partition("?")
        p = {"appId": app_id, "statsDataId": stats_id, "metaGetFlg": "N",
             **dict(urllib.parse.parse_qsl(qs))}
        r = requests.get("https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData",
                         params=p, timeout=120)
        r.raise_for_status()
        body = r.json()["GET_STATS_DATA"]
        if body["RESULT"]["STATUS"] != 0:
            raise RuntimeError(f"e-Stat: {body['RESULT'].get('ERROR_MSG')}")
        df = pd.DataFrame(body["STATISTICAL_DATA"]["DATA_INF"]["VALUE"])
        # @time is 10 chars, YYYY00MMMM; the annual row ends "0000" and is dropped
        t = df["@time"].astype(str)
        mm = t.str[-2:]
        keep = t.str.len().eq(10) & mm.between("01", "12")
        idx = pd.to_datetime(t[keep].str[:4] + mm[keep], format="%Y%m")
        return pd.Series(pd.to_numeric(df.loc[keep, "$"], errors="coerce").values, index=idx)
    return _cached(f"estat_{stats_key(spec)}", go, MACRO_DAYS)


def stats_key(spec):
    return "".join(c if c.isalnum() else "-" for c in spec)


def splice(new, old):
    """Chain-link `old` onto `new`'s base and use it before `new` starts.

    Statistical agencies rebase and retire the old series (TURKSTAT rebased
    Turkish CPI to 2025=100, stranding the 2003-base index). Two rebasings of
    the same index differ by a constant factor, so scaling `old` by the ratio of
    the two over their overlap recovers one continuous series. The ratio is the
    mean over the whole overlap, not a single month, so one revised print cannot
    shift the entire pre-splice history.
    """
    a, b = new.resample("ME").last(), old.resample("ME").last()
    both = pd.concat([a.rename("a"), b.rename("b")], axis=1, sort=True).dropna()
    if len(both) < 6:
        raise ValueError(f"splice needs >=6 overlapping months, got {len(both)}")
    scaled = b * float((both["a"] / both["b"]).mean())
    return pd.concat([scaled[scaled.index < a.index.min()], a]).sort_index()


def series(spec):
    """Dispatch a registry spec: 'fred:CPIAUCSL', 'evds:TP.FG.J0', 'ons:D7BT',
    a difference of two, 'fred:A - fred:B' (curve slopes, where no ready-made
    spread series exists), or a splice, 'evds:NEW | evds:OLD' (rebased indices,
    newest first)."""
    if spec is None:
        return None
    if " | " in spec:
        new, old = spec.split(" | ", 1)
        return splice(series(new), series(old))
    if " - " in spec:
        a, b = (series(x) for x in spec.split(" - ", 1))
        return (a.resample("ME").last() - b.resample("ME").last()).dropna()
    src, _, sid = spec.partition(":")
    return {"fred": fred, "evds": evds, "ons": ons, "estat": estat, "yf": prices}[src](sid)


# --- registry: adding a market is an entry here, not a code change -------------
# macro components are oriented in overlay.py, not here.
# `window` is that market's default trend window, chosen in results/window_study.csv.
MARKETS = {
    "new_york": dict(name="New York", index="Nasdaq Composite", ticker="^IXIC",
                     ccy="USD", cpi="fred:CPIAUCSL", window=84,
                     macro=dict(policy="fred:FEDFUNDS", curve="fred:T10Y3M",
                                credit="fred:TOTBKCR")),
    "london":   dict(name="London", index="FTSE 100", ticker="^FTSE",
                     ccy="GBP", cpi="ons:D7BT", window=120,  # FRED's GBRCPIALLMINMEI died 2025-03
                     macro=dict(policy="fred:IRSTCI01GBM156N",
                                curve="fred:IRLTLT01GBM156N - fred:IRSTCI01GBM156N",
                                credit=None)),   # no live monthly UK credit series found
    # e-Stat CPI 2020-base: tab=1 index, cat01=0001 all items, area=00000 all Japan
    # start: the 1970-89 re-rating runs the wrong way for two decades and drags the
    # full-sample signal wrong-signed (results/asia_eras.csv). Restricted to 1990+,
    # which is a decision made AFTER seeing that result -- so the UI says so.
    "asia":     dict(name="Asia", index="Nikkei 225", ticker="^N225",
                     ccy="JPY", window=120, start="1990-01",
                     weak=True,
                     note="History restricted to 1990 onward: Japan's 1970&ndash;89 "
                          "re-rating ran the wrong way for two decades and left the "
                          "full-sample reading wrong-signed. That restriction was "
                          "chosen after seeing the result, not before it. Even so, "
                          "this reading still carries less information about forward "
                          "returns than the other three markets.",
                     cpi="estat:0003427113?cdTab=1&cdCat01=0001&cdArea=00000",
                     macro=dict(policy="fred:IRSTCI01JPM156N",
                                curve="fred:IRLTLT01JPM156N - fred:IRSTCI01JPM156N",
                                credit=None)),
    # CPI: TURKSTAT rebased to 2025=100, stranding the 2003-base index at 2026-01.
    # TP.GENENDEKS.T1 is the live general index (2003-) spliced onto the archived
    # 1987-base all-items index so the series covers all of BIST's history.
    "turkey":   dict(name="Turkey", index="BIST 100", ticker="XU100.IS",
                     ccy="TRY", window=120,
                     cpi="evds:TP.GENENDEKS.T1 | evds:TP.FG.A01",
                     macro=dict(policy="evds:TP.BISPOLFAIZ.TUR", curve=None,
                                credit="evds:TP.KM.B33")),
}


def load(key, window=None):
    """Everything the UI needs for one market. Raises only if the market is unusable.

    window=None uses that market's own default (results/window_study.csv): 84m for New
    York, 120m elsewhere. 240m was the original default and is not defensible --
    on Nasdaq it is wrong-signed and fires 6.4x its nominal rate, on London and
    Turkey it never fires at all.
    """
    import bubble
    import overlay
    m = MARKETS[key]
    window = window or m["window"]
    cpi = series(m["cpi"])
    if cpi is None:
        raise RuntimeError(f"{m['name']}: no CPI source configured")
    df = bubble.price_index(prices(m["ticker"]), cpi, warn=False)
    # A market may be restricted to part of its history. The cut happens BEFORE the
    # fit, not after: trimming only the display would let the excluded era still set
    # the trend for the years just after it, which is the incoherent version.
    # Cost: z needs `window` months of data, so it starts `window` months after start.
    start = m.get("start")
    if start:
        df = df[df.index >= start]
    tz, k, ent = bubble.score(df["p"], window)

    macro = {}
    for kind, spec in m["macro"].items():
        try:
            macro[kind] = series(spec)
        except Exception as e:
            _STALE[f"{key}:{kind}"] = f"{type(e).__name__}: {e}"
    comps = overlay.components(cpi, **macro)
    ov, ov_z = overlay.score(comps)

    if start:
        ov, ov_z = ov[ov.index >= start], ov_z[ov_z.index >= start]
        comps = {k2: v[v.index >= start] for k2, v in comps.items()}

    return dict(key=key, **{x: m[x] for x in ("name", "index", "ticker", "ccy")},
                df=df, tz=tz, crit=k, entries=ent, window=window,
                start=start, note=m.get("note"), weak=m.get("weak", False),
                comps=comps, overlay=ov, overlay_z=ov_z)


def state(z, crit):
    """Three-level label. 'elevated' is within 1 of the threshold."""
    if z is None or not (z == z):
        return "n/a"
    return "BUBBLE" if z > crit else "elevated" if z > crit - 1 else "normal"


def _selfcheck():
    import numpy as np
    idx = pd.period_range("2000-01", periods=120, freq="M").to_timestamp("M")
    true = pd.Series(100 * 1.01 ** np.arange(120), index=idx)

    # same index published on two bases, overlapping by 24 months
    new_base = true.iloc[60:] / true.iloc[60] * 100      # rebased, starts month 60
    old_base = true.iloc[:84] * 3.7                      # old base, ends month 83

    out = splice(new_base, old_base)
    assert len(out) == 120, len(out)
    # the seam is invisible: one continuous series, proportional to the truth
    ratio = (out / true).dropna()
    assert np.allclose(ratio, ratio.iloc[0], rtol=1e-9), ratio.describe()
    # the newer series is authoritative where both exist
    assert np.allclose(out.loc[new_base.index], new_base)

    # too little overlap must raise rather than silently rescale on noise
    try:
        splice(true.iloc[60:], true.iloc[:62])
        raise AssertionError("short overlap did not raise")
    except ValueError:
        pass
    print("data.py selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
    cpi = fred("CPIAUCSL")
    print("CPIAUCSL", len(cpi), cpi.index.max().date(), cpi.iloc[-1])
    px = prices("^IXIC")
    print("^IXIC", len(px), px.index.max().date(), round(float(px.iloc[-1]), 1))
    print("stale:", stale())
