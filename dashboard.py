import streamlit as st
from streamlit_autorefresh import st_autorefresh
from tracker import fetchTxs, fetchLivePrice, fetchPrice
import pandas as pd
import time
from dotenv import load_dotenv
import os

print("[DEBUG] FUND_ADDRESS:", os.getenv("BITCOIN_ADDRESS"))

st.set_page_config(page_title="Bitcoin Fund | Norma Escobar", layout="wide")
st_autorefresh(interval=120 * 1000, key="refresh")

st.title("₿itcoin Accrual Fund")
st.caption(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")

debugLogs = []

def log(msg):
    print(msg)
    debugLogs.append(str(msg))

try:
    log("[INFO] Starting data fetch...")
    df = fetchTxs()
    log(f"[INFO] {len(df)} transactions fetched")

    log("[INFO] Fetching price for each blockTime:")
    df["priceCAD"] = df["blockTime"].apply(lambda bt: log(f" - blockTime={bt}") or fetchPrice(bt))

    livePrice = fetchLivePrice()
    log(f"[INFO] Live price fetched: {livePrice} CAD")

    df["cadValue"] = df["btcValue"] * df["priceCAD"]
    df["cadCurrentValue"] = df["btcValue"] * livePrice
    df["pnlDollar"] = df["cadCurrentValue"] - df["cadValue"]
    df["pnlPercent"] = (df["pnlDollar"] / df["cadValue"]) * 100
    df["date"] = pd.to_datetime(df["blockTime"], unit="s").dt.strftime("%Y-%m-%d")

    df["btcValue"] = df["btcValue"].round(8)
    df["priceCAD"] = df["priceCAD"].round(2)
    df["cadValue"] = df["cadValue"].round(2)
    df["cadCurrentValue"] = df["cadCurrentValue"].round(2)
    df["pnlDollar"] = df["pnlDollar"].round(2)
    df["pnlPercent"] = df["pnlPercent"].round(2)

    df = df[[
        "date", "txid", "btcValue",
        "priceCAD", "cadValue", "cadCurrentValue",
        "pnlDollar", "pnlPercent", "blockHeight"
    ]]

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

    df.index = df.index + 1
    df.index.name = "#"
    st.markdown("#### 📊 Fund Summary")

    st.markdown("#### 💰 Portfolio Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total BTC", f"{totalBtc:.8f}")
    col2.metric("Total Invested (CAD)", f"${totalCad:,.2f}")
    col3.metric("Current Fund Value", f"${currentValue:,.2f}")

    st.markdown("#### 📈 Performance")
    col4, col5, col6 = st.columns(3)
    pnl_dollar_emoji = "🟢" if totalPnlDollar >= 0 else "🔴"
    pnl_percent_emoji = "📈" if totalPnlPercent >= 0 else "📉"
    col4.metric("PnL ($)", f"{pnl_dollar_emoji} ${totalPnlDollar:,.2f}", delta_color="normal" if totalPnlDollar >= 0 else "inverse")
    col5.metric("PnL (%)", f"{pnl_percent_emoji} {totalPnlPercent:.2f}%", delta_color="normal" if totalPnlPercent >= 0 else "inverse")
    col6.metric("Purchases", numPurchases)

    st.markdown("#### 📅 Fund History")
    col7, col8, col9 = st.columns(3)
    col7.metric("Fund Start Date", firstDate.strftime("%Y-%m-%d"))
    col8.metric("Days Since Start", f"{daysSinceStart} days")
    col9.metric("Avg Purchase Price", f"${averagePrice:,.2f}")


    def highlight_pnl(val):
        color = "green" if val > 0 else "red" if val < 0 else "black"
        return f"color: {color}"

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

    st.dataframe(styledDf, use_container_width=True)

    chartData = df.groupby("date")[["cadValue", "cadCurrentValue"]].sum().cumsum()
    chartData.columns = ["Fund investments (CAD)", "Fund Value (CAD)"]

    st.markdown("#### 📈 Fund Value Over Time")
    st.line_chart(chartData)

    # Display debug logs at the end
    with st.expander("🔍 Debug Log"):
        for line in debugLogs:
            st.text(line)

except Exception as e:
    st.error(f"❌ Failed to load data: {e}")
    log(f"[EXCEPTION] {e}")
    with st.expander("🔍 Debug Log"):
        for line in debugLogs:
            st.text(line)
