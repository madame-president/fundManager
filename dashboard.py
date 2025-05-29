import streamlit as st
from streamlit_autorefresh import st_autorefresh
from tracker import fetchTxs, fetchLivePrice, fetchPrice
import pandas as pd
import time

st.set_page_config(page_title="Bitcoin Fund Tracker", layout="wide")
st_autorefresh(interval=60 * 1000, key="refresh")
st.title("📈 Bitcoin Fund Tracker")

# 🕒 Show last updated timestamp
st.caption(f"🔄 Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")

try:
    # Load and cache raw transaction data
    df = fetchTxs()

    # Fetch historical BTC price in CAD for each transaction
    df["priceCAD"] = df["blockTime"].apply(fetchPrice)

    # Fetch current live BTC price in CAD
    livePrice = fetchLivePrice()

    # Compute derived columns
    df["cadValue"] = df["btcValue"] * df["priceCAD"]
    df["cadCurrentValue"] = df["btcValue"] * livePrice
    df["pnlDollar"] = df["cadCurrentValue"] - df["cadValue"]
    df["pnlPercent"] = (df["pnlDollar"] / df["cadValue"]) * 100
    df["date"] = pd.to_datetime(df["blockTime"], unit="s").dt.strftime("%Y-%m-%d")

    # Round values for clean display
    df["btcValue"] = df["btcValue"].round(8)
    df["priceCAD"] = df["priceCAD"].round(2)
    df["cadValue"] = df["cadValue"].round(2)
    df["cadCurrentValue"] = df["cadCurrentValue"].round(2)
    df["pnlDollar"] = df["pnlDollar"].round(2)
    df["pnlPercent"] = df["pnlPercent"].round(2)

    # Reorder columns for readability
    df = df[[
        "txid", "date", "blockHeight", "btcValue",
        "priceCAD", "cadValue", "cadCurrentValue",
        "pnlDollar", "pnlPercent"
    ]]

    # Display metrics and table
    st.metric("Live BTC Price (CAD)", f"${livePrice:,.2f}")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Failed to load data: {e}")
