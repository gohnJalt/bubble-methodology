"""Streamlit UI. See DESIGN.md section 4; theme.py holds the visual system.

Run: streamlit run app.py
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import bubble
import data
import overlay
import theme
from theme import M

WINDOWS = (12, 24, 36, 60, 84, 120, 240, 360)

st.set_page_config(page_title="Bubble Methodology", layout="wide",
                   initial_sidebar_state="auto")
st.markdown(theme.CSS, unsafe_allow_html=True)


def html(s):
    st.markdown(s, unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _load(key, window):
    return data.load(key, window)


def get(key, window):
    """-> (market, error). window=None means that market's own default."""
    try:
        return _load(key, window or data.MARKETS[key]["window"]), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def last_z(m):
    z = m["tz"]["z"]
    return float(z.iloc[-1]) if len(z) and np.isfinite(z.iloc[-1]) else float("nan")


def prov(m):
    """True when the last month is still provisional: partial month, carried CPI, or both."""
    return bool(m["df"]["prov"].iloc[-1])


def last_ov(m):
    ov = m["overlay"].dropna()
    return float(ov.iloc[-1]) if len(ov) else float("nan")


def stale_banner():
    s = data.stale()
    if s:
        html('<div class="warn"><b>Serving cached data.</b> Refresh failed for '
             + ", ".join(f"<code>{k}</code>" for k in s) + ".</div>")


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


# ---------------------------------------------------------------- charts
def main_chart(m):
    tz, crit = m["tz"], m["crit"]
    p = m["df"]["p"].reindex(tz.index)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.76, 0.24], vertical_spacing=0.045)

    # legendrank keeps the key reading price -> trend -> band -> z, while the
    # trace order stays whatever `fill="tonexty"` needs to shade trend..upper
    fig.add_scatter(x=tz.index, y=tz["trend"], name="trend", row=1, col=1, legendrank=2,
                    line=dict(color=M["trend"], width=1), hovertemplate="%{y:.2f}")
    fig.add_scatter(x=tz.index, y=tz["upper"], name=f"+{crit:.2f}\u03c3", row=1, col=1,
                    legendrank=3, line=dict(color=M["band"], width=1, dash="dot"),
                    fill="tonexty", fillcolor=M["fill"], hovertemplate="%{y:.2f}")
    fig.add_scatter(x=p.index, y=p, name="log real price", row=1, col=1, legendrank=1,
                    line=dict(color=M["price"], width=1.7), hovertemplate="%{y:.2f}")
    fig.add_scatter(x=tz.index, y=tz["z"], name="z", row=2, col=1, legendrank=4,
                    line=dict(color=M["z"], width=1.2), hovertemplate="%{y:.2f}")
    fig.add_hline(y=crit, row=2, col=1, line=dict(color=M["band"], width=1, dash="dot"))
    fig.add_hline(y=0, row=2, col=1, line=dict(color=theme.LINE2, width=1))

    for s, e in episodes(tz["z"] > crit):
        fig.add_vrect(x0=s, x1=e, fillcolor=M["bubble"], opacity=.11,
                      line_width=0, layer="below")

    theme.style_fig(fig, height=560)
    fig.update_yaxes(title_text="log real price", row=1, col=1)
    fig.update_yaxes(title_text="z", row=2, col=1)
    fig.update_xaxes(showline=False, ticks="", row=1, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=2, col=1)
    return fig


def entry_table(m):
    tz, crit = m["tz"], m["crit"]
    rows = []
    for s, e in episodes(tz["z"] > crit):
        seg = m["df"]["real"].loc[s:]
        peak = seg.loc[s:e].max() if len(seg.loc[s:e]) else np.nan
        after = seg.loc[e:].head(25)
        dd = (after.min() / peak - 1) * 100 if len(after) and peak == peak else np.nan
        rows.append({"entered": s.strftime("%Y-%m"),
                     "z": round(float(tz["z"].loc[s]), 2),
                     "months": len(tz.loc[s:e]),
                     "real drawdown %": None if dd != dd else round(float(dd), 1)})
    return pd.DataFrame(rows)


def heat(key):
    rows = {}
    for w in WINDOWS:
        m, err = get(key, w)
        if err:
            continue
        rows[f"{w // 12}y" if w >= 12 else f"{w}m"] = (m["tz"]["z"] > m["crit"]).astype(int)
    if not rows:
        return None
    hm = pd.DataFrame(rows).sort_index()
    fig = go.Figure(go.Heatmap(
        z=hm.T.values, x=hm.index, y=list(hm.columns),
        colorscale=[[0, "#F1EFE9"], [1, M["bubble"]]], showscale=False, ygap=2,
        hovertemplate="%{y} - %{x|%Y-%m}<extra></extra>"))
    theme.style_fig(fig, height=232, legend=False)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return fig


# ---------------------------------------------------------------- pages
def page_overview(window):
    html('<h1>Bubble Methodology</h1>'
         '<p class="lede">Each market&rsquo;s CPI-deflated real index, measured against '
         'its own rolling trend. A reading is a statistical deviation &mdash; not a '
         'forecast, and not advice.</p>')
    stale_banner()

    loaded, errs = {}, []
    for key in data.MARKETS:
        m, err = get(key, window)
        if err:
            errs.append((key, err))
        else:
            loaded[key] = m

    body = ['<div class="rail"><div class="rail-head">'
            '<span>Index</span><span>Window</span><span>z</span>'
            '<span>State &middot; macro</span><span>z, last 10 years</span></div>']
    for key, m in loaded.items():
        z, crit = last_z(m), m["crit"]
        state = data.state(z, crit)
        ov = last_ov(m)
        if ov == ov:
            ovtxt = f'<b>{overlay.band(ov)}</b> <span class="num">{ov:+.2f}</span>'
        else:
            ovtxt = f'<span style="color:{theme.INK3}">not available</span>'
        zc = theme.STATE[state][0] if state != "normal" else theme.INK
        spark = m["tz"]["z"]
        spark = spark[spark.index >= spark.index.max() - pd.DateOffset(years=10)]
        warn = (f'<br><span style="color:{theme.WARN};font-size:.75rem">'
                f'from {m["start"][:4]} &middot; weak signal</span>'
                if m.get("weak") or m.get("start") else "")
        body.append(
            '<div class="row">'
            f'<div class="mk">{m["index"]}<small>{m["ccy"]}{warn}</small></div>'
            f'<div class="num meta">{m["window"] // 12}y</div>'
            f'<div><div class="z" style="color:{zc}">{z:+.2f}</div>'
            f'<div class="z-sub">vs {crit:.2f}</div></div>'
            f'<div>{theme.pill(state)}<div class="meta" style="margin-top:.4rem">{ovtxt}</div></div>'
            f'<div>{theme.sparkline(spark, crit)}'
            f'<div class="z-sub" style="margin-top:.3rem">to {m["df"].index.max():%b %Y}'
            f'{" &middot; provisional" if prov(m) else ""}</div></div>'
            '</div>')
    body.append("</div>")
    html("".join(body))

    for key, err in errs:
        html(f'<div class="err" style="margin-top:.8rem"><b>{data.MARKETS[key]["index"]}'
             f'</b> could not be loaded &mdash; {err}</div>')

    if len(loaded) > 1:
        html('<h2>Across markets</h2>'
             '<p class="lede">One market, or all of them at once? z is built to be '
             'comparable across window lengths, so the per-market windows share an '
             'axis; their thresholds differ only in the second decimal.</p>')
        f = go.Figure()
        for m in loaded.values():
            f.add_scatter(x=m["tz"].index, y=m["tz"]["z"], name=m["index"],
                          line=dict(width=1.15), opacity=.85,
                          hovertemplate="%{y:.2f}")
        f.update_layout(colorway=[M["price"], M["z"], M["band"], M["bubble"]])
        crit = next(iter(loaded.values()))["crit"]
        f.add_hline(y=crit, line=dict(color=theme.LINE2, width=1, dash="dot"),
                    annotation_text=f"threshold ~{crit:.2f}",
                    annotation_position="top left",
                    annotation=dict(font=dict(size=11, color=theme.INK3),
                                    bgcolor=theme.SURFACE, borderpad=3))
        theme.style_fig(f, height=380)
        f.update_yaxes(title_text="z")
        st.plotly_chart(f, width="stretch", config={"displayModeBar": False})


def page_market(key, window):
    m, err = get(key, window)
    if err:
        html(f'<h1>{data.MARKETS[key]["index"]}</h1>'
             f'<div class="err" style="margin-top:1rem">Could not be loaded &mdash; {err}</div>')
        return
    z, crit = last_z(m), m["crit"]
    state = data.state(z, crit)
    ov = last_ov(m)

    span = (f' &middot; history from {m["start"][:4]}' if m.get("start") else "")
    html(f'<h1>{m["index"]}</h1><p class="lede">Real {m["ccy"]}, CPI-deflated '
         f'&middot; {m["window"] // 12}-year rolling trend{span}</p>')
    stale_banner()
    if m.get("note"):
        html(f'<div class="warn" style="margin-top:.9rem">{m["note"]} '
             'The era breakdown is in <code>results/asia_eras.csv</code>.</div>')

    zc = theme.STATE[state][0] if state != "normal" else theme.INK
    cells = [("state", theme.pill(state), f"z {'above' if z > crit else 'below'} threshold"),
             ("z", f'<span class="v" style="color:{zc}">{z:+.2f}</span>',
              f"threshold {crit:.2f}"),
             ("macro overlay",
              f'<span class="v">{ov:+.2f}</span>' if ov == ov
              else f'<span class="v" style="color:{theme.INK3}">&mdash;</span>',
              overlay.band(ov) if ov == ov else "not available"),
             ("data through", f'<span class="v">{m["df"].index.max():%b %Y}</span>',
              ("provisional" if prov(m) else f'readings from {m["tz"].index.min():%Y}'))]
    for col, (k, v, sub) in zip(st.columns(4), cells):
        with col:
            html(f'<div class="card stat"><span class="k">{k}</span>{v}'
                 f'<span class="note">{sub}</span></div>')

    st.plotly_chart(main_chart(m), width="stretch", config={"displayModeBar": False})

    left, right = st.columns([1, 1], gap="large")
    with left:
        html('<h3>Episodes</h3><p class="note">A run of flagged months is one event. '
             'Drawdown runs from the episode peak over the following 24 months.</p>')
        t = entry_table(m)
        if len(t):
            st.dataframe(t, width="stretch", hide_index=True)
        else:
            html('<div class="card note">No episode at this window &mdash; the reading '
                 'has never crossed its threshold over the available history.</div>')
    with right:
        html('<h3>Macro overlay</h3><p class="note">A separate signal. It does not '
             'enter z and does not change the state above.</p>')
        if not m["comps"]:
            html('<div class="card note">No macro components are published for this '
                 'market in the sources used here.</div>')
        for name, s in m["comps"].items():
            f = go.Figure(go.Scatter(x=s.index, y=s, line=dict(color=M["price"], width=1.2),
                                     hovertemplate="%{y:.2f}"))
            theme.style_fig(f, height=112, legend=False)
            f.update_layout(margin=dict(l=8, r=8, t=6, b=4))
            html('<div class="eyebrow" style="margin:.7rem 0 -.15rem">'
                 f'{name.replace("_", " ")} &middot; <span class="num">{s.iloc[-1]:.2f}</span></div>')
            st.plotly_chart(f, width="stretch", config={"displayModeBar": False},
                            key=f"c_{key}_{name}")

    html('<h2>Window sensitivity</h2><p class="lede">The window is the biggest '
         'judgement call in the model, so it is shown rather than hidden. Short '
         'windows fire constantly; the longest ones never fire.</p>')
    f = heat(key)
    if f:
        st.plotly_chart(f, width="stretch", config={"displayModeBar": False})


def page_method():
    html('<h1>Methodology</h1><p class="lede">Every number in this app traces back '
         'to a paragraph on this page.</p>')
    st.markdown("""
## What the model computes

1. **Real price.** The monthly mean of daily closes, divided by that market's own
CPI, then logged. Every market uses its **local** index and **local** CPI — no
currency conversion, no special cases.
2. **Rolling trend.** For each month *t*, a straight line is fitted to the *W*
months **ending at** *t*. Nothing after *t* is ever used: every number shown for
month *t* was computable at *t*.
3. **Leverage correction.** Month *t* is **removed from its own fit** before being
measured against it. The last point of a linear fit is its highest-leverage point,
so an uncorrected residual there is shrunk by `sqrt(1-h)` — about 16% at a
12-month window, under 1% at 240. Without this, z-scores from different window
lengths are not comparable, and comparing windows is a feature here.
4. **z.** The deviation divided by its own standard error, distributed **t(W−3)**
under a trend-stationary null.
5. **Threshold.** `zcrit(W)` carries the same tail probability as 2σ on a normal at
that window's degrees of freedom: 2.32 at W=12, 2.01 at W=360. A flat 2.0 would be
a looser test on short windows.
6. **State.** *Bubble* when z exceeds the threshold, *elevated* within 1 of it,
otherwise *normal*.

## The last reading is provisional

The series runs to the current month, so the newest reading is marked
**provisional** and will move:

- **The month is still trading.** Its level is the mean of the sessions so far, not
of the whole month. Same quantity, noisier estimate.
- **CPI publishes a month or two behind price.** Until it prints, the last published
CPI is carried forward, which deflates those months as if inflation were zero. That
overstates real price by exactly the inflation that has not been reported yet —
immaterial at 2% a year, material in Turkey. The carry stops after three months and
the month is dropped instead, so a dead CPI feed cannot quietly turn a nominal rally
into a real one.

Neither uses information from after the month it is stamped on, so the no-look-ahead
rule still holds. A provisional month can cross the threshold and then uncross it
when the real CPI lands.

## Window lengths

The Nasdaq Composite reads at a 7-year window, the other three at 10 years. These were chosen
against criteria fixed before any results were read, led by a threshold-free
measure: the rank correlation between z and subsequent real returns. The study is
in `results/window_study.csv`, regenerated by `evaluate.py`.

The original 20-year default was dropped. On the Nasdaq it was wrong-signed while
flagging 14.5% of months — 6.4× the rate its own threshold claims — and on the
FTSE 100 and BIST 100 it never fired at all.

## The macro overlay

Real policy rate (negated), credit growth and curve slope, each ranked against its
own trailing decade and oriented so **higher means looser**. The score averages
whichever components exist for a market; a missing series is treated as missing,
never as neutral.

It is a **separate** signal. It never enters z, never changes the state, and is
never averaged with z into a single number. z says *price is far above its own
trend*; it cannot say *and credit is cheap*. The overlay carries that separately,
so neither contaminates the other. It has **not** been tested for predictive
power — it is context, and it is labelled as context.

## Limitations

- **Trend-stationarity is a strong assumption.** The test cannot separate a bubble
from a structural break or a genuine repricing of earnings power.
- **This is not a timing signal.** On the Nasdaq at a 20-year window the state
turned on in 1995 — four years and roughly a 4× before the peak.
- **No multiple-testing correction.** Eight windows across four markets over
hundreds of months is a great many tests, and noise alone clears a 2σ threshold
about 2% of the time. The window-sensitivity strip exists to make that visible,
not to let anyone shop for the window that says what they want.
- **Asia is restricted, and still weak.** The Nikkei is evaluated from 1990 only:
its 1970–89 re-rating ran the wrong way for two decades and left the full-sample
reading wrong-signed. The trend is fitted on the restricted history, not merely
displayed from it, so readings begin ten years after the cut. That restriction was
chosen *after* seeing the result, which is why it is stated here and on the market
itself. Even restricted, this reading carries less information about forward
returns than the other three. Filtering does not fix it; every filter tested is
in `results/filter_study.csv`.
- **Headline CPI is a choice.** Asset prices and consumer prices are different
objects.
- **Turkish CPI is contested.** The official CBRT series is used.
- **Turkey is scored in local CPI-deflated terms** like everywhere else. A
USD-converted BIST looks very different; consistency was chosen over per-market
tuning, because the moment one market gets a bespoke deflator the cross-market
comparison stops meaning anything.

This model measures statistical deviation from trend. It does not forecast returns.
""")


# ---------------------------------------------------------------- shell
with st.sidebar:
    html('<div class="eyebrow" style="margin-bottom:.9rem">Bubble Methodology</div>')
    pages = ["Overview"] + [m["index"] for m in data.MARKETS.values()] + ["Methodology"]
    choice = st.radio("View", pages, label_visibility="collapsed")
    html("<div style='height:1.5rem'></div>")
    picked = st.select_slider(
        "Trend window", ["default", *WINDOWS], value="default",
        format_func=lambda w: w if w == "default"
        else (f"{w // 12}y" if w >= 12 else f"{w}m"))
    window = None if picked == "default" else picked
    if window is None:
        html('<p class="note" style="margin-top:.55rem">Nasdaq <b>7y</b>, others '
             '<b>10y</b> &mdash; see Methodology.</p>')
    else:
        unit = f"{window // 12}y" if window >= 12 else f"{window}m"
        html(f'<p class="note" style="margin-top:.55rem">Threshold at {unit}: '
             f'<b>{bubble.zcrit(window):.2f}</b></p>')

if choice == "Overview":
    page_overview(window)
elif choice == "Methodology":
    page_method()
else:
    page_market(next(k for k, v in data.MARKETS.items() if v["index"] == choice), window)
