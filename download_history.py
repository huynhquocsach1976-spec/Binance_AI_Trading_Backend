import os
import io
import zipfile
import requests
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

OUTPUT_DIR = "historical"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "XBTUSD_60.csv"
)

# Kraken quarterly historical OHLCVT
# Q3/2026 covers July -> September 2026,
# enough for more than 1440 hourly candles.
DOWNLOAD_URL = (
    "https://assets.kraken.com/"
    "marketing/institutions/"
    "Kraken_OHLCVT_2026Q3.zip"
)

MIN_CANDLES = 1440


# ============================================================
# DOWNLOAD
# ============================================================

def download_file(url):
    print("=" * 70)
    print("DOWNLOAD KRAKEN HISTORICAL OHLCVT")
    print("=" * 70)

    print("URL:")
    print(url)
    print()

    response = requests.get(
        url,
        timeout=180,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    print("HTTP:", response.status_code)
    print(
        "Downloaded:",
        round(len(response.content) / 1024 / 1024, 2),
        "MB"
    )

    response.raise_for_status()

    return response.content


# ============================================================
# FIND XBTUSD 60 MINUTE CSV
# ============================================================

def find_xbtusd_60(zip_file):
    names = zip_file.namelist()

    print()
    print("=" * 70)
    print("FILES INSIDE ZIP")
    print("=" * 70)

    for name in names:
        print(name)

    print()
    print("=" * 70)
    print("SEARCHING XBTUSD 60 MINUTE FILE")
    print("=" * 70)

    candidates = []

    for name in names:
        lower = name.lower()

        if not lower.endswith(".csv"):
            continue

        if "xbtusd" not in lower:
            continue

        # Kraken filenames can vary slightly.
        # Look for 60-minute / 60 interval.
        if (
            "_60" in lower
            or "-60" in lower
            or "60.csv" in lower
        ):
            candidates.append(name)

    if not candidates:
        raise RuntimeError(
            "Không tìm thấy file XBTUSD 60 phút trong ZIP."
        )

    print("Candidates:")

    for name in candidates:
        print(" -", name)

    # Prefer a filename ending with 60.csv
    for name in candidates:
        if name.lower().endswith("60.csv"):
            print()
            print("Selected:", name)
            return name

    print()
    print("Selected:", candidates[0])

    return candidates[0]


# ============================================================
# READ KRAKEN CSV
# ============================================================

def read_kraken_csv(zip_file, filename):
    print()
    print("=" * 70)
    print("READING DATA")
    print("=" * 70)

    raw = zip_file.read(filename)

    print(
        "CSV size:",
        round(len(raw) / 1024 / 1024, 2),
        "MB"
    )

    # Kraken OHLCVT files do not include a header row.
    df = pd.read_csv(
        io.BytesIO(raw),
        header=None
    )

    print()
    print("Raw rows:", len(df))
    print("Raw columns:", len(df.columns))

    if len(df.columns) < 7:
        raise RuntimeError(
            f"CSV không đủ 7 cột. "
            f"Đang có {len(df.columns)} cột."
        )

    # Kraken format:
    #
    # timestamp
    # open
    # high
    # low
    # close
    # volume
    # trades
    #
    # Keep only first 7 columns.
    df = df.iloc[:, :7].copy()

    df.columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trades"
    ]

    return df


# ============================================================
# CLEAN DATA
# ============================================================

def clean_data(df):
    print()
    print("=" * 70)
    print("CLEANING DATA")
    print("=" * 70)

    numeric_columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trades"
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]
    )

    # Timestamp must be integer Unix seconds.
    df["timestamp"] = df["timestamp"].astype("int64")

    # Trades should be integer.
    df["trades"] = (
        df["trades"]
        .fillna(1)
        .astype("int64")
    )

    # Remove duplicates.
    df = df.drop_duplicates(
        subset=["timestamp"]
    )

    # Sort oldest -> newest.
    df = df.sort_values(
        "timestamp"
    )

    df = df.reset_index(drop=True)

    print("Clean candles:", len(df))

    return df


# ============================================================
# SAVE
# ============================================================

def save_data(df):
    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    # We only need enough history for Backtest v1.2.
    #
    # Keep the latest 2160 candles (~90 days).
    # This gives enough data for:
    #
    # 720
    # 1440
    # 2160
    #
    TARGET_CANDLES = 2160

    if len(df) > TARGET_CANDLES:
        df = df.tail(
            TARGET_CANDLES
        ).copy()

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

    return df


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        # ----------------------------------------------------
        # 1. Download ZIP
        # ----------------------------------------------------

        content = download_file(
            DOWNLOAD_URL
        )

        # ----------------------------------------------------
        # 2. Open ZIP
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("OPEN ZIP")
        print("=" * 70)

        with zipfile.ZipFile(
            io.BytesIO(content)
        ) as zip_file:

            # ------------------------------------------------
            # 3. Find XBTUSD 60m CSV
            # ------------------------------------------------

            filename = find_xbtusd_60(
                zip_file
            )

            # ------------------------------------------------
            # 4. Read
            # ------------------------------------------------

            df = read_kraken_csv(
                zip_file,
                filename
            )

        # ----------------------------------------------------
        # 5. Clean
        # ----------------------------------------------------

        df = clean_data(df)

        # ----------------------------------------------------
        # 6. Save
        # ----------------------------------------------------

        df = save_data(df)

        print()
        print("=" * 70)
        print("DOWNLOAD COMPLETED")
        print("=" * 70)

        print()
        print("Output:")
        print(OUTPUT_FILE)

        print()
        print("Candles:")
        print(len(df))

        if len(df) > 0:

            first_time = pd.to_datetime(
                df.iloc[0]["timestamp"],
                unit="s",
                utc=True
            )

            last_time = pd.to_datetime(
                df.iloc[-1]["timestamp"],
                unit="s",
                utc=True
            )

            print()
            print("From:")
            print(first_time)

            print()
            print("To:")
            print(last_time)

        print()
        print("=" * 70)
        print("FIRST 5")
        print("=" * 70)

        print(
            df.head().to_string(
                index=False
            )
        )

        print()
        print("=" * 70)
        print("LAST 5")
        print("=" * 70)

        print(
            df.tail().to_string(
                index=False
            )
        )

        # ----------------------------------------------------
        # 7. Validate
        # ----------------------------------------------------

        if len(df) < MIN_CANDLES:

            raise RuntimeError(
                f"Chỉ có {len(df)} candles, "
                f"cần ít nhất {MIN_CANDLES} candles."
            )

        print()
        print("=" * 70)
        print("VALIDATION PASSED")
        print("=" * 70)

        print(
            f"OK: {len(df)} candles >= "
            f"{MIN_CANDLES}"
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("DOWNLOAD FAILED")
        print("=" * 70)

        print(
            type(e).__name__ + ":",
            str(e)
        )

        raise


if __name__ == "__main__":
    main()
