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

TARGET_CANDLES = 2160
MIN_CANDLES = 1440

KRAKEN_BASE = (
    "https://assets.kraken.com/"
    "marketing/institutions/"
)

# Dùng 2 quý để chắc chắn đủ 1440 candles.
QUARTERS = [
    "2026Q2",
    "2026Q3",
]


# ============================================================
# DOWNLOAD
# ============================================================

def download_quarter(quarter):

    url = (
        KRAKEN_BASE
        + f"Kraken_OHLCVT_{quarter}.zip"
    )

    print()
    print("=" * 70)
    print(f"DOWNLOADING {quarter}")
    print("=" * 70)

    print("URL:")
    print(url)

    response = requests.get(
        url,
        timeout=180,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    print(
        "HTTP:",
        response.status_code
    )

    response.raise_for_status()

    print(
        "Downloaded:",
        round(
            len(response.content) / 1024 / 1024,
            2
        ),
        "MB"
    )

    return response.content


# ============================================================
# FIND EXACT XBTUSD FILE
# ============================================================

def find_exact_xbtusd_file(zip_file):

    names = zip_file.namelist()

    candidates = []

    for name in names:

        filename = os.path.basename(name)

        if filename == "XBTUSD_60.csv":
            candidates.append(name)

    if not candidates:

        print()
        print("Không tìm thấy XBTUSD_60.csv.")

        print()
        print("Các file XBTUSD liên quan:")

        for name in names:

            filename = os.path.basename(name)

            if "XBTUSD" in filename:
                print(
                    " -",
                    name
                )

        raise RuntimeError(
            "Không tìm thấy chính xác "
            "XBTUSD_60.csv trong ZIP."
        )

    if len(candidates) > 1:

        print()
        print("Các file trùng tên:")

        for name in candidates:
            print(
                " -",
                name
            )

    selected = candidates[0]

    print()
    print(
        "Selected exact file:",
        selected
    )

    return selected


# ============================================================
# READ CSV
# ============================================================

def read_xbtusd_60(content, quarter):

    print()
    print("=" * 70)
    print(
        f"READING XBTUSD_60.csv - {quarter}"
    )
    print("=" * 70)

    with zipfile.ZipFile(
        io.BytesIO(content)
    ) as zip_file:

        filename = find_exact_xbtusd_file(
            zip_file
        )

        raw = zip_file.read(
            filename
        )

    print(
        "CSV size:",
        round(
            len(raw) / 1024 / 1024,
            2
        ),
        "MB"
    )

    # Kraken OHLCVT không có header.
    df = pd.read_csv(
        io.BytesIO(raw),
        header=None
    )

    print(
        "Raw rows:",
        len(df)
    )

    print(
        "Raw columns:",
        len(df.columns)
    )

    if len(df.columns) < 7:

        raise RuntimeError(
            "XBTUSD_60.csv không đủ 7 cột."
        )

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
# CLEAN
# ============================================================

def clean_dataframe(df):

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

    df["timestamp"] = (
        df["timestamp"]
        .astype("int64")
    )

    df["trades"] = (
        df["trades"]
        .fillna(1)
        .astype("int64")
    )

    # Loại duplicate timestamp.
    df = df.drop_duplicates(
        subset=[
            "timestamp"
        ]
    )

    # Sắp xếp thời gian.
    df = df.sort_values(
        "timestamp"
    )

    df = df.reset_index(
        drop=True
    )

    return df


# ============================================================
# MAIN
# ============================================================

def main():

    all_data = []

    # --------------------------------------------------------
    # Download Q2 + Q3
    # --------------------------------------------------------

    for quarter in QUARTERS:

        content = download_quarter(
            quarter
        )

        df = read_xbtusd_60(
            content,
            quarter
        )

        df = clean_dataframe(
            df
        )

        print(
            f"{quarter} candles:",
            len(df)
        )

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

            print(
                "From:",
                first_time
            )

            print(
                "To:",
                last_time
            )

        all_data.append(df)

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("COMBINING QUARTERS")
    print("=" * 70)

    df = pd.concat(
        all_data,
        ignore_index=True
    )

    print(
        "Before duplicate removal:",
        len(df)
    )

    df = clean_dataframe(
        df
    )

    print(
        "After duplicate removal:",
        len(df)
    )

    # --------------------------------------------------------
    # Keep latest 2160 candles
    # --------------------------------------------------------

    if len(df) > TARGET_CANDLES:

        df = df.tail(
            TARGET_CANDLES
        ).copy()

        df = df.reset_index(
            drop=True
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

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

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DOWNLOAD COMPLETED")
    print("=" * 70)

    print()
    print(
        "Output:",
        OUTPUT_FILE
    )

    print(
        "Candles:",
        len(df)
    )

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
        print(
            "From:",
            first_time
        )

        print(
            "To:",
            last_time
        )

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

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

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


if __name__ == "__main__":
    main()
