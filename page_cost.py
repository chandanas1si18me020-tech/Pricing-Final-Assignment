"""Cost Simulator: cost per mile, break-even rate, fuel-surcharge recovery, and driver-pay trade-off."""
import plotly.graph_objects as go
import streamlit as st
import lib

st.title("Cost Simulator")
st.markdown("Cost per mile sets a carrier's price floor. Adjust your costs to see your break-even rate, your margin at "
            "today's spot and contract rates, and what a fuel spike or a driver pay change really does.")

atri = lib.load_csv("atri_cost_per_mile.csv", index_col="year")
s = lib.current_state()
d_date, diesel_now = lib.latest_weekly_diesel()
COST_KEYS = ["truck_trailer_payments", "repair_maintenance", "insurance", "permits_licenses", "tires", "tolls",
             "driver_wages", "driver_benefits"]
LABELS = {"truck_trailer_payments": "Truck & trailer payments", "repair_maintenance": "Repair & maintenance",
          "insurance": "Insurance", "permits_licenses": "Permits & licenses", "tires": "Tires", "tolls": "Tolls",
          "driver_wages": "Driver wages", "driver_benefits": "Driver benefits", "fuel": "Fuel"}

SCENARIOS = {
    "2025 baseline (ATRI)": dict(year=2025, diesel=3.70, spot=2.06, contract=2.42, adj={}),
    "2022 diesel spike": dict(year=2022, diesel=5.00, spot=2.69, contract=3.15, adj={}),
    "2023 freight recession": dict(year=2023, diesel=4.20, spot=2.13, contract=2.65, adj={}),
    "Today (latest data)": dict(year=2025, diesel=round(diesel_now, 2), spot=round(s["spot"], 2),
                                contract=round(s["contract"], 2), adj={}),
    "Tariff on trucks & parts": dict(year=2025, diesel=3.70, spot=2.06, contract=2.42,
                                     adj={"truck_trailer_payments": 1.15, "repair_maintenance": 1.10, "tires": 1.10}),
}


def sgn(v):
    return "+" if v >= 0 else "−"


def money_m(v):
    return f"{sgn(v)}${abs(v) / 1e6:.2f}M"


def apply_scenario(name):
    sc = SCENARIOS[name]
    for k in COST_KEYS:
        st.session_state[f"c_{k}"] = round(float(atri.loc[sc["year"], k]) * sc["adj"].get(k, 1.0), 3)
    st.session_state["diesel"] = sc["diesel"]
    st.session_state["spot"] = sc["spot"]
    st.session_state["contract"] = sc["contract"]


if "c_driver_wages" not in st.session_state:
    apply_scenario("Today (latest data)")

st.markdown("**Load a scenario:**")
cols = st.columns(len(SCENARIOS))
for col, name in zip(cols, SCENARIOS):
    col.button(name, on_click=apply_scenario, args=(name,), width="stretch")

tab1, tab2 = st.tabs(["Cost & break-even", "Driver pay trade-off"])

with tab1:
    left, right = st.columns([1, 1.4])
    with left:
        st.markdown("##### Costs per total mile ($)")
        costs = {}
        for k in COST_KEYS:
            costs[k] = st.number_input(LABELS[k], 0.0, 2.0, step=0.005, format="%.3f", key=f"c_{k}")
        st.markdown("##### Fuel")
        diesel = st.number_input("Diesel price ($/gal)", 2.0, 8.0, step=0.05, key="diesel",
                                 help=f"Latest EIA weekly average: ${diesel_now:.2f} (week of {d_date}).")
        mpg = st.number_input("Truck fuel economy (MPG)", 4.0, 12.0, 7.43, 0.05, help="ATRI 2025 average: 7.43 MPG.")
        costs["fuel"] = diesel / mpg
        st.markdown("##### Operations")
        deadhead = st.slider("Empty (deadhead) miles, % of total", 0, 40, 17, help="ATRI 2025 average: 16.5%.") / 100
        overhead = st.slider("Overhead, % of revenue", 0, 35, 0,
                             help="ATRI's costs exclude overhead (offices, non-driver staff, technology). For dry-van "
                                  "carriers that was about 26% of revenue in 2025. Leave at 0 for a marginal-cost floor.") / 100
        margin = st.slider("Target operating margin (%)", 0, 15, 5) / 100
    with right:
        total = sum(costs.values())
        loaded = total / (1 - deadhead)
        breakeven = loaded / (1 - overhead)
        target = loaded / (1 - overhead - margin)
        st.markdown("##### Results")
        c1, c2, c3 = st.columns(3)
        c1.metric("Cost per total mile", f"${total:.3f}")
        c2.metric("Break-even per loaded mile", f"${breakeven:.2f}")
        c3.metric(f"Rate for {margin:.0%} margin", f"${target:.2f}")
        st.markdown("##### Against market rates (all-in, per loaded mile)")
        spot = st.number_input("Spot rate ($/mi)", 0.5, 8.0, step=0.05, key="spot")
        contract = st.number_input("Contract rate ($/mi)", 0.5, 8.0, step=0.05, key="contract")
        c1, c2 = st.columns(2)
        c1.metric("Margin on spot", f"{sgn(spot - breakeven)}${abs(spot - breakeven):.2f}/mi", f"{(spot - breakeven) / spot:+.1%} of rate")
        c2.metric("Margin on contract", f"{sgn(contract - breakeven)}${abs(contract - breakeven):.2f}/mi", f"{(contract - breakeven) / contract:+.1%} of rate")
        order = sorted(costs, key=lambda k: costs[k])
        fig = go.Figure(go.Bar(y=[LABELS[k] for k in order], x=[costs[k] / (1 - deadhead) for k in order], orientation="h",
                               marker_color=[lib.ORANGE if k == "fuel" else lib.BLUE for k in order],
                               text=[f"${costs[k] / (1 - deadhead):.3f}" for k in order], textposition="outside",
                               hovertemplate="%{x:$.3f} per loaded mile<extra></extra>"))
        fig.update_xaxes(tickprefix="$", title_text="Cost per loaded mile", range=[0, max(costs.values()) / (1 - deadhead) * 1.25])
        fig.update_layout(hovermode="closest", title=dict(text="Where each loaded mile's cost goes", font_size=14))
        st.plotly_chart(lib.style(fig, height=380, legend=False), width="stretch")

    st.markdown("##### Fuel surcharge recovery (contract freight)")
    f1, f2, f3 = st.columns(3)
    peg = f1.number_input("Surcharge base (peg) price ($/gal)", 0.0, 5.0, 1.25, 0.05,
                          help="Diesel price at which the surcharge is zero. $1.20–$1.25 is common.")
    ref_mpg = f2.number_input("Surcharge MPG divisor", 4.0, 8.0, 6.0, 0.5, help="Many schedules use 6.0 MPG.")
    fsc = max(diesel - peg, 0) / ref_mpg
    fuel_loaded = costs["fuel"] / (1 - deadhead)
    f3.metric("Surcharge per loaded mile", f"${fsc:.3f}", f"covers {fsc / fuel_loaded:.0%} of fuel cost" if fuel_loaded else None)
    st.caption("Contract surcharges rise automatically with diesel. Spot rates are quoted all-in, so a carrier on the spot "
               "market must win the fuel increase back load by load (DAT, 2026).")

with tab2:
    st.markdown("Does a pay cut save money once you count turnover and trucks sitting without drivers? Enter your own "
                "fleet's numbers.")
    a, b = st.columns(2)
    with a:
        cut = st.slider("Pay change (¢ per mile; negative = raise)", -10.0, 10.0, 1.0, 0.5)
        drivers = st.number_input("Drivers", 1, 50000, 100, 10)
        dmiles = st.number_input("Miles per driver per year", 20000, 150000, 85991, 1000, help="ATRI 2025: 85,991.")
        resp = st.select_slider("Turnover response to pay", options=[0.5, 1.0, 2.0, 3.0, 5.0], value=1.0,
                                format_func=lambda v: f"{v:g}× ATRI average" + (" (tight market)" if v >= 3 else ""),
                                help="ATRI 2026: 2.9 points lower turnover per $5,000 of annual pay, on average.")
        repl = st.number_input("Cost to replace one driver ($)", 1000, 50000, 15866, 500,
                               help="Rodriguez et al. (2000): $8,234, inflated to January 2026 dollars with the BLS CPI.")
    with b:
        open_pts = st.slider("Change in open tractors (percentage points)", -3.0, 5.0, 0.0, 0.1,
                             help="How many more of your tractors sit without drivers because of the change.")
        tractors = st.number_input("Tractors", 1, 50000, 90, 5)
        contrib = st.number_input("Contribution margin per tractor-week ($)", 0, 10000, 2500, 50,
                                  help="Freight revenue minus variable costs avoided while parked. About $2,500 is typical for a dry-van truckload fleet.")
    annual_change = cut / 100 * dmiles
    savings = annual_change * drivers
    extra_turn = 0.029 / 5000 * resp * annual_change
    turnover_cost = extra_turn * drivers * repl
    seat_cost = open_pts / 100 * tractors * contrib * 52
    net = savings - turnover_cost - seat_cost
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pay savings / yr", money_m(savings))
    c2.metric("Extra turnover cost / yr", money_m(-turnover_cost), f"{extra_turn * 100:+.1f} pts turnover", delta_color="off")
    c3.metric("Empty-seat cost / yr", money_m(-seat_cost))
    c4.metric("Net effect / yr", money_m(net))
    fig = go.Figure(go.Waterfall(x=["Pay savings", "Turnover cost", "Empty seats", "Net"],
                                 measure=["relative", "relative", "relative", "total"],
                                 y=[savings / 1e6, -turnover_cost / 1e6, -seat_cost / 1e6, 0],
                                 increasing=dict(marker_color=lib.BLUE), decreasing=dict(marker_color=lib.RED),
                                 totals=dict(marker_color=lib.INK2), connector=dict(line_color=lib.GRID),
                                 text=[money_m(v) for v in [savings, -turnover_cost, -seat_cost, net]],
                                 textposition="outside"))
    fig.update_yaxes(tickprefix="$", ticksuffix="M")
    fig.update_layout(hovermode="closest")
    st.plotly_chart(lib.style(fig, height=380, legend=False), width="stretch")
    if cut > 0 and seat_cost > 0:
        be = savings / (tractors * contrib * 52) * 100 if tractors * contrib else float("nan")
        st.info(f"This pay cut breaks even if it adds no more than **{be:.1f} points** of open tractors.")
    st.caption("Basis: ATRI (2026) pay–turnover slope; Rodriguez et al. (2000) driver replacement cost in 2026 dollars. "
               "Direct turnover costs are usually small next to the margin lost when trucks sit without drivers.")
