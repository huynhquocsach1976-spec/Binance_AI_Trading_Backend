import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone


PAIR = "XBTUSD"
INTERVAL = 60

OUTPUT_DIR = "historical"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "XBTUSD_60.csv")

TARGET_CANDLES = 3000

KRAKEN_URL = "https://api.kraken.com/0/public/OHLC"


def fetch_ohlc(pair, interval, since):
    params = {
        "pair": pair,
        "interval": interval,
        "since": since
    }

    response = requests.get(
        KRAKEN_URL,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if data.get("error"):
        raise RuntimeError(data["error"])

    result = data["result"]

    pair_key = next(
        key for key in result.keys()
        if key != "last"
    )

    return result[pair_key]


def convert_rows(rows):
    result = []

    for row in rows:
        result.append({
            "timestamp": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[6]),
            "trades": int(row[7])
        })

    return result


def main():

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_rows = []

    # =========================================================
    # Lấy mốc thời gian hiện tại
    # =========================================================

    now = int(datetime.now(timezone.utc).timestamp())

    # =========================================================
    # Kraken trả khoảng 720 candles/lần.
    # Ta lùi từng đoạn khoảng 700 giờ.
    # =========================================================

    since = now - (720 * 60)

    while len(all_rows) < TARGET_CANDLES:

        print(
            f"Downloading since "
            f"{datetime.fromtimestamp(since, tz=timezone.utc)}"
        )

        rows = fetch_ohlc(
            PAIR,
            INTERVAL,
            since
        )

        if not rows:
            print("Không còn dữ liệu.")
            break

        converted = convert_rows(rows)

        print(
            f"Received: {len(converted)} candles"
        )

        all_rows.extend(converted)

        # Lùi tiếp về quá khứ.
        #
        # Quan trọng:
        # lấy timestamp của candle đầu tiên
        # rồi lùi thêm 1 candle.
        #
        oldest = min(
            row["timestamp"]
            for row in converted
        )

        since = oldest - 60

        time.sleep(1)

        if len(converted) < 10:
            print("API trả quá ít dữ liệu, dừng.")
            break

    # =========================================================
    # Xóa candle trùng
    # =========================================================

    unique = {}

    for row in all_rows:
        unique[row["timestamp"]] = row

    all_rows = list(unique.values())

    # Cũ -> mới
    all_rows.sort(
        key=lambda x: x["timestamp"]
    )

    # =========================================================
    # Chỉ giữ TARGET_CANDLES
    # =========================================================

    if len(all_rows) > TARGET_CANDLES:
        all_rows = all_rows[-TARGET_CANDLES:]

    df = pd.DataFrame(all_rows)

    df = df[
        [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trades"
        ]
    ]

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # =========================================================
    # Thông tin kết quả
    # =========================================================

    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETED")
    print("=" * 60)

    print(f"File: {OUTPUT_FILE}")
    print(f"Candles: {len(df)}")

    if len(df) > 0:

        first_time = datetime.fromtimestamp(
            int(df.iloc[0]["timestamp"]),
            tz=timezone.utc
        )

        last_time = datetime.fromtimestamp(
            int(df.iloc[-1]["timestamp"]),
            tz=timezone.utc
        )

        print(f"From: {first_time}")
        print(f"To:   {last_time}")

    print()
    print(df.head())

    print()
    print(df.tail())


if __name__ == "__main__":
    main()
