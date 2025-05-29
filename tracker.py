import requests
import sqlite3
import pandas as pd
import time
from pathlib import Path

# Constants
FUND_ADDRESS = "3D3J5tQ5trfZnzDwSozgCTY73PmfuybSuj"
TX_API_URL = f"https://mempool.space/api/address/{FUND_ADDRESS}/txs"
PRICE_API_URL = "https://mempool.space/api/v1/historical-price"
TX_DB_PATH = "txs.db"
PRICE_DB_PATH = "prices.db"

def fetchLivePrice():
    res = requests.get("https://mempool.space/api/v1/prices")
    if res.status_code != 200:
        raise Exception(f"Live price fetch failed: {res.status_code}")
    return res.json()["CAD"]


def fetchTxs():
    Path(TX_DB_PATH).touch(exist_ok=True)
    conn = sqlite3.connect(TX_DB_PATH)
    cursor = conn.cursor()

    # Create transactions table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            txid TEXT PRIMARY KEY,
            blockHeight INTEGER,
            blockTime INTEGER,
            btcValue REAL
        )
    """)

    # Create metadata table to store last seen txid
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()

    # Get the last seen txid from metadata
    cursor.execute("SELECT value FROM metadata WHERE key = 'lastSeenTxid'")
    row = cursor.fetchone()
    lastSeenTxid = row[0] if row else None

    allTxs = []
    seenTxs = set(r[0] for r in cursor.execute("SELECT txid FROM transactions"))
    nextTxid = lastSeenTxid

    while True:
        url = TX_API_URL
        if nextTxid:
            url += f"?after_txid={nextTxid}"

        res = requests.get(url)
        if res.status_code != 200:
            print(f"Failed: {res.status_code}")
            break

        data = res.json()
        if not data:
            break

        newTxids = []

        for tx in data:
            txid = tx["txid"]
            if txid in seenTxs:
                continue

            block = tx.get("status", {})
            blockHeight = block.get("block_height")
            blockTime = block.get("block_time")

            btcValue = sum(
                vout["value"]
                for vout in tx.get("vout", [])
                if vout.get("scriptpubkey_address") == FUND_ADDRESS
            )

            allTxs.append((txid, blockHeight, blockTime, btcValue))
            newTxids.append(txid)
            seenTxs.add(txid)

        if newTxids:
            nextTxid = data[-1]["txid"]
        else:
            break

        time.sleep(0.5)

    # Save new transactions
    if allTxs:
        cursor.executemany("""
            INSERT OR IGNORE INTO transactions (txid, blockHeight, blockTime, btcValue)
            VALUES (?, ?, ?, ?)
        """, allTxs)

        # Update lastSeenTxid in metadata table
        cursor.execute("""
            INSERT INTO metadata (key, value) VALUES ('lastSeenTxid', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (nextTxid,))

        conn.commit()

    df = pd.read_sql("SELECT * FROM transactions", conn)
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
        raise Exception(f"Price fetch failed: {res.status_code}")

    priceCAD = res.json()["prices"][0]["CAD"]
    cursor.execute("INSERT OR IGNORE INTO prices (blockTime, priceCAD) VALUES (?, ?)", (blockTime, priceCAD))
    conn.commit()
    conn.close()
    return priceCAD

txs = fetchTxs()
livePrice = fetchLivePrice()
txs["priceCAD"] = txs["blockTime"].apply(fetchPrice)
txs["btcValue"] = txs["btcValue"] / 1e8
txs["cadValue"] = txs["btcValue"] * txs["priceCAD"]
txs["date"] = pd.to_datetime(txs["blockTime"], unit="s").dt.strftime("%Y-%m-%d")
txs["cadCurrentValue"] = txs["btcValue"] * livePrice
txs["pnlCad"] = txs["cadCurrentValue"] - txs["cadValue"]
txs["pnlPercent"] = (txs["pnlCad"] / txs["cadValue"]) * 100

print(txs)

