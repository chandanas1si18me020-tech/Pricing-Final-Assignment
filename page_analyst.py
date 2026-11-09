"""Ask the Freight Analyst: a chatbot grounded in the toolkit's market data and tool guide."""
import os
import streamlit as st
import lib

MODEL = "claude-haiku-5-5"
MAX_TURNS = 12

st.title("Ask the Freight Analyst")
st.markdown("Ask about current truckload rates, where the market is in its cycle, pricing concepts, or how to use the "
            "tools on this site.")


def api_key():
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


@st.cache_data
def build_context() -> str:
    ph = lib.load_phases()
    recent = ph[["phase", "spot_van", "contract_van", "spread"]].tail(12)
    recent.index = recent.index.strftime("%Y-%m")
    summ = lib.load_csv("phase_summary.csv")
    eps = lib.load_csv("phase_episodes.csv")
    m = lib.load_master()
    ind = m[["diesel_usd_gal", "cass_shipments_yoy", "ata_tonnage_yoy"]].dropna(how="all").tail(6)
    ind.index = ind.index.strftime("%Y-%m")
    s = lib.current_state()
    pb = {p: (f"{v['share'][0]:.0%}-{v['share'][1]:.0%}", v["term"]) for p, v in lib.PLAYBOOK.items()}
    return f"""
CURRENT MARKET (latest month {s['month']:%Y-%m}; phase {s['phase']}{' (provisional)' if s['provisional'] else ''}):
DAT national dry van rates, all-in incl. fuel, $/mile, last 12 months:
{recent.round(2).to_string()}

Supporting indicators, last 6 months (diesel $/gal; Cass shipments and ATA tonnage as year-over-year change):
{ind.round(3).to_string()}

CYCLE PHASES (rule: 3-month spread level, tight if within $0.10 of contract; 3-month spot momentum +/-5%; 2-month persistence):
Episodes:
{eps.to_string(index=False)}
Phase statistics (2021-09 to 2026-09):
{summ.round(3).to_string(index=False)}
Average 6-month-ahead change in spot after each phase: {lib.FWD6}

PLAYBOOK (contract share range, contract term) by phase: {pb}

MARKET PATTERNS (2021-2026)
- Spot was below contract every month Mar 2022 - May 2026; spot passed contract again in Jun 2026.
- 2021-2025: truckload operating cost per mile (ATRI) +27% while contract rates fell ~14% and spot ~26%. ATRI 2025 average cost $2.336/mile.
- Contract rates lag spot by several months; the gap is widest in Correction, when existing contracts are worth the most.

TOOLS ON THIS SITE (how to use them)
- Market Monitor: spot vs. contract chart with phase shading, demand indicators (Cass shipments, ATA tonnage, diesel), phase statistics and history.
- Pricing Mix Calculator: sidebar inputs (phase, offered contract rate, current spot, expected 6-month spot change, risk tolerance, leakage, trucks, loaded miles). Returns a recommended contract share (mean-variance: spot share = (expected spot - effective contract) / (2 x risk aversion x variance), capped 0-80%), the phase playbook range and contract term, and expected revenue by mix.
- Cost Simulator: enter cost per mile by line item (or load a scenario), diesel, MPG, deadhead, overhead and target margin -> break-even and target rate per loaded mile, margin on spot and contract, fuel surcharge recovery. Driver pay tab: pay change, drivers, miles, turnover response, replacement cost (~$15,866), change in open tractors, contribution per tractor-week -> net annual effect of a pay change.
- Lane Rate Estimator: pick origin, destination (30 markets) and equipment -> estimated miles, spot and contract rate, and break-even. Estimates use national averages adjusted for distance and market strength; they are not quotes.

LIMITATIONS: one cycle of data (about 5 years), short Recovery sample; national averages, not lane quotes; rates include fuel.
"""


SYSTEM = """You are the Freight Analyst on the Freight Pricing Toolkit, a free website of truckload pricing tools.
Help carriers, brokers and shippers understand the market and use the tools. Use the CONTEXT for any market figures;
never invent rates, dates or company figures, and quote numbers with their units and period. If the context lacks the
answer, say so and point to the tool that could help (Market Monitor, Pricing Mix Calculator, Cost Simulator, Lane Rate
Estimator). You may explain pricing concepts (spot vs. contract, fuel surcharges, deadhead, operating ratio) in general
terms. Keep answers short (under 150 words unless asked for detail). Do not give personalized financial or investment
advice; frame suggestions as planning considerations.

CONTEXT
"""

key = api_key()
if not key:
    st.info("The analyst needs an Anthropic API key to run. Site owner: add `ANTHROPIC_API_KEY` to the app's secrets "
            "(Streamlit Community Cloud → app settings → Secrets) or set it as an environment variable when running locally.")
    st.markdown("**Example questions it answers:** What phase is the market in? · Should I sign 12-month contracts "
                "now? · How do I find my break-even rate? · What is a fuel surcharge?")
    st.stop()

import anthropic  # noqa: E402

client = anthropic.Anthropic(api_key=key)
if "chat" not in st.session_state:
    st.session_state.chat = []

examples = ["What phase is the freight market in right now?", "Should I sign 12-month contracts now?",
            "How do I find my break-even rate?", "How does a fuel surcharge work?"]
cols = st.columns(len(examples))
clicked = None
for c, q in zip(cols, examples):
    if c.button(q, width="stretch"):
        clicked = q

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask about rates, cycle phases, or the tools") or clicked
if prompt:
    if len(st.session_state.chat) >= MAX_TURNS * 2:
        st.warning("This conversation is getting long. Refresh the page to start a new one.")
        st.stop()
    st.session_state.chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            with client.messages.stream(model=MODEL, max_tokens=700, system=SYSTEM + build_context(),
                                        messages=st.session_state.chat) as stream:
                reply = st.write_stream(stream.text_stream)
        except anthropic.APIError as e:
            reply = f"Sorry, the analyst is unavailable right now ({e.__class__.__name__})."
            st.error(reply)
    st.session_state.chat.append({"role": "assistant", "content": reply})

if st.session_state.chat and st.button("Clear conversation"):
    st.session_state.chat = []
    st.rerun()
st.caption(f"Powered by Claude ({MODEL}). Answers may contain mistakes; check important figures.")
