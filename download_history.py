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


def fetch_ohlc(pair, interval, since=None):
    params = {
        "pair": pair,
        "interval": interval,
    }

    if since is not None:
        params["since"] = since

    print(f"Đang tải dữ liệu: since={since}")

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

    rows = result[pair_key]

    return rows, result.get("last")


def convert_rows(rows):
    data = []

    for row in rows:
        data.append({
            "timestamp": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[6]),
            "trades": int(row[7]),
        })

    return data


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_rows = []

    # Lần đầu lấy dữ liệu hiện tại
    rows, last = fetch_ohlc(PAIR, INTERVAL)

    converted = convert_rows(rows)
    all_rows.extend(converted)

    print(f"Đã lấy: {len(converted)} nến")

    # Kraken giới hạn số lượng trả về.
    # Tiếp tục lùi về quá khứ.
    while len(all_rows) < TARGET_CANDLES:

        oldest_timestamp = min(
            row["timestamp"]
            for row in all_rows
        )

        # Lùi trước nến cũ nhất 720 nến
        since = oldest_timestamp - (720 * 60)

        rows, _ = fetch_ohlc(
            PAIR,
            INTERVAL,
            since=since
        )

        if not rows:
            print("Không còn dữ liệu.")
            break

        converted = convert_rows(rows)

        print(
            f"Đợt mới: {len(converted)} nến | "
            f"Tổng trước lọc: {len(all_rows) + len(converted)}"
        )

        all_rows.extend(converted)

        # Tránh gọi API quá nhanh
        time.sleep(1)

        # Nếu API trả dữ liệu quá ít thì dừng
        if len(converted) < 10:
            break

    # Xóa timestamp trùng
    unique = {}

    for row in all_rows:
        unique[row["timestamp"]] = row

    all_rows = list(unique.values())

    # Sắp xếp từ cũ -> mới
    all_rows.sort(
        key=lambda x: x["timestamp"]
    )

    # Chỉ giữ TARGET_CANDLES nến cuối cùng
    if len(all_rows) > TARGET_CANDLES:
        all_rows = all_rows[-TARGET_CANDLES:]

    df = pd.DataFrame(all_rows)

    # Đảm bảo đúng thứ tự cột
    df = df[
        [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trades",
        ]
    ]

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print()
    print("=" * 60)
    print("HOÀN TẤT")
    print("=" * 60)
    print(f"File: {OUTPUT_FILE}")
    print(f"Số nến: {len(df)}")

    if len(df) > 0:
        first_time = datetime.fromtimestamp(
            int(df.iloc[0]["timestamp"]),
            tz=timezone.utc
        )

        last_time = datetime.fromtimestamp(
            int(df.iloc[-1]["timestamp"]),
            tz=timezone.utc
        )

        print(f"Từ: {first_time}")
        print(f"Đến: {last_time}")

    print()
    print("5 dòng đầu:")
    print(df.head())

    print()
    print("5 dòng cuối:")
    print(df.tail())


if __name__ == "__main__":
    main()
