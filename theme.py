"""Visual system for the app: tokens, CSS, chart styling, drawn marks.

Operate surface. The instrument, not the brand: the reading should disappear into
the data. The mark palette is inherited from the original notebook figures and is
deliberately unchanged -- it is the project's existing identity.
"""
import numpy as np

# --- tokens ----------------------------------------------------------------
INK = "#1A1917"        # primary text
INK2 = "#57534B"       # secondary, 7.0:1 on canvas
INK3 = "#6B675E"       # tertiary / micro labels, 5.1:1 on canvas
CANVAS = "#FBFAF8"     # warm paper
SURFACE = "#FFFFFF"
PANEL = "#F4F2ED"      # sidebar / second neutral layer
LINE = "#E5E1D8"
LINE2 = "#D5D0C4"

ACCENT = "#534AB7"     # violet, the price mark -> also the UI accent
ALERT = "#B7332D"      # bubble, text-safe (5.4:1)
WARN = "#8A5A0F"       # elevated, text-safe
OK = "#136A4C"         # normal, text-safe

# chart marks — unchanged from the notebook figures
M = dict(price="#534AB7", trend="#96918A", band="#BA7517", fill="rgba(250,199,117,.20)",
         bubble="#E24B4A", z="#1D9E75", grid="#EDEAE3")

STATE = {"BUBBLE": (ALERT, "#FBEDEC"), "elevated": (WARN, "#FBF3E4"),
         "normal": (OK, "#EAF4EF"), "n/a": (INK3, "#F1EFEA")}

UI = "'Inter', ui-sans-serif, system-ui, sans-serif"
MONO = "'IBM Plex Mono', ui-monospace, SFMono-Regular, monospace"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {{
  --ink:{INK}; --ink2:{INK2}; --ink3:{INK3};
  --canvas:{CANVAS}; --surface:{SURFACE}; --panel:{PANEL};
  --line:{LINE}; --line2:{LINE2}; --accent:{ACCENT};
}}

/* ---- app frame ---- */
[data-testid="stAppViewContainer"] {{ background:var(--canvas); }}
[data-testid="stHeader"] {{ background:transparent; }}
[data-testid="stSidebar"] {{ background:var(--panel); border-right:1px solid var(--line); }}
[data-testid="stMainBlockContainer"] {{ padding:3.25rem 3rem 6rem; max-width:1180px; }}
[data-testid="stSidebarUserContent"] {{ padding-top:1.5rem; }}

html, body, [data-testid="stAppViewContainer"] * {{
  font-family:{UI};
  -webkit-font-smoothing:antialiased;
}}
/* Streamlit's icons are ligature glyphs; the rule above would print their names */
[data-testid="stIconMaterial"], span[class*="material-symbols"],
[data-testid="stIconMaterial"] * {{
  font-family:'Material Symbols Rounded','Material Symbols Outlined',
              'Material Icons' !important;
}}
body {{ color:var(--ink); font-size:.9375rem; line-height:1.55; }}

/* ---- browser surfaces: these ship with nobody's design system ---- */
::selection {{ background:{ACCENT}22; color:var(--ink); }}
* {{ scrollbar-width:thin; scrollbar-color:var(--line2) transparent; }}
::-webkit-scrollbar {{ width:10px; height:10px; }}
::-webkit-scrollbar-thumb {{ background:var(--line2); border-radius:6px;
  border:3px solid var(--canvas); }}
::-webkit-scrollbar-thumb:hover {{ background:var(--ink3); }}
::-webkit-scrollbar-track {{ background:transparent; }}
:focus-visible {{ outline:2px solid {ACCENT}; outline-offset:2px; border-radius:3px; }}
a {{ color:var(--accent); text-underline-offset:3px; text-decoration-thickness:1px; }}

/* ---- type scale (fixed rem; product UI, not fluid) ---- */
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {{
  font-family:{UI}; color:var(--ink); letter-spacing:-.02em;
  text-wrap:balance; margin:0; padding:0; }}
[data-testid="stMarkdownContainer"] h1 {{ font-size:1.75rem; font-weight:600;
  line-height:1.2; }}
[data-testid="stMarkdownContainer"] h2 {{ font-size:1.1875rem; font-weight:600;
  margin:2.9rem 0 .3rem; }}
[data-testid="stMarkdownContainer"] h3 {{ font-size:.9375rem; font-weight:600;
  margin:0 0 .15rem; }}
.lede {{ color:var(--ink2); font-size:.9375rem; max-width:68ch; margin:.55rem 0 0; }}
.eyebrow {{ font-size:.6875rem; font-weight:600; letter-spacing:.09em;
  text-transform:uppercase; color:var(--ink3); }}
.num {{ font-family:{MONO}; font-variant-numeric:tabular-nums; letter-spacing:-.01em; }}

/* ---- market rail: rows, not cards. comparison is the job. ---- */
.rail {{ margin-top:1.6rem; border:1px solid var(--line); border-radius:10px;
  background:var(--surface); overflow:hidden; box-shadow:0 1px 2px rgba(26,25,23,.04), 0 8px 24px -16px rgba(26,25,23,.18); }}
.rail-head, .row {{ display:grid; grid-template-columns:1.6fr .62fr .72fr .78fr 190px;
  gap:1rem; align-items:center; padding:.85rem 1.25rem; }}
.rail-head {{ padding-top:.7rem; padding-bottom:.7rem; background:{PANEL}80;
  border-bottom:1px solid var(--line); }}
.rail-head span {{ font-size:.6875rem; font-weight:600; letter-spacing:.09em;
  text-transform:uppercase; color:var(--ink3); }}
.row {{ border-top:1px solid var(--line); transition:background 160ms ease; }}
.row:first-of-type {{ border-top:none; }}
.row:hover {{ background:{PANEL}66; }}
.mk {{ font-weight:600; font-size:.9375rem; }}
.mk small {{ display:block; font-weight:400; color:var(--ink3); font-size:.8125rem;
  margin-top:.1rem; }}
.z {{ font-family:{MONO}; font-variant-numeric:tabular-nums; font-size:1.375rem;
  font-weight:500; letter-spacing:-.02em; }}
.z-sub {{ font-family:{MONO}; font-size:.6875rem; color:var(--ink3); margin-top:.15rem; }}

/* state: a drawn mark plus the word. never colour alone. */
.pill {{ display:inline-flex; align-items:center; gap:.42rem; padding:.2rem .55rem .2rem .45rem;
  border-radius:999px; font-size:.75rem; font-weight:600; letter-spacing:.01em;
  white-space:nowrap; }}
.pill i {{ width:7px; height:7px; border-radius:50%; background:currentColor;
  flex:none; }}
.meta {{ font-size:.8125rem; color:var(--ink2); }}
.meta b {{ font-weight:600; color:var(--ink); }}

/* ---- panels ---- */
.card {{ border:1px solid var(--line); border-radius:10px; background:var(--surface);
  padding:1.15rem 1.25rem; }}
.stat {{ display:flex; flex-direction:column; align-items:flex-start; gap:.3rem; }}
.stat .k {{ font-size:.6875rem; font-weight:600; letter-spacing:.09em;
  text-transform:uppercase; color:var(--ink3); }}
.stat .v {{ font-family:{MONO}; font-variant-numeric:tabular-nums; font-size:1.5rem;
  font-weight:500; letter-spacing:-.02em; color:var(--ink); }}
.note {{ font-size:.8125rem; color:var(--ink2); }}
.warn {{ border:1px solid #E7D3A8; background:#FCF6E9; color:#6B4A0C;
  border-radius:8px; padding:.7rem .9rem; font-size:.8438rem; }}
.err {{ border:1px solid #EBC9C6; background:#FDF2F1; color:#8E2B26;
  border-radius:8px; padding:.7rem .9rem; font-size:.8438rem; }}
.rule {{ height:1px; background:var(--line); border:0; margin:2.25rem 0 0; }}

/* ---- streamlit widgets, quietened ---- */
[data-testid="stSidebar"] label, [data-testid="stWidgetLabel"] p {{
  font-size:.6875rem !important; font-weight:600 !important; letter-spacing:.09em;
  text-transform:uppercase; color:var(--ink3) !important; }}
[data-testid="stSidebar"] [role="radiogroup"] {{ gap:.1rem; }}
[data-testid="stSidebar"] [role="radiogroup"] label {{
  text-transform:none !important; letter-spacing:0 !important; font-size:.9rem !important;
  font-weight:500 !important; color:var(--ink2) !important;
  padding:.34rem .55rem; border-radius:7px; transition:background 140ms ease; }}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background:#E8E5DE; }}
[data-testid="stDataFrame"] {{ border-radius:8px; }}
[data-testid="stDataFrame"] * {{ font-family:{MONO} !important; font-size:.8125rem !important;
  font-variant-numeric:tabular-nums; }}
[data-testid="stHeaderActionElements"] {{ display:none; }}
.stPlotlyChart {{ border:1px solid var(--line); border-radius:10px; background:var(--surface);
  padding:.35rem; }}

/* ---- responsive: structural, not fluid type ---- */
@media (max-width:900px) {{
  [data-testid="stMainBlockContainer"] {{ padding:2rem 1.15rem 4rem; }}
  .rail-head {{ display:none; }}
  .row {{ grid-template-columns:1fr auto; gap:.5rem .9rem; padding:1rem 1.05rem; }}
  .row > :nth-child(3) {{ grid-column:1; }}
  .row > :nth-child(4) {{ grid-column:2; text-align:right; }}
  .row > :nth-child(5) {{ grid-column:1 / -1; }}
  h1 {{ font-size:1.5rem; }}
}}
</style>
"""


def pill(state):
    fg, bg = STATE.get(state, STATE["n/a"])
    label = "bubble" if state == "BUBBLE" else state
    return f'<span class="pill" style="color:{fg};background:{bg}"><i></i>{label}</span>'


def sparkline(z, crit, w=182, h=38):
    """Inline SVG of the z history. Content, not decoration: the threshold is drawn.

    Rendered as SVG rather than a chart object so a row stays a row -- 4 Plotly
    figures in a comparison rail cost more than they show.
    """
    v = np.asarray(z, float)
    v = v[np.isfinite(v)]
    if len(v) < 3:
        return ""
    lo, hi = float(np.min(v)), float(max(np.max(v), crit))
    pad = (hi - lo) * 0.12 or 1.0
    lo, hi = lo - pad, hi + pad
    sx = lambda i: 1 + i * (w - 2) / (len(v) - 1)
    sy = lambda y: h - 1 - (y - lo) * (h - 2) / (hi - lo)
    pts = " ".join(f"{sx(i):.1f},{sy(y):.1f}" for i, y in enumerate(v))
    yc = sy(crit)
    # fill only where the series is above the threshold
    band = ""
    if np.nanmax(v) > crit:
        clip = f"M1,{yc:.1f} L{w-1:.1f},{yc:.1f} L{w-1:.1f},0 L1,0 Z"
        band = (f'<clipPath id="c{id(z)%99999}"><path d="{clip}"/></clipPath>'
                f'<polyline points="{pts}" fill="none" stroke="{M["bubble"]}" '
                f'stroke-width="2.4" clip-path="url(#c{id(z)%99999})"/>')
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true" '
            f'style="display:block;overflow:visible">'
            f'<line x1="1" y1="{yc:.1f}" x2="{w-1}" y2="{yc:.1f}" stroke="{M["band"]}" '
            f'stroke-width="1" stroke-dasharray="3 3"/>'
            f'<polyline points="{pts}" fill="none" stroke="{M["trend"]}" stroke-width="1.4" '
            f'stroke-linejoin="round"/>{band}</svg>')


def style_fig(fig, height=None, legend=True):
    """One chart voice across the app."""
    fig.update_layout(
        template="none", height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="Inter, sans-serif", size=12, color=INK2),
        margin=dict(l=8, r=14, t=34 if legend else 12, b=8),
        hovermode="x unified", hoverlabel=dict(bgcolor=SURFACE, bordercolor=LINE,
                                               font=dict(family="IBM Plex Mono, monospace",
                                                         size=11.5, color=INK)),
        showlegend=legend, legend_traceorder="normal",
        legend=dict(orientation="h", y=1.10, x=0, yanchor="bottom",
                    font=dict(size=11.5), bgcolor="rgba(0,0,0,0)"),
        title=None)
    fig.update_xaxes(showgrid=False, showline=True, linecolor=LINE, linewidth=1,
                     ticks="outside", tickcolor=LINE, ticklen=4,
                     tickfont=dict(size=11, color=INK3))
    fig.update_yaxes(showgrid=True, gridcolor=M["grid"], gridwidth=1, zeroline=False,
                     showline=False, ticks="", tickfont=dict(size=11, color=INK3),
                     title_font=dict(size=11, color=INK3))
    return fig
