import streamlit as st
from streamlit_autorefresh import st_autorefresh
from tracker import fetchTxs, fetchLivePrice, fetchPrice
import pandas as pd
import time

st.set_page_config(page_title="Bitcoin Savings Experiment | Norma Escobar", layout="wide")
st_autorefresh(interval=60 * 1000, key="refresh")
st.title("Bitcoin Savings Tracker: what is the worth of your money if you save in ₿itcoin?")

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
    totalBtc = df["btcValue"].sum()
    totalCad = df["cadValue"].sum()
    currentValue = df["cadCurrentValue"].sum()
    totalPnlDollar = currentValue - totalCad
    totalPnlPercent = (totalPnlDollar / totalCad) * 100
    numPurchases = len(df)
    firstDate = pd.to_datetime(df["date"].min())
    daysSinceStart = (pd.Timestamp.now() - firstDate).days
    averagePrice = totalCad / totalBtc

    # 🔢 Add human-readable index
    df.index = df.index + 1
    df.index.name = "#"
    st.markdown("#### 📊 Account Summary")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total BTC", f"{totalBtc:.8f}")
    col2.metric("Total Invested (CAD)", f"${totalCad:,.2f}")
    col3.metric("Current Account Value", f"${currentValue:,.2f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("PnL ($)", f"${totalPnlDollar:,.2f}", delta_color="normal" if totalPnlDollar >= 0 else "inverse")
    col5.metric("PnL (%)", f"{totalPnlPercent:.2f}%", delta_color="normal" if totalPnlPercent >= 0 else "inverse")
    col6.metric("Purchases", numPurchases)

    col7, col8, col9 = st.columns(3)
    col7.metric("Account Start Date", firstDate.strftime("%Y-%m-%d"))
    col8.metric("Days Since Start", f"{daysSinceStart} days")
    col9.metric("Avg Purchase Price", f"${averagePrice:,.2f}")

    def highlight_pnl(val):
        color = "green" if val > 0 else "red" if val < 0 else "black"
        return f"color: {color}"

    # Create a display copy with renamed columns
    displayDf = df.rename(columns={
    "txid": "Transaction ID",
    "date": "Date",
    "blockHeight": "Block Height",
    "btcValue": "BTC",
    "priceCAD": "Price (CAD)",
    "cadValue": "Cost Basis (CAD)",
    "cadCurrentValue": "Current Value (CAD)",
    "pnlDollar": "PnL ($)",
    "pnlPercent": "PnL (%)"
    })

    styledDf = displayDf.style\
    .map(highlight_pnl, subset=["PnL ($)", "PnL (%)"])\
    .format({
        "Price (CAD)": "${:,.2f}",
        "Cost Basis (CAD)": "${:,.2f}",
        "Current Value (CAD)": "${:,.2f}",
        "PnL ($)": "${:,.2f}",
        "PnL (%)": "{:.2f}%",
    })

    # Display with new headers
    st.dataframe(styledDf, use_container_width=True)

    # Group by date and compute cumulative sums
    chartData = df.groupby("date")[["cadValue", "cadCurrentValue"]].sum().cumsum()
    chartData.columns = ["Normal Savings (CAD)", "Bitcoin Savings (CAD)"]

    st.markdown("#### 📈 Account Value Over Time")
    st.line_chart(chartData)

except Exception as e:
    st.error(f"Failed to load data: {e}")
