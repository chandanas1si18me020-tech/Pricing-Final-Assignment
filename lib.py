"""Shared data loaders, constants, and chart helpers for the Freight Pricing Toolkit."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

def _find_data_dir(marker: str = "master_monthly.csv") -> Path:
    """Folder holding the data files, wherever the upload put them (repo root, data/, or any subfolder)."""
    here = Path(__file__).resolve().parent
    roots = []
    for r in (here, Path.cwd(), *list(here.parents)[:2]):
        if r not in roots:
            roots.append(r)
    for r in roots:
        if (r / marker).is_file():
            return r
    for r in roots:
        hits = [h for h in sorted(r.rglob(marker), key=lambda x: len(x.parts))
                if "site-packages" not in h.parts and ".git" not in h.parts]
        if hits:
            return hits[0].parent
    st.error(f"Data file `{marker}` is missing. Upload all the .csv and .json files next to streamlit_app.py.")
    st.stop()


DATA = _find_data_dir()

# Validated palette (dataviz reference palette)
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
PHASE_COL = {"Peak": "#e34948", "Correction": "#eda100", "Trough": "#6250d6", "Recovery": "#1baf7a"}
PHASE_TINT = {"Peak": "rgba(227,73,72,0.10)", "Correction": "rgba(237,161,0,0.12)",
              "Trough": "rgba(98,80,214,0.09)", "Recovery": "rgba(27,175,122,0.12)"}
PHASE_ORDER = ["Peak", "Correction", "Trough", "Recovery"]

# Contract playbook by cycle phase
PLAYBOOK = {
    "Peak":       {"share": (0.90, 1.00), "term": "Long (12+ months)", "why": "Contract rates are at their highest; lock them before spot turns."},
    "Correction": {"share": (0.90, 1.00), "term": "Long (12 months)",  "why": "Contracts still pay well above spot (56¢ on average); protect them."},
    "Trough":     {"share": (0.85, 1.00), "term": "Short (~3 months) or indexed", "why": "Contracts still beat spot, but don't lock in bottom-of-cycle rates."},
    "Recovery":   {"share": (0.40, 0.60), "term": "Short (~3 months)", "why": "Spot climbs past lagging contracts; keep the book free to re-price up."},
}
# Average 6-month-ahead change in spot by phase, 2021-2026 (Recovery: only 4 observations)
FWD6 = {"Peak": -0.096, "Correction": -0.067, "Trough": 0.031, "Recovery": 0.250}


@st.cache_data
def load_master() -> pd.DataFrame:
    return pd.read_csv(DATA / "master_monthly.csv", parse_dates=["month"], index_col="month")


@st.cache_data
def load_phases() -> pd.DataFrame:
    return pd.read_csv(DATA / "phases_monthly.csv", parse_dates=["month"], index_col="month")


@st.cache_data
def load_csv(name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(DATA / name, **kw)


@st.cache_data
def load_json(name: str) -> dict:
    return json.loads((DATA / name).read_text())


@st.cache_data
def latest_weekly_diesel() -> tuple[str, float]:
    d = pd.read_csv(DATA / "GASDESW.csv", parse_dates=["observation_date"]).dropna()
    last = d.iloc[-1]
    return last.observation_date.strftime("%b %d, %Y"), float(last.GASDESW)


def current_state() -> dict:
    ph = load_phases()
    last = ph.iloc[-1]
    return {"month": ph.index[-1], "phase": last.phase, "provisional": bool(last.provisional),
            "spot": float(last.spot_van), "contract": float(last.contract_van), "spread": float(last.spread)}


def style(fig: go.Figure, height: int = 420, legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, font=dict(color=INK2, size=13),
        hovermode="x unified", showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=12)),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def add_phase_bands(fig: go.Figure, ph: pd.DataFrame, row=None, col=None):
    runs = (ph.phase != ph.phase.shift()).cumsum()
    for _, g in ph.groupby(runs):
        name = g.phase.iloc[0]
        x0 = g.index.min() - pd.Timedelta(days=15)
        x1 = g.index.max() + pd.Timedelta(days=15)
        kw = dict(x0=x0, x1=x1, fillcolor=PHASE_TINT[name], line_width=0, layer="below")
        if row:
            fig.add_vrect(row=row, col=col, exclude_empty_subplots=False, **kw)
        else:
            fig.add_vrect(**kw)
    return fig


def phase_legend_html() -> str:
    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;margin-right:14px;font-size:0.85rem;color:{INK2}">'
        f'<span style="width:12px;height:12px;border-radius:3px;background:{PHASE_COL[p]};margin-right:6px;display:inline-block"></span>{p}</span>'
        for p in PHASE_ORDER)
    return f'<div style="margin:-4px 0 8px 0">Phase shading: {chips}</div>'


def phase_badge(phase: str, provisional: bool = False) -> str:
    txt = phase + (" (provisional)" if provisional else "")
    fg = "#ffffff" if phase in ("Peak", "Trough") else INK
    return (f'<span style="background:{PHASE_COL[phase]};color:{fg};padding:4px 12px;border-radius:999px;'
            f'font-weight:600;font-size:0.95rem">{txt}</span>')


def footer_sources(text: str):
    st.caption(text)
