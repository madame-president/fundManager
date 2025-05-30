import requests, sqlite3, pandas as pd, time
from pathlib import Path
from dotenv import load_dotenv
import os

FUND_ADDRESS = os.getenv("BITCOIN_ADDRESS")
TX_API_URL = f"https://mempool.space/api/address/{FUND_ADDRESS}/txs"
PRICE_API_URL = "https://mempool.space/api/v1/historical-price"
TX_DB_PATH = "txs.db"
PRICE_DB_PATH = "prices.db"

def fetchLivePrice():
    res = requests.get("https://mempool.space/api/v1/prices")
    if res.status_code != 200:
        raise Exception(f"Request failed: {res.status_code}")
    return res.json()["CAD"]

def fetchTxs():
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

    res = requests.get(TX_API_URL)
    if res.status_code != 200:
        conn.close()
        raise Exception(f"Request failed: {res.status_code}")

    data = res.json()
    newTxs = []

    for tx in data:
        txid = tx["txid"]
        if txid in seenTxs:
            continue

        status = tx.get("status", {})
        blockHeight = status.get("block_height")
        blockTime = status.get("block_time")

        if blockHeight and blockTime:
            btcValue = sum(
                vout["value"]
                for vout in tx.get("vout", [])
                if vout.get("scriptpubkey_address") == FUND_ADDRESS
            ) / 1e8

            newTxs.append((txid, blockHeight, blockTime, btcValue))

    if newTxs:
        cursor.executemany("""
            INSERT OR IGNORE INTO transactions (txid, blockHeight, blockTime, btcValue)
            VALUES (?, ?, ?, ?)
        """, newTxs)
        conn.commit()

    df = pd.read_sql("SELECT * FROM transactions ORDER BY blockTime DESC", conn)
    conn.close()
    return df


def fetchPrice(blockTime):
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
        return row[0]

    res = requests.get(f"{PRICE_API_URL}?currency=CAD&timestamp={blockTime}")
    if res.status_code != 200:
        conn.close()
        raise Exception(f"Request failed: {res.status_code}")

    priceCAD = res.json()["prices"][0]["CAD"]
    cursor.execute("INSERT OR IGNORE INTO prices (blockTime, priceCAD) VALUES (?, ?)", (blockTime, priceCAD))
    conn.commit()
    conn.close()
    return priceCAD

