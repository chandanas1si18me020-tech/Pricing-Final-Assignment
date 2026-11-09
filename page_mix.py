"""Pricing Mix Calculator: how much freight to contract, and for how long."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import lib

st.title("Pricing Mix Calculator")
st.markdown("Decide how much of your capacity to put under contract, and for how long, based on where the freight "
            "cycle is and what you expect spot rates to do.")

s = lib.current_state()
summ = lib.load_csv("phase_summary.csv", index_col="phase")

with st.sidebar:
    st.header("Your inputs")
    phase = st.selectbox("Cycle phase", lib.PHASE_ORDER, index=lib.PHASE_ORDER.index(s["phase"]),
                         help=f"Defaults to the latest classified phase ({s['month']:%b %Y}). Override if you see it differently.")
    contract = st.number_input("Contract rate you're offered ($/mile, all-in)", 1.00, 6.00, round(s["contract"], 2), 0.05,
                               help="Default: latest DAT national contract van rate.")
    spot = st.number_input("Current spot rate on your lanes ($/mile, all-in)", 1.00, 6.00, round(s["spot"], 2), 0.05,
                           help="Default: latest DAT national spot van rate.")
    g = st.slider("Expected spot change over the next 6 months (%)", -30, 40, int(round(lib.FWD6[phase] * 100)),
                  key=f"g_{phase}",
                  help="Default: average 6-month change in spot after this phase, 2021–2026 (Recovery has only 4 "
                       "observations, so treat its default with caution).") / 100
    risk = st.select_slider("Risk tolerance", ["Low", "Medium", "High"], value="Medium",
                            help="Low = you need steady revenue (thin cash cushion). High = you can ride spot swings.")
    leak = st.slider("Contract leakage in soft markets (%)", 0, 40, 15,
                     help="Share of contracted volume shippers stop tendering when spot falls below your contract rate.") / 100
    st.subheader("Your fleet")
    trucks = st.number_input("Trucks", 1, 20000, 50, 5)
    miles = st.number_input("Loaded miles per truck per year", 20000, 150000, 72000, 1000,
                            help="Default ≈ ATRI 2025 average of 85,991 miles × (1 − 16.5% deadhead).")

# ---- model -------------------------------------------------------------------------
lam = {"Low": 6.0, "Medium": 3.0, "High": 1.5}[risk]
exp_spot = spot * (1 + g)
vol = summ.loc[phase, "spot_monthly_vol"] * np.sqrt(6)         # 6-month horizon
sigma2 = (exp_spot * vol) ** 2
c_eff = contract * (1 - leak) + exp_spot * leak if exp_spot < contract else contract
raw = (exp_spot - c_eff) / (2 * lam * sigma2)                  # mean-variance optimal spot share
spot_share_mv = float(np.clip(raw, 0.0, 0.8))
pb = lib.PLAYBOOK[phase]
pb_spot_lo, pb_spot_hi = 1 - pb["share"][1], 1 - pb["share"][0]

# ---- recommendation ----------------------------------------------------------------
st.subheader("Recommendation")
c1, c2, c3 = st.columns(3)
c1.metric("Contract share (model)", f"{1 - spot_share_mv:.0%}", help="Mean-variance optimum given your outlook and risk tolerance")
c2.metric("Phase playbook range", f"{pb['share'][0]:.0%}–{pb['share'][1]:.0%} contract")
c3.metric("Contract term", pb["term"])
st.markdown(f"{lib.phase_badge(phase)} &nbsp; {pb['why']}", unsafe_allow_html=True)

agree = pb_spot_lo - 0.05 <= spot_share_mv <= pb_spot_hi + 0.05
if agree:
    st.success("Your outlook and the phase playbook agree.")
elif spot_share_mv > pb_spot_hi:
    st.warning("Your outlook calls for **more spot exposure** than the playbook. That pays only if spot really rises as "
               "you expect; historically, loosening contract coverage before a recovery was confirmed cost carriers money.")
else:
    st.warning("Your outlook calls for **more contract coverage** than the playbook. Reasonable if you need steady cash, "
               "but you may give up upside if the market is entering Recovery.")

# ---- comparison --------------------------------------------------------------------
mixes = {"All contract": 0.0, "Model mix": spot_share_mv, "50 / 50": 0.5, "All spot": 1.0}
rows = []
for name, ss in mixes.items():
    exp = (1 - ss) * c_eff + ss * exp_spot
    sd = ss * exp_spot * vol
    rows.append((name, exp, sd))
st.subheader("Expected revenue per loaded mile by mix")
fig = go.Figure()
fig.add_trace(go.Bar(x=[r[0] for r in rows], y=[r[1] for r in rows], marker_color=[lib.INK2, lib.BLUE, lib.MUTED, lib.AQUA],
                     error_y=dict(type="data", array=[r[2] for r in rows], color=lib.INK2, thickness=1.2),
                     text=[f"${r[1]:.2f}" for r in rows], textposition="outside", hovertemplate="$%{y:.2f} ± risk"))
fig.update_yaxes(tickprefix="$", range=[min(r[1] for r in rows) * 0.85, max(r[1] + r[2] for r in rows) * 1.08])
fig.update_layout(hovermode="closest")
st.plotly_chart(lib.style(fig, height=360, legend=False), width="stretch")
st.caption("Bars show expected revenue per loaded mile over the contract life; whiskers show one standard deviation of "
           "spot risk for that mix. Contract value is reduced by leakage when expected spot is below the contract rate.")

base = rows[0][1]
model = rows[1][1]
annual = trucks * miles
c1, c2, c3 = st.columns(3)
c1.metric("Fleet loaded miles / year", f"{annual:,.0f}")
c2.metric("Model mix revenue / year", f"${model * annual / 1e6:,.2f}M")
diff_k = (model - base) * annual / 1e3
c3.metric("vs. all contract", f"{'+' if diff_k >= 0 else '−'}${abs(diff_k):,.0f}K")

with st.expander("How this works"):
    st.markdown(
        "**Model:** choose the spot share *s* that maximizes expected revenue minus a risk penalty:\n\n"
        "spot share = (expected spot − effective contract rate) ÷ (2 × risk aversion × spot variance), capped at 0–80%.\n\n"
        f"- Expected spot = current spot × (1 + expected change) = **${exp_spot:.2f}**\n"
        f"- Effective contract rate after leakage = **${c_eff:.2f}**\n"
        f"- Spot volatility over 6 months in this phase ≈ **{vol:.1%}** (from 2021–2026 DAT data)\n"
        f"- Risk aversion λ = {lam} ({risk})\n\n"
        "**Playbook:** based on how spot and contract rates moved through each phase in 2021–2026. Keep contract "
        "coverage high through Peak, Correction and Trough; shift toward spot only in Recovery. Match the *term* to the "
        "phase: lock long at the top, sign short or indexed contracts at the bottom so your book can follow rates up.\n\n"
        "This is a planning aid for national-average conditions, not a forecast or financial advice.")
