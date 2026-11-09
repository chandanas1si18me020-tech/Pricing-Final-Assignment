"""Freight Pricing Toolkit — free truckload pricing tools for carriers, brokers and shippers.

Run locally:   streamlit run streamlit_app.py
"""
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Freight Pricing Toolkit", page_icon="🚚", layout="wide")

HERE = Path(__file__).resolve().parent


def page_file(name: str) -> str:
    """Find a page file next to this script, or in any subfolder if the upload nested it."""
    if (HERE / name).is_file():
        return name
    hits = [h for h in HERE.rglob(name) if ".git" not in h.parts]
    if hits:
        return str(hits[0].relative_to(HERE))
    st.error(f"Page file `{name}` is missing. Upload it next to streamlit_app.py.")
    st.stop()


market = st.Page(page_file("page_market.py"), url_path="market", title="Market Monitor", icon="📈")
mix = st.Page(page_file("page_mix.py"), url_path="pricing-mix", title="Pricing Mix Calculator", icon="🧮")
cost = st.Page(page_file("page_cost.py"), url_path="cost-simulator", title="Cost Simulator", icon="⛽")
lane = st.Page(page_file("page_lane.py"), url_path="lane-rates", title="Lane Rate Estimator", icon="🗺️")
analyst = st.Page(page_file("page_analyst.py"), url_path="analyst", title="Ask the Freight Analyst", icon="💬")


def home():
    import lib

    s = lib.current_state()
    d_date, diesel = lib.latest_weekly_diesel()
    st.title("Freight Pricing Toolkit")
    st.markdown("#### Free truckload pricing tools for carriers, brokers and shippers")
    st.markdown(f"**Freight market now ({s['month']:%B %Y}):** {lib.phase_badge(s['phase'], s['provisional'])}",
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Spot van rate", f"${s['spot']:.2f}/mi")
    c2.metric("Contract van rate", f"${s['contract']:.2f}/mi")
    c3.metric("Spot minus contract", f"{s['spread'] * 100:+.0f}¢/mi")
    c4.metric(f"Diesel (week of {d_date})", f"${diesel:.2f}/gal")
    st.caption("National dry van averages, all-in including fuel. The latest month's phase is provisional until the "
               "next month's data confirms it.")

    st.divider()
    tools = [
        (market, "Where the freight cycle is now: spot vs. contract rates, demand indicators and phase history."),
        (mix, "How much capacity to put under contract, and for how long, given the market and your risk tolerance."),
        (cost, "Your cost per mile, break-even rate, fuel-surcharge recovery and the true cost of a driver pay change."),
        (lane, "Estimated spot and contract rates for 30 major freight markets, compared with your break-even."),
        (analyst, "Ask questions about the market and the tools in plain language."),
    ]
    cols = st.columns(len(tools))
    for col, (pg, text) in zip(cols, tools):
        with col:
            st.page_link(pg, label=pg.title, icon=pg.icon)
            st.caption(text)

    st.divider()
    st.caption("For planning and education only, not financial advice. Market data: DAT, EIA, Cass, ATA, ATRI.")


st.navigation([st.Page(home, title="Home", icon="🏠", default=True), market, mix, cost, lane, analyst]).run()
