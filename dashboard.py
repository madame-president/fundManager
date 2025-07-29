import streamlit as st
from streamlit_autorefresh import st_autorefresh
from tracker import getTxs, livePrice, getPrice
import pandas as pd
import time
from dotenv import load_dotenv
import os

df = getTxs()
livePrice = livePrice()


print("[DEBUG] FUND_ADDRESS:", os.getenv("BITCOIN_ADDRESS"))

st.set_page_config(page_title="Bitcoin Address Analyzer", layout="wide")
st_autorefresh(interval=1200 * 1000, key="refresh")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(
        """
        <h1 style='text-align: left; color: #111;'>This is an autonomous Bitcoin address analyzer.</h1>
        <h4 style='text-align: left; color: gray;'> 
            I built this using Python, Streamlit and SQLite. It is updated every 20 minutes using 
            <a href='https://mempool.space/docs/api/rest' target='_blank' style='color: gray; text-decoration: underline;'>mempool.space</a>.
        </h4>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.caption(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")

st.markdown("---")

with st.container():
        st.markdown("**Address being analyzed:**")
        st.code("3D3J5tQ5trfZnzDwSozgCTY73PmfuybSuj", language="text")

        st.markdown("**About this tool:**")
        st.markdown("""
        This analyzer autonomously tracks a Bitcoin address using real-time data.
                    
        **I created this tool to act like a self-updating Bitcoin dashboard. But without managers, associates or additional costs related to labour.
        Just the data, automated every 20 minutes.**
        """)

debugLogs = []

def log(msg):
    print(msg)
    debugLogs.append(str(msg))

try:
    log("[INFO] Starting requests...")

    log(f"[INFO] {len(df)} transactions received")

    log("[INFO] Requesting price for each blockTime:")
    df["priceCAD"] = df["blockTime"].apply(lambda bt: log(f" - blockTime={bt}") or getPrice(bt))

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
    st.markdown("#### Statistics related to address overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Bitcoin Held", f"{totalBtc:.8f}")
    col2.metric("Total Fiat Cost", f"${totalCad:,.2f}")
    col3.metric("Current Bitcoin Value", f"${currentValue:,.2f}")

    st.markdown("---")
    st.markdown("#### Statistics related to cumulative performance")
    col4, col5, col6 = st.columns(3)
    pnl_dollar_emoji = "🟢" if totalPnlDollar >= 0 else "🔴"
    pnl_percent_emoji = "🟢" if totalPnlPercent >= 0 else "🔴"
    col4.metric("PnL ($)", f"{pnl_dollar_emoji} ${totalPnlDollar:,.2f}", delta_color="normal" if totalPnlDollar >= 0 else "inverse")
    col5.metric("PnL (%)", f"{pnl_percent_emoji} {totalPnlPercent:.2f}%", delta_color="normal" if totalPnlPercent >= 0 else "inverse")
    col6.metric("Total Transactions", numPurchases)

    st.markdown("---")
    st.markdown("#### Statistics related to address history")
    col7, col8, col9 = st.columns(3)
    col7.metric("Address First Seen", firstDate.strftime("%Y-%m-%d"))
    col8.metric("Days Since First Seen", f"{daysSinceStart} days")
    col9.metric("Avg Purchase Price", f"${averagePrice:,.2f}")

    st.markdown("---")
    st. markdown("#### Statistic related to bitcoin price")
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
    st.markdown("#### Self-updating table with historical transactions")
    st.dataframe(styledDf, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Automatically performs annual return analysis")
    st.markdown("""
        This tool automatically calculates **annual return** for each 365-day period since the first transaction at the address.
        
        For each rolling year:
        - Tracks the amount of bitcoin acquired
        - Computes the CAD closing price
        - Calculates the CAD value of bitcoin exactly 1 year later
        - Displays the annual return percentage
                    
        This gives you an objective view of how each year performed, regardless of timing or volatility.
        """)

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
    with st.container():
        st.markdown(
        """
        <h4 style='margin-bottom: 0.2rem;'>If you want this tool for your Bitcoin address:</h4>
        <div style='display: flex; align-items: center; gap: 1.5rem; margin-top: 2rem;'>
            <img src='https://payhip.com/cdn-cgi/image/format=auto,width=500/https://pe56d.s3.amazonaws.com/o_1ipdbv9jbqh91dhcs86184vqqoc.jpeg' style='width: 100px; border-radius: 50%; border: 2px solid #ccc;' alt='Norma Escobar'>
            <div>
                <p style='margin: 0; color: gray; font-size: 0.95rem;'>
                    Visit <a href='https://normaescobar.com' target='_blank' style='color: #0A84FF;'>normaescobar.com</a><br>
                    <strong>To get in touch with me or to check out my previous work.</strong>
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


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
