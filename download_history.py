import io
import os
import zipfile
import requests
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

SYMBOL = "XBTUSD"
TIMEFRAME = "60"

OUTPUT_DIR = "historical"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    f"{SYMBOL}_{TIMEFRAME}.csv"
)

# Cần ít nhất 2880 candles cho Backtest v1.2
MIN_CANDLES = 2880

# Lấy dư dữ liệu để an toàn
TARGET_CANDLES = 4000

# Kraken quarterly OHLCVT archives
QUARTERS = [
    "2026Q1",
    "2026Q2",
    "2026Q3",
    "2025Q4",
]

BASE_URL = "https://assets.kraken.com/api/0/public/OHLCVT"


# ============================================================
# DOWNLOAD
# ============================================================

def download_quarter(quarter):
    """
    Download Kraken quarterly OHLCVT ZIP.

    Returns:
        bytes hoặc None
    """

    urls = [
        f"https://assets.kraken.com/spot/ohlcvt/{quarter}/Kraken_OHLCVT_{quarter}.zip",
        f"https://assets.kraken.com/spot/ohlcvt/{quarter}/Kraken_OHLCVT_{quarter}.zip",
        f"https://downloads.kraken.com/ohlcvt/Kraken_OHLCVT_{quarter}.zip",
    ]

    print()
    print("=" * 70)
    print(f"Downloading Kraken archive: {quarter}")
    print("=" * 70)

    for url in urls:

        print(f"Trying: {url}")

        try:
            response = requests.get(
                url,
                timeout=120
            )

            print(
                f"HTTP {response.status_code} - "
                f"{len(response.content):,} bytes"
            )

            if response.status_code == 200:

                print(f"SUCCESS: {quarter}")

                return response.content

        except Exception as e:

            print(
                f"Download error for {quarter}: {e}"
            )

    print(
        f"WARNING: Could not download {quarter}"
    )

    return None


# ============================================================
# FIND EXACT FILE
# ============================================================

def find_symbol_file(zip_bytes):

    """
    Find EXACT:

        XBTUSD_60.csv

    inside Kraken ZIP.

    Không dùng contains() để tránh lấy nhầm:
        AIXBTUSD_60.csv
        XBTUSD1_60.csv
        XBTUSDC_60.csv
        XBTUSDT_60.csv
    """

    with zipfile.ZipFile(
        io.BytesIO(zip_bytes)
    ) as z:

        names = z.namelist()

        target = f"{SYMBOL}_{TIMEFRAME}.csv"

        print()
        print("Searching exact file:")
        print(target)

        # Tìm basename chính xác
        matches = []

        for name in names:

            if os.path.basename(name) == target:

                matches.append(name)

        if not matches:

            print()
            print("ERROR: Exact file not found.")

            print()
            print("Possible XBTUSD files:")

            for name in names:

                base = os.path.basename(name)

                if (
                    "XBTUSD" in base
                    and base.endswith(".csv")
                ):

                    print("  ", name)

            return None

        selected = matches[0]

        print()
        print("Selected:")
        print(selected)

        data = z.read(selected)

        return data


# ============================================================
# READ CSV
# ============================================================

def read_kraken_csv(csv_bytes):

    """
    Kraken OHLCVT format:

    timestamp
    open
    high
    low
    close
    volume
    trades
    """

    columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trades",
    ]

    df = pd.read_csv(
        io.BytesIO(csv_bytes),
        header=None,
        names=columns
    )

    # Nếu file có header thì loại bỏ
    if len(df) > 0:

        first_value = str(
            df.iloc[0]["timestamp"]
        ).lower()

        if first_value == "timestamp":

            df = df.iloc[1:].copy()

    # Convert numeric
    for column in columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # Remove invalid rows
    df = df.dropna(
        subset=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trades",
        ]
    )

    # Remove duplicate timestamps
    df = df.drop_duplicates(
        subset=["timestamp"]
    )

    # Sort oldest -> newest
    df = df.sort_values(
        "timestamp"
    )

    return df.reset_index(
        drop=True
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("KRAKEN BTC 1H HISTORICAL DATA DOWNLOADER")
    print("=" * 70)

    print()
    print(f"Symbol        : {SYMBOL}")
    print(f"Timeframe     : {TIMEFRAME}")
    print(f"Minimum       : {MIN_CANDLES}")
    print(f"Target        : {TARGET_CANDLES}")
    print(f"Output        : {OUTPUT_FILE}")

    all_data = []

    # --------------------------------------------------------
    # Download quarterly archives
    # --------------------------------------------------------

    for quarter in QUARTERS:

        zip_bytes = download_quarter(
            quarter
        )

        if zip_bytes is None:

            continue

        csv_bytes = find_symbol_file(
            zip_bytes
        )

        if csv_bytes is None:

            continue

        try:

            df = read_kraken_csv(
                csv_bytes
            )

            print(
                f"{quarter}: "
                f"{len(df):,} candles"
            )

            if len(df) > 0:

                all_data.append(df)

        except Exception as e:

            print(
                f"ERROR reading {quarter}: {e}"
            )

    # --------------------------------------------------------
    # Check data
    # --------------------------------------------------------

    if not all_data:

        raise RuntimeError(
            "Không tải được dữ liệu XBTUSD_60.csv "
            "từ Kraken quarterly archives."
        )

    print()
    print("=" * 70)
    print("MERGING DATA")
    print("=" * 70)

    df = pd.concat(
        all_data,
        ignore_index=True
    )

    # Remove duplicates
    df = df.drop_duplicates(
        subset=["timestamp"]
    )

    # Sort
    df = df.sort_values(
        "timestamp"
    )

    df = df.reset_index(
        drop=True
    )

    print(
        f"Total merged candles: "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # Keep latest candles
    # --------------------------------------------------------

    if len(df) > TARGET_CANDLES:

        df = df.tail(
            TARGET_CANDLES
        ).copy()

    # --------------------------------------------------------
    # Final validation
    # --------------------------------------------------------

    actual = len(df)

    print()
    print("=" * 70)
    print("FINAL VALIDATION")
    print("=" * 70)

    print(
        f"Final candles: {actual:,}"
    )

    if actual < MIN_CANDLES:

        raise RuntimeError(
            f"Chỉ có {actual} candles, "
            f"cần ít nhất {MIN_CANDLES} candles."
        )

    # --------------------------------------------------------
    # Create output directory
    # --------------------------------------------------------

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Save CSV
    # --------------------------------------------------------

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print()
    print("=" * 70)
    print("SUCCESS")
    print("=" * 70)

    print(
        f"Saved: {OUTPUT_FILE}"
    )

    print(
        f"Candles: {len(df):,}"
    )

    print()
    print("Columns:")

    print(
        list(df.columns)
    )

    print()
    print("First candle:")

    print(
        df.iloc[0].to_dict()
    )

    print()
    print("Last candle:")

    print(
        df.iloc[-1].to_dict()
    )

    print()
    print("=" * 70)
    print(
        "Historical data is ready for Backtest v1.2"
    )
    print("=" * 70)


if __name__ == "__main__":

    main()
