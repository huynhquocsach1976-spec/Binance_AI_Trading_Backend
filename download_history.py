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

# Backtest v1.2 cần tối thiểu 2880 candles
MIN_CANDLES = 2880

# Lấy dư dữ liệu
TARGET_CANDLES = 4000

# Kraken official quarterly OHLCVT archives
QUARTERS = [
    "2026Q1",
    "2026Q2",
    "2026Q3",
]

BASE_URL = (
    "https://assets.kraken.com/"
    "marketing/institutions/"
)


# ============================================================
# DOWNLOAD QUARTER
# ============================================================

def download_quarter(quarter):

    url = (
        f"{BASE_URL}"
        f"Kraken_OHLCVT_{quarter}.zip"
    )

    print()
    print("=" * 70)
    print(f"Downloading: {quarter}")
    print("=" * 70)

    print("URL:")
    print(url)

    try:

        response = requests.get(
            url,
            timeout=180
        )

        print(
            f"HTTP {response.status_code}"
        )

        print(
            f"Size: {len(response.content):,} bytes"
        )

        if response.status_code != 200:

            print(
                f"WARNING: {quarter} download failed"
            )

            return None

        return response.content

    except Exception as e:

        print(
            f"ERROR downloading {quarter}: {e}"
        )

        return None


# ============================================================
# FIND EXACT CSV
# ============================================================

def find_symbol_file(zip_bytes):

    target = f"{SYMBOL}_{TIMEFRAME}.csv"

    print()
    print("Looking for exact file:")
    print(target)

    try:

        with zipfile.ZipFile(
            io.BytesIO(zip_bytes)
        ) as z:

            names = z.namelist()

            matches = []

            for name in names:

                if os.path.basename(name) == target:

                    matches.append(name)

            if not matches:

                print()
                print(
                    "ERROR: Exact file not found:"
                )

                print(target)

                print()
                print(
                    "Possible XBTUSD files:"
                )

                for name in names:

                    basename = os.path.basename(
                        name
                    )

                    if (
                        "XBTUSD" in basename
                        and basename.endswith(".csv")
                    ):

                        print(
                            "  ",
                            name
                        )

                return None

            selected = matches[0]

            print()
            print("Selected:")
            print(selected)

            return z.read(selected)

    except zipfile.BadZipFile:

        print(
            "ERROR: Downloaded file is not a valid ZIP."
        )

        return None

    except Exception as e:

        print(
            f"ERROR reading ZIP: {e}"
        )

        return None


# ============================================================
# READ KRAKEN CSV
# ============================================================

def read_kraken_csv(csv_bytes):

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

    # Remove possible header
    if len(df) > 0:

        first_value = str(
            df.iloc[0]["timestamp"]
        ).strip().lower()

        if first_value == "timestamp":

            df = df.iloc[1:].copy()

    # Convert numeric columns
    for column in columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # Remove invalid rows
    df = df.dropna(
        subset=columns
    )

    # Remove duplicate timestamps
    df = df.drop_duplicates(
        subset=["timestamp"]
    )

    # Sort
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
    print(f"Symbol       : {SYMBOL}")
    print(f"Timeframe    : {TIMEFRAME}")
    print(f"Minimum      : {MIN_CANDLES}")
    print(f"Target       : {TARGET_CANDLES}")
    print(f"Output       : {OUTPUT_FILE}")

    all_data = []

    # --------------------------------------------------------
    # Download quarterly files
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
                f"ERROR processing "
                f"{quarter}: {e}"
            )

    # --------------------------------------------------------
    # Validate downloaded data
    # --------------------------------------------------------

    if not all_data:

        raise RuntimeError(
            "Không tải được dữ liệu "
            "XBTUSD_60.csv từ Kraken."
        )

    # --------------------------------------------------------
    # Merge
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("MERGING QUARTERLY DATA")
    print("=" * 70)

    df = pd.concat(
        all_data,
        ignore_index=True
    )

    # Remove duplicate timestamps
    df = df.drop_duplicates(
        subset=["timestamp"]
    )

    # Sort oldest -> newest
    df = df.sort_values(
        "timestamp"
    )

    df = df.reset_index(
        drop=True
    )

    print(
        f"Merged candles: {len(df):,}"
    )

    # --------------------------------------------------------
    # Keep latest TARGET_CANDLES
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
    # Create directory
    # --------------------------------------------------------

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Save
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
        "BTC 1H historical data is ready."
    )
    print("=" * 70)


if __name__ == "__main__":

    main()
