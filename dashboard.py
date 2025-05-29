import streamlit as st
from tracker import fetchTxs, fetchLivePrice, fetchPrice
import pandas as pd

st.set_page_config(page_title="Bitcoin Fund Tracker", layout="wide")

st.title("📈 Bitcoin Fund Tracker")

try:
    # Load base transaction data
    df = fetchTxs()

    # Fetch historical price for each blockTime (per tx)
    df["priceCAD"] = df["blockTime"].apply(fetchPrice)

    # Fetch current BTC price in CAD
    livePrice = fetchLivePrice()

    # Column order and formatting
    df = df[[
        "txid", "date", "blockHeight", "btcValue",
        "priceCAD", "cadValue", "cadCurrentValue",
        "pnlDollar", "pnlPercent"
    ]]

    df["btcValue"] = df["btcValue"].round(8)
    df["priceCAD"] = df["priceCAD"].round(2)
    df["cadValue"] = df["cadValue"].round(2)
    df["cadCurrentValue"] = df["cadCurrentValue"].round(2)
    df["pnlDollar"] = df["pnlDollar"].round(2)
    df["pnlPercent"] = df["pnlPercent"].round(2)

    # Display live price and data
    st.metric("Live BTC Price (CAD)", f"${livePrice:,.2f}")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Failed to load data: {e}")
