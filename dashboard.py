import streamlit as st
from streamlit_autorefresh import st_autorefresh
from tracker import getTxs, livePrice, getPrice
import pandas as pd
import time
from dotenv import load_dotenv
import os

print("[DEBUG] FUND_ADDRESS:", os.getenv("BITCOIN_ADDRESS"))

st.set_page_config(page_title="Sister Bitcoin Fund", layout="wide")
st_autorefresh(interval=180 * 1000, key="refresh")

st.title("Sister Bitcoin Fund")
st.caption(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")

with st.container():
        st.markdown("**Fund Address:**")
        st.code("3D3J5tQ5trfZnzDwSozgCTY73PmfuybSuj", language="text")

        st.markdown("**About:**")
        st.markdown("""
        Norma Escobar and Maria Escobar manage a unique high-conviction, non-diversified, bitcoin Fund.
        """)

debugLogs = []

def log(msg):
    print(msg)
    debugLogs.append(str(msg))

try:
    log("[INFO] Starting requests...")
    df = getTxs()
    log(f"[INFO] {len(df)} transactions received")

    log("[INFO] Requesting price for each blockTime:")
    df["priceCAD"] = df["blockTime"].apply(lambda bt: log(f" - blockTime={bt}") or getPrice(bt))

    livePrice = livePrice()
    log(f"[INFO] Live price: {livePrice} CAD")

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
    
    st.markdown("---")
    st.markdown("#### Fund Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Bitcoin Held", f"{totalBtc:.8f}")
    col2.metric("Total Fiat Cost", f"${totalCad:,.2f}")
    col3.metric("Current Fund Value", f"${currentValue:,.2f}")

    st.markdown("---")
    st.markdown("#### Cumulative Performance")
    col4, col5, col6 = st.columns(3)
    pnl_dollar_emoji = "🟢" if totalPnlDollar >= 0 else "🔴"
    pnl_percent_emoji = "🟢" if totalPnlPercent >= 0 else "🔴"
    col4.metric("PnL ($)", f"{pnl_dollar_emoji} ${totalPnlDollar:,.2f}", delta_color="normal" if totalPnlDollar >= 0 else "inverse")
    col5.metric("PnL (%)", f"{pnl_percent_emoji} {totalPnlPercent:.2f}%", delta_color="normal" if totalPnlPercent >= 0 else "inverse")
    col6.metric("Total Transactions", numPurchases)

    st.markdown("---")
    st.markdown("#### Fund History")
    col7, col8, col9 = st.columns(3)
    col7.metric("Fund Inception", firstDate.strftime("%Y-%m-%d"))
    col8.metric("Days Since Inception", f"{daysSinceStart} days")
    col9.metric("Avg Purchase Price", f"${averagePrice:,.2f}")

    st.markdown("---")
    st. markdown("#### Other Stats")
    st.metric("Live Bitcoin Price", f"${livePrice:,.2f}")


    def pnlHighlighter(val):
        color = "green" if val > 0 else "red" if val < 0 else "black"
        return f"color: {color}"

    displayDf = df.rename(columns={
        "txid": "Transaction ID",
        "date": "Date",
        "blockHeight": "Block Height",
        "btcValue": "BTC",
        "priceCAD": "Price",
        "cadValue": "Cost Basis",
        "cadCurrentValue": "Current Value",
        "pnlDollar": "PnL ($)",
        "pnlPercent": "PnL (%)"
    })

    styledDf = displayDf.style\
        .map(pnlHighlighter, subset=["PnL ($)", "PnL (%)"])\
        .format({
            "Price (CAD)": "${:,.2f}",
            "Cost Basis (CAD)": "${:,.2f}",
            "Current Value (CAD)": "${:,.2f}",
            "PnL ($)": "${:,.2f}",
            "PnL (%)": "{:.2f}%",
        })

    st.markdown("---")
    st.markdown("#### Bitcoin Purchases")
    st.dataframe(styledDf, use_container_width=True)

    chartData = df.groupby("date")[["cadValue", "cadCurrentValue"]].sum().cumsum()
    chartData.columns = ["Fiat Capital", "Fund Value"]

    st.markdown("---")
    st.markdown("#### Fund Value Over Time")
    st.line_chart(chartData)

    # --- Annual Return Summary (Y1) ---

    yearOneDate = firstDate + pd.Timedelta(days=365)
    year1 = df[pd.to_datetime(df["date"]) <= yearOneDate]

    year1BtcAcquired = year1["btcValue"].sum()
    year1CadInvested = year1["cadValue"].sum()
    year1Closing = 120_548
    year1BtcValue = year1BtcAcquired * year1Closing
    year1Pnl = year1BtcValue - year1CadInvested
    year1ReturnPercent = (year1Pnl / year1CadInvested) * 100

    annual_summary_df = pd.DataFrame({
        "Metric": [
            "Annual Return",
            "Bitcoin Closing Price",
            "Bitcoin Held",
        ],
        "Value": [
            f"{year1ReturnPercent:.2f}%",
            f"${year1Closing:,.2f}",
            f"{year1BtcAcquired:.8f}",
        ]
    })

    st.markdown("---")
    st.markdown("#### Year 1 Performance")
    st.table(annual_summary_df.set_index("Metric"))

    st.markdown("---")
 
    with st.expander("Debug Log"):
        for line in debugLogs:
            st.text(line)

except Exception as e:
    st.error(f"Failed to load data: {e}")
    log(f"[EXCEPTION] {e}")
    with st.expander("🔍 Debug Log"):
        for line in debugLogs:
            st.text(line)
