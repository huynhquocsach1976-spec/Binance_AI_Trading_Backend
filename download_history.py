import os
import io
import zipfile
import requests
import pandas as pd

PAIR = "XBTUSD"
INTERVAL = "60"

OUTPUT_DIR = "historical"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "XBTUSD_60.csv")

# Lấy khoảng 90 ngày dữ liệu 1H
# 90 ngày ≈ 2160 candles
DAYS = 90

BASE_URL = "https://www.cryptodatadownload.com/cdd"


def download_csv():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    url = f"{BASE_URL}/Kraken_{PAIR}_{INTERVAL}.csv"

    print("=" * 70)
    print("DOWNLOADING HISTORICAL DATA")
    print("=" * 70)
    print("URL:", url)

    response = requests.get(
        url,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    print("HTTP:", response.status_code)

    response.raise_for_status()

    content = response.content

    # Kiểm tra ZIP
    if content[:2] == b"PK":
        print("Detected ZIP file")

        with zipfile.ZipFile(io.BytesIO(content)) as z:
            files = z.namelist()

            print("Files:")
            for f in files:
                print(" -", f)

            csv_files = [
                f for f in files
                if f.lower().endswith(".csv")
            ]

            if not csv_files:
                raise RuntimeError("Không tìm thấy CSV trong ZIP")

            with z.open(csv_files[0]) as f:
                df = pd.read_csv(f)

    else:
        print("Detected CSV file")

        text = content.decode("utf-8", errors="ignore")

        # CryptoDataDownload thường có vài dòng header
        df = pd.read_csv(
            io.StringIO(text),
            skiprows=1
        )

    print()
    print("Original columns:")
    print(list(df.columns))

    print()
    print("Original candles:", len(df))

    # Chuẩn hóa tên cột
    columns = {str(c).strip().lower(): c for c in df.columns}

    def find_column(names):
        for name in names:
            if name in columns:
                return columns[name]
        return None

    timestamp_col = find_column([
        "unix",
        "timestamp",
        "date"
    ])

    open_col = find_column(["open"])
    high_col = find_column(["high"])
    low_col = find_column(["low"])
    close_col = find_column(["close"])
    volume_col = find_column([
        "volume xbt",
        "volume",
        "volume btc"
    ])
    trades_col = find_column([
        "tradecount",
        "trades",
        "trade count"
    ])

    required = {
        "timestamp": timestamp_col,
        "open": open_col,
        "high": high_col,
        "low": low_col,
        "close": close_col,
        "volume": volume_col,
    }

    missing = [
        key for key, value in required.items()
        if value is None
    ]

    if missing:
        raise RuntimeError(
            f"Thiếu cột dữ liệu: {missing}"
        )

    result = pd.DataFrame()

    result["timestamp"] = pd.to_numeric(
        df[timestamp_col],
        errors="coerce"
    )

    result["open"] = pd.to_numeric(
        df[open_col],
        errors="coerce"
    )

    result["high"] = pd.to_numeric(
        df[high_col],
        errors="coerce"
    )

    result["low"] = pd.to_numeric(
        df[low_col],
        errors="coerce"
    )

    result["close"] = pd.to_numeric(
        df[close_col],
        errors="coerce"
    )

    result["volume"] = pd.to_numeric(
        df[volume_col],
        errors="coerce"
    )

    if trades_col:
        result["trades"] = pd.to_numeric(
            df[trades_col],
            errors="coerce"
        ).fillna(1)
    else:
        # Nếu nguồn không có trades,
        # dùng 1 để không phá Signal v1.6.1
        result["trades"] = 1

    result = result.dropna(
        subset=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]
    )

    # Timestamp phải là Unix seconds
    result["timestamp"] = result["timestamp"].astype("int64")

    # Nếu timestamp đang ở milliseconds
    if result["timestamp"].max() > 10_000_000_000:
        result["timestamp"] = (
            result["timestamp"] // 1000
        )

    result = result.sort_values("timestamp")

    result = result.drop_duplicates(
        subset=["timestamp"]
    )

    # Chỉ lấy dữ liệu gần nhất cần thiết
    target = DAYS * 24

    if len(result) > target:
        result = result.tail(target)

    result = result[
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

    result.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print()
    print("=" * 70)
    print("DOWNLOAD COMPLETED")
    print("=" * 70)
    print("Output:", OUTPUT_FILE)
    print("Candles:", len(result))

    if len(result) > 0:
        first = pd.to_datetime(
            result.iloc[0]["timestamp"],
            unit="s",
            utc=True
        )

        last = pd.to_datetime(
            result.iloc[-1]["timestamp"],
            unit="s",
            utc=True
        )

        print("From:", first)
        print("To:  ", last)

    print()
    print(result.head())
    print()
    print(result.tail())

    if len(result) < 1440:
        raise RuntimeError(
            f"Chỉ có {len(result)} candles, "
            f"cần ít nhất 1440"
        )


if __name__ == "__main__":
    download_csv()
