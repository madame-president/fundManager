import requests, sqlite3, pandas as pd, time
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()  # Make sure to load the .env variables

FUND_ADDRESS = os.getenv("BITCOIN_ADDRESS")
if not FUND_ADDRESS:
    raise ValueError("Cannot detect address. Check .env file or upload secrets to Streamlit using TOML file.")

TX_API_URL = f"https://mempool.space/api/address/{FUND_ADDRESS}/txs"
PRICE_API_URL = "https://mempool.space/api/v1/historical-price"
TX_DB_PATH = "txs.db"
PRICE_DB_PATH = "prices.db"

def fetchLivePrice():
    print("[INFO] Fetching live price...")
    res = requests.get("https://mempool.space/api/v1/prices")
    print(f"[DEBUG] Status Code: {res.status_code}")
    if res.status_code != 200:
        raise Exception(f"Request failed: {res.status_code}")
    return res.json()["CAD"]

def fetchTxs():
    print("[INFO] Fetching transactions...")
    Path(TX_DB_PATH).touch(exist_ok=True)
    conn = sqlite3.connect(TX_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            txid TEXT PRIMARY KEY,
            blockHeight INTEGER,
            blockTime INTEGER,
            btcValue REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()

    seenTxs = set(r[0] for r in cursor.execute("SELECT txid FROM transactions"))

    print(f"[DEBUG] Making request to: {TX_API_URL}")
    res = requests.get(TX_API_URL)
    print(f"[DEBUG] Status Code: {res.status_code}")
    if res.status_code != 200:
        conn.close()
        raise Exception(f"[ERROR] Transaction request failed: {res.status_code}")

    data = res.json()
    newTxs = []

    for tx in data:
        txid = tx["txid"]
        if txid in seenTxs:
            continue

        status = tx.get("status", {})
        blockHeight = status.get("block_height")
        blockTime = status.get("block_time")

        if not blockHeight or not blockTime:
            print(f"[WARN] Skipping tx {txid} due to missing blockHeight or blockTime")
            continue

        print(f"[DEBUG] Processing tx {txid}: blockTime={blockTime}")

        btcValue = sum(
            vout["value"]
            for vout in tx.get("vout", [])
            if vout.get("scriptpubkey_address") == FUND_ADDRESS
        ) / 1e8

        newTxs.append((txid, blockHeight, blockTime, btcValue))

    if newTxs:
        print(f"[INFO] Inserting {len(newTxs)} new transactions...")
        cursor.executemany("""
            INSERT OR IGNORE INTO transactions (txid, blockHeight, blockTime, btcValue)
            VALUES (?, ?, ?, ?)
        """, newTxs)
        conn.commit()

    df = pd.read_sql("SELECT * FROM transactions ORDER BY blockTime DESC", conn)
    conn.close()
    return df

def fetchPrice(blockTime):
    print(f"[INFO] Fetching price for blockTime: {blockTime}")
    Path(PRICE_DB_PATH).touch(exist_ok=True)
    conn = sqlite3.connect(PRICE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            blockTime INTEGER PRIMARY KEY,
            priceCAD REAL
        )
    """)
    conn.commit()

    cursor.execute("SELECT priceCAD FROM prices WHERE blockTime = ?", (blockTime,))
    row = cursor.fetchone()
    if row:
        conn.close()
        print(f"[INFO] Price found in DB: {row[0]} CAD")
        return row[0]

    priceUrl = f"{PRICE_API_URL}?currency=CAD&timestamp={blockTime}"
    print(f"[DEBUG] Making request to: {priceUrl}")
    res = requests.get(priceUrl)
    print(f"[DEBUG] Status Code: {res.status_code}")
    if res.status_code != 200:
        conn.close()
        raise Exception(f"[ERROR] Price request failed for blockTime {blockTime}: {res.status_code}")

    try:
        priceCAD = res.json()["prices"][0]["CAD"]
    except Exception as e:
        print(f"[ERROR] Failed to parse price response: {res.text}")
        conn.close()
        raise e

    print(f"[INFO] Price fetched: {priceCAD} CAD")
    cursor.execute("INSERT OR IGNORE INTO prices (blockTime, priceCAD) VALUES (?, ?)", (blockTime, priceCAD))
    conn.commit()
    conn.close()
    return priceCAD

# Debug entry point
if __name__ == "__main__":
    try:
        df = fetchTxs()
        print(f"[INFO] {len(df)} total transactions found.")

        # Try fetching price for the latest 3 transactions
        for i, row in df.head(3).iterrows():
            price = fetchPrice(row['blockTime'])
            print(f"[RESULT] TX {row['txid'][:6]}... — BlockTime: {row['blockTime']} — Price: {price} CAD")

    except Exception as e:
        print(f"[FATAL ERROR] {e}")

