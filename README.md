# Freight Pricing Toolkit

Free truckload pricing tools: Market Monitor, Pricing Mix Calculator, Cost Simulator, Lane Rate Estimator,
and an AI Freight Analyst.

Run locally:

    pip install -r requirements.txt
    streamlit run streamlit_app.py

Deploy on Streamlit Community Cloud: upload all files to a GitHub repo, then create an app with
main file `streamlit_app.py`. For the Freight Analyst, add `ANTHROPIC_API_KEY = "..."` under the app's
Settings → Secrets. Never upload a secrets file to GitHub.

For planning and education only, not financial advice.
