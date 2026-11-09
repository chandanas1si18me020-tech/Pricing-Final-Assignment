"""Lane Rate Estimator: estimated spot and contract rates for major freight markets vs. carrier break-even."""
import math
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
import lib

st.title("Lane Rate Estimator")
st.markdown("Estimate what a lane should pay, on the spot market and under contract, and whether it covers your cost. "
            "Built from national DAT averages, adjusted for distance and for each market's freight balance.")

mk = lib.load_csv("freight_markets.csv").set_index("city")
reg = lib.load_csv("atri_regional_cost_2025.csv").set_index("region")
inp = lib.load_json("model_inputs.json")
s = lib.current_state()
d_date, diesel_now = lib.latest_weekly_diesel()
EQUIP = {"Dry van": 1.00, "Reefer": 1.20, "Flatbed": 1.20}     # DAT Sep 2026 spot ratios to van (3.62/3.01, 3.61/3.01)
CIRCUITY = 1.18                                                # road miles per straight-line mile (assumption)

c1, c2, c3 = st.columns(3)
origin = c1.selectbox("Origin", mk.index, index=list(mk.index).index("Chicago, IL"))
dest = c2.selectbox("Destination", mk.index, index=list(mk.index).index("Atlanta, GA"))
equip = c3.selectbox("Equipment", list(EQUIP))
with st.expander("Market assumptions"):
    a1, a2, a3 = st.columns(3)
    nat_spot = a1.number_input("National spot van rate ($/mi, all-in)", 1.0, 6.0, round(s["spot"], 2), 0.05)
    nat_con = a2.number_input("National contract van rate ($/mi, all-in)", 1.0, 6.0, round(s["contract"], 2), 0.05)
    diesel = a3.number_input("Diesel ($/gal)", 2.0, 8.0, round(diesel_now, 2), 0.05)
    o_f = a1.slider(f"Outbound strength: {origin}", 0.7, 1.3, float(mk.loc[origin, "outbound_factor"]), 0.05,
                    help=">1 = strong outbound market (carriers can charge more to leave). Assumption; adjust to your lane.")
    d_f = a2.slider(f"Outbound strength: {dest}", 0.7, 1.3, float(mk.loc[dest, "outbound_factor"]), 0.05,
                    help="A weak outbound destination (<1) means a poor backhaul, so carriers charge more to go there.")
    deadhead = a3.slider("Your deadhead %", 0, 40, 17) / 100

if origin == dest:
    st.warning("Pick two different markets.")
    st.stop()


def haversine(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


o, d = mk.loc[origin], mk.loc[dest]
miles = haversine(o.lat, o.lon, d.lat, d.lon) * CIRCUITY
short_haul = (250 / miles) ** 0.35 if miles < 250 else 1.0     # shorter lanes pay more per mile (assumption)
dest_adj = 1 + 0.5 * (1 - d_f)                                 # pay more to reach a poor-backhaul market
mult = o_f * dest_adj * short_haul * EQUIP[equip]
est_spot = nat_spot * mult
est_con = nat_con * mult

# Carrier break-even: ATRI 2025 regional costs (avg of the two regions), fuel replaced with today's diesel / MPG
r = reg.loc[[o.atri_region, d.atri_region]].mean(numeric_only=True)
nonfuel = r.total_reported - r.fuel
cost_total_mile = nonfuel + diesel / inp["mpg_2025"]
be = cost_total_mile / (1 - deadhead)

st.subheader(f"{origin} → {dest}")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Estimated road miles", f"{miles:,.0f}")
m2.metric("Est. spot rate", f"${est_spot:.2f}/mi"); m2.caption(f"≈ ${est_spot * miles:,.0f} per load")
m3.metric("Est. contract rate", f"${est_con:.2f}/mi"); m3.caption(f"≈ ${est_con * miles:,.0f} per load")
m4.metric("Your break-even", f"${be:.2f}/mi"); m4.caption(f"≈ ${be * miles:,.0f} per load")

for label, rate in [("spot", est_spot), ("contract", est_con)]:
    mg = rate - be
    (st.success if mg >= 0 else st.error)(
        f"At the estimated **{label}** rate this lane earns **{'+' if mg >= 0 else '−'}${abs(mg):.2f}/mile** "
        f"({'+' if mg >= 0 else '−'}${abs(mg) * miles:,.0f} per load) over break-even.")

others = mk.drop(index=[origin, dest])
fig = go.Figure()
fig.add_trace(go.Scattergeo(lon=others.lon, lat=others.lat, text=others.index, mode="markers", name="Other markets",
                            marker=dict(size=6, color=lib.MUTED), hovertemplate="%{text}<extra></extra>"))
fig.add_trace(go.Scattergeo(lon=[o.lon, d.lon], lat=[o.lat, d.lat], mode="lines", name="Lane",
                            line=dict(width=3, color=lib.BLUE), hoverinfo="skip"))
fig.add_trace(go.Scattergeo(lon=[o.lon, d.lon], lat=[o.lat, d.lat], text=[f"Origin: {origin}", f"Destination: {dest}"],
                            mode="markers+text", textposition="top center", name="Origin / destination",
                            marker=dict(size=12, color=[lib.BLUE, lib.RED], line=dict(width=2, color="white")),
                            hovertemplate="%{text}<extra></extra>", textfont=dict(size=12, color=lib.INK)))
fig.update_geos(scope="usa", showland=True, landcolor="#f0efec", subunitcolor="#d6d5cf", countrycolor="#d6d5cf",
                lakecolor=lib.SURFACE, bgcolor=lib.SURFACE)
fig.update_layout(height=430, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=lib.SURFACE, showlegend=False)
st.plotly_chart(fig, width="stretch")

with st.expander("How the estimate is built"):
    st.markdown(
        f"- **National base:** DAT national van averages (all-in, lanes of 250+ miles): spot ${nat_spot:.2f}, contract ${nat_con:.2f}.\n"
        f"- **Distance:** straight-line miles × {CIRCUITY} to approximate road miles.\n"
        f"- **Short-haul premium:** lanes under 250 miles × (250 ÷ miles)^0.35 = {short_haul:.2f}.\n"
        f"- **Origin strength:** × {o_f:.2f}. **Destination backhaul:** × {dest_adj:.2f}.\n"
        f"- **Equipment:** × {EQUIP[equip]:.2f} (DAT Sep 2026 reefer and flatbed spot rates vs. van).\n"
        f"- **Break-even:** ATRI 2025 cost per mile averaged for the {o.atri_region} and {d.atri_region} regions, with fuel "
        f"replaced by ${diesel:.2f} ÷ {inp['mpg_2025']} MPG, divided by (1 − deadhead).\n\n"
        "Market strength factors, the circuity factor and the short-haul curve are **assumptions** for a planning "
        "estimate, not measured lane rates. Real lane rates vary widely; use DAT RateView or a broker quote for pricing.")
