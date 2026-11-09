import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import lib

st.title("Market Monitor")
st.markdown("Where the truckload market is in its cycle. Contract rates lag spot rates, so the phase tells you "
            "whether to lock rates in or keep your book free to re-price.")
s = lib.current_state()
st.markdown(f"Current phase ({s['month']:%B %Y}): {lib.phase_badge(s['phase'], s['provisional'])}", unsafe_allow_html=True)

ph = lib.load_phases()
m = lib.load_master()
w = m.loc[ph.index.min():ph.index.max()]

tab1, tab2, tab3 = st.tabs(["Spot vs. contract", "Supporting indicators", "Phase statistics"])
with tab1:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.68, 0.32], vertical_spacing=0.06)
    lib.add_phase_bands(fig, ph, row=1, col=1)
    lib.add_phase_bands(fig, ph, row=2, col=1)
    fig.add_trace(go.Scatter(x=w.index, y=w.spot_van, name="Spot", line=dict(color=lib.BLUE, width=2.5),
                             hovertemplate="$%{y:.2f}"), row=1, col=1)
    fig.add_trace(go.Scatter(x=w.index, y=w.contract_van, name="Contract", line=dict(color=lib.ORANGE, width=2.5),
                             hovertemplate="$%{y:.2f}"), row=1, col=1)
    sp = w.spread
    fig.add_trace(go.Bar(x=w.index, y=sp, name="Spot minus contract", marker_color=np.where(sp >= 0, lib.BLUE, lib.RED),
                         hovertemplate="%{y:+.2f}", showlegend=False), row=2, col=1)
    fig.update_yaxes(tickprefix="$", tickformat=".2f", row=1, col=1, title_text="$/mile")
    fig.update_yaxes(tickformat="+.2f", row=2, col=1, title_text="Spot − contract")
    lib.style(fig, height=560)
    st.plotly_chart(fig, width="stretch")
    st.markdown(lib.phase_legend_html(), unsafe_allow_html=True)
    st.caption("DAT national dry van rates, all-in including fuel. A few months in 2022, 2024 and 2025 are interpolated "
               "where DAT published no figure. Phase rule: 3-month spread level plus 3-month spot momentum, with a "
               "2-month persistence filter.")

with tab2:
    s2 = m.loc["2019-01-01":]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("Cass shipments, % change vs. year earlier",
                                        "ATA truck tonnage, % change vs. year earlier", "Diesel, $/gallon"))
    for i, col in enumerate(["cass_shipments_yoy", "ata_tonnage_yoy"], start=1):
        y = s2[col] * 100
        fig.add_trace(go.Bar(x=s2.index, y=y, marker_color=np.where(y >= 0, lib.BLUE, lib.RED), showlegend=False,
                             hovertemplate="%{y:+.1f}%"), row=i, col=1)
        fig.update_yaxes(ticksuffix="%", row=i, col=1)
    fig.add_trace(go.Scatter(x=s2.index, y=s2.diesel_usd_gal, line=dict(color=lib.BLUE, width=2.5), showlegend=False,
                             hovertemplate="$%{y:.2f}"), row=3, col=1)
    fig.update_yaxes(tickprefix="$", row=3, col=1)
    lib.style(fig, height=640, legend=False)
    fig.update_annotations(font_size=13, font_color=lib.INK)
    st.plotly_chart(fig, width="stretch")
    st.caption("Sources: FRED series FRGSHPUSM649NCIS (Cass), TRUCKD11 (ATA), GASDESW (EIA weekly diesel, monthly average).")

with tab3:
    summ = lib.load_csv("phase_summary.csv")
    summ = summ.rename(columns={"phase": "Phase", "months": "Months", "avg_spot": "Avg spot ($/mi)",
                                "avg_contract": "Avg contract ($/mi)", "avg_spread": "Avg spread ($/mi)",
                                "spot_monthly_vol": "Spot volatility (monthly)"})
    st.dataframe(summ.style.format({"Avg spot ($/mi)": "${:.2f}", "Avg contract ($/mi)": "${:.2f}",
                                    "Avg spread ($/mi)": "{:+.2f}", "Spot volatility (monthly)": "{:.1%}"}),
                 hide_index=True, width="stretch")
    st.markdown("The gap between contract and spot is widest in **Correction**, not Trough: contract rates lag spot "
                "on the way down. That is when a carrier's existing contracts are worth the most.")
    ep = lib.load_csv("phase_episodes.csv", parse_dates=["start", "end"])
    ep["Period"] = ep.start.dt.strftime("%b %Y") + " – " + ep.end.dt.strftime("%b %Y")
    st.dataframe(ep[["Period", "phase", "months"]].rename(columns={"phase": "Phase", "months": "Months"}).iloc[::-1],
                 hide_index=True, width="stretch")
