import os
import math
import requests
import pandas as pd
import numpy as np

from backtest_engine import run_backtest


VERSION = "1.2.3"


# =========================================================
# KRAKEN PAIR MAP
# =========================================================

PAIR_MAP = {

    "BTCUSDT": "XBTUSD",

    "ETHUSDT": "ETHUSD",

    "SOLUSDT": "SOLUSD",

}


# =========================================================
# ALLOWED CANDLE COUNTS
# =========================================================

ALLOWED_CANDLES = [

    720,

    1440,

    2160,

    2880

]


# =========================================================
# SAFE FLOAT
# =========================================================

def safe_float(value, default=0.0):

    try:

        value = float(value)

        if not math.isfinite(value):

            return float(default)

        return value

    except Exception:

        return float(default)


# =========================================================
# NATIVE JSON
# =========================================================

def native(value):

    if isinstance(value, dict):

        return {
            str(k): native(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple)):

        return [
            native(v)
            for v in value
        ]

    if isinstance(value, np.integer):

        return int(value)

    if isinstance(value, np.floating):

        value = float(value)

        if not math.isfinite(value):

            return None

        return value

    if isinstance(value, np.bool_):

        return bool(value)

    if isinstance(value, float):

        if not math.isfinite(value):

            return None

    return value


# =========================================================
# VWAP
# =========================================================

def calculate_vwap(df):

    df = df.copy()

    typical_price = (
        df["high"] +
        df["low"] +
        df["close"]
    ) / 3.0

    volume = pd.to_numeric(
        df["volume"],
        errors="coerce"
    ).fillna(0)

    cumulative_volume = (
        volume.cumsum()
    )

    cumulative_pv = (
        typical_price *
        volume
    ).cumsum()

    df["vwap"] = np.where(

        cumulative_volume > 0,

        cumulative_pv /
        cumulative_volume,

        typical_price

    )

    return df


# =========================================================
# NORMALIZE KRAKEN ROWS
# =========================================================

def normalize_rows(rows):

    normalized = []

    for row in rows:

        if isinstance(row, dict):

            normalized.append({

                "time": int(
                    safe_float(
                        row.get("time")
                    )
                ),

                "open": safe_float(
                    row.get("open")
                ),

                "high": safe_float(
                    row.get("high")
                ),

                "low": safe_float(
                    row.get("low")
                ),

                "close": safe_float(
                    row.get("close")
                ),

                "volume": safe_float(
                    row.get("volume")
                ),

                "trades": safe_float(
                    row.get("trades")
                )

            })

            continue

        # Kraken raw OHLC:
        # time, open, high, low, close,
        # vwap, volume, count

        if len(row) >= 8:

            normalized.append({

                "time": int(
                    safe_float(row[0])
                ),

                "open": safe_float(
                    row[1]
                ),

                "high": safe_float(
                    row[2]
                ),

                "low": safe_float(
                    row[3]
                ),

                "close": safe_float(
                    row[4]
                ),

                "volume": safe_float(
                    row[6]
                ),

                "trades": safe_float(
                    row[7]
                )

            })

    return normalized


# =========================================================
# FIND LOCAL CSV
# =========================================================

def find_local_csv(symbol):

    pair = PAIR_MAP.get(
        symbol.upper(),
        symbol.upper()
    )

    candidates = [

        os.path.join(
            "historical",
            f"{pair}_60.csv"
        ),

        os.path.join(
            "historical",
            f"{symbol.upper()}_60.csv"
        ),

        os.path.join(
            os.path.dirname(__file__),
            "historical",
            f"{pair}_60.csv"
        ),

        os.path.join(
            os.path.dirname(__file__),
            "historical",
            f"{symbol.upper()}_60.csv"
        )

    ]

    for path in candidates:

        if os.path.exists(path):

            return path

    return None


# =========================================================
# LOAD LOCAL CSV
# =========================================================

def load_local_csv(
    symbol,
    candles
):

    path = find_local_csv(
        symbol
    )

    if path is None:

        return {

            "status": "error",

            "message": (
                f"Không tìm thấy dữ liệu lịch sử "
                f"cho {symbol}. "
                f"Cần file historical/{PAIR_MAP.get(symbol, symbol)}_60.csv"
            )

        }

    try:

        df = pd.read_csv(
            path
        )

    except Exception as e:

        return {

            "status": "error",

            "message": (
                f"Không thể đọc CSV: {str(e)}"
            )

        }

    # -----------------------------------------------------
    # Normalize columns
    # -----------------------------------------------------

    rename_map = {}

    if (
        "timestamp" in df.columns
        and "time" not in df.columns
    ):

        rename_map["timestamp"] = "time"

    if (
        "Timestamp" in df.columns
        and "time" not in df.columns
    ):

        rename_map["Timestamp"] = "time"

    if rename_map:

        df = df.rename(
            columns=rename_map
        )

    required = [

        "time",
        "open",
        "high",
        "low",
        "close",
        "volume"

    ]

    for col in required:

        if col not in df.columns:

            return {

                "status": "error",

                "message": (
                    f"CSV thiếu column: {col}"
                )

            }

    if "trades" not in df.columns:

        if "count" in df.columns:

            df["trades"] = df["count"]

        else:

            df["trades"] = 0

    numeric_cols = [

        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trades"

    ]

    for col in numeric_cols:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "time",
            "open",
            "high",
            "low",
            "close"
        ]
    )

    df = df.sort_values(
        "time"
    )

    df = df.drop_duplicates(
        subset=["time"]
    )

    df = df.reset_index(
        drop=True
    )

    if len(df) < candles:

        return {

            "status": "error",

            "message": (
                f"CSV chỉ có {len(df)} candles, "
                f"cần {candles}"
            )

        }

    # Take latest requested candles

    df = df.tail(
        candles
    ).reset_index(
        drop=True
    )

    df = calculate_vwap(
        df
    )

    return {

        "status": "ok",

        "source": "local_csv",

        "file": path,

        "data": df

    }


# =========================================================
# FETCH KRAKEN OHLC
# =========================================================

def fetch_kraken_ohlc(
    symbol,
    interval=60
):

    pair = PAIR_MAP.get(
        symbol.upper()
    )

    if pair is None:

        return {

            "status": "error",

            "message": (
                f"Symbol chưa hỗ trợ: {symbol}"
            )

        }

    url = (
        "https://api.kraken.com/0/public/OHLC"
    )

    params = {

        "pair": pair,

        "interval": interval

    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        payload = response.json()

    except Exception as e:

        return {

            "status": "error",

            "message": (
                f"Kraken request error: {str(e)}"
            )

        }

    if payload.get("error"):

        return {

            "status": "error",

            "message": str(
                payload.get("error")
            )

        }

    result = payload.get(
        "result",
        {}
    )

    pair_key = None

    for key in result.keys():

        if key != "last":

            pair_key = key

            break

    if pair_key is None:

        return {

            "status": "error",

            "message": (
                "Kraken không trả về candle"
            )

        }

    rows = result.get(
        pair_key,
        []
    )

    normalized = normalize_rows(
        rows
    )

    if not normalized:

        return {

            "status": "error",

            "message": (
                "Không có dữ liệu OHLC"
            )

        }

    df = pd.DataFrame(
        normalized
    )

    df = df.sort_values(
        "time"
    )

    df = df.drop_duplicates(
        subset=["time"]
    )

    df = df.reset_index(
        drop=True
    )

    df = calculate_vwap(
        df
    )

    return {

        "status": "ok",

        "source": "Kraken",

        "actual_candles": len(df),

        "data": df

    }


# =========================================================
# GET HISTORICAL CANDLES
# =========================================================

def get_historical_candles(
    symbol,
    candles
):

    symbol = symbol.upper()

    candles = int(
        candles
    )

    if candles not in ALLOWED_CANDLES:

        return {

            "status": "error",

            "message": (
                f"candles phải là một trong "
                f"{ALLOWED_CANDLES}"
            )

        }

    # -----------------------------------------------------
    # Kraken can provide about 720 candles.
    # -----------------------------------------------------

    if candles <= 720:

        result = fetch_kraken_ohlc(
            symbol,
            interval=60
        )

        if result.get("status") != "ok":

            return result

        df = result["data"]

        if len(df) < candles:

            return {

                "status": "error",

                "message": (
                    f"Kraken chỉ trả về "
                    f"{len(df)} candles, "
                    f"cần {candles}"
                )

            }

        df = df.tail(
            candles
        ).reset_index(
            drop=True
        )

        return {

            "status": "ok",

            "source": "Kraken",

            "actual_candles": len(df),

            "data": df

        }

    # -----------------------------------------------------
    # >720 requires local historical CSV
    # -----------------------------------------------------

    return load_local_csv(
        symbol,
        candles
    )


# =========================================================
# BUILD SUMMARY
# =========================================================

def build_summary(
    result,
    symbol=None,
    period=None
):

    if not result:

        return {

            "status": "error",

            "message": "Backtest result rỗng"

        }

    summary = result.get(
        "summary",
        {}
    )

    output = {

        "status": result.get(
            "status",
            "ok"
        ),

        "version": VERSION,

        "strategy": result.get(
            "strategy",
            "Signal v1.6.1"
        ),

        "symbol": symbol,

        "period": period,

        "summary": summary

    }

    return native(
        output
    )


# =========================================================
# RUN SYMBOL BACKTEST
# =========================================================

def run_symbol_backtest(
    symbol,
    candles=720,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):

    symbol = symbol.upper()

    candles = int(
        candles
    )

    historical = get_historical_candles(
        symbol,
        candles
    )

    if historical.get("status") != "ok":

        return historical

    df = historical["data"]

    rows = df.to_dict(
        orient="records"
    )

    try:

        result = run_backtest(

            rows,

            initial_balance=initial_balance,

            fee_rate=fee_rate,

            slippage=slippage

        )

    except TypeError:

        # Compatibility fallback

        result = run_backtest(
            rows
        )

    except Exception as e:

        return {

            "status": "error",

            "symbol": symbol,

            "message": (
                f"Backtest error: {str(e)}"
            )

        }

    return {

        "status": "ok",

        "version": VERSION,

        "symbol": symbol,

        "candles": len(df),

        "source": historical.get(
            "source"
        ),

        "result": native(
            result
        )

    }


# =========================================================
# MULTI PERIOD
# =========================================================

def run_multi_period_backtest(
    symbol,
    periods=None,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):

    if periods is None:

        periods = [

            720,

            1440,

            2160,

            2880

        ]

    results = []

    for candles in periods:

        result = run_symbol_backtest(

            symbol,

            candles=candles,

            initial_balance=initial_balance,

            fee_rate=fee_rate,

            slippage=slippage

        )

        if result.get("status") == "ok":

            inner = result.get(
                "result",
                {}
            )

            summary = inner.get(
                "summary",
                {}
            )

            results.append({

                "candles": candles,

                "status": "ok",

                "source": result.get(
                    "source"
                ),

                "initial_balance":
                    summary.get(
                        "initial_balance"
                    ),

                "final_balance":
                    summary.get(
                        "final_balance"
                    ),

                "profit":
                    summary.get(
                        "profit"
                    ),

                "return_pct":
                    summary.get(
                        "return_pct"
                    ),

                "total_trades":
                    summary.get(
                        "total_trades"
                    ),

                "wins":
                    summary.get(
                        "wins"
                    ),

                "losses":
                    summary.get(
                        "losses"
                    ),

                "win_rate":
                    summary.get(
                        "win_rate"
                    ),

                "profit_factor":
                    summary.get(
                        "profit_factor"
                    ),

                "max_drawdown":
                    summary.get(
                        "max_drawdown"
                    ),

                "max_drawdown_pct":
                    summary.get(
                        "max_drawdown_pct"
                    )

            })

        else:

            results.append({

                "candles": candles,

                "status": "error",

                "message": result.get(
                    "message",
                    "Unknown error"
                )

            })

    return native({

        "status": "ok",

        "version": VERSION,

        "symbol": symbol.upper(),

        "strategy": "Signal v1.6.1",

        "periods": results

    })


# =========================================================
# MULTI SYMBOL
# =========================================================

def run_multi_backtest(
    symbols=None,
    periods=None,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):

    if symbols is None:

        symbols = [

            "BTCUSDT",

            "ETHUSDT",

            "SOLUSDT"

        ]

    if periods is None:

        periods = [

            720,

            1440,

            2160,

            2880

        ]

    all_results = []

    for symbol in symbols:

        result = run_multi_period_backtest(

            symbol,

            periods=periods,

            initial_balance=initial_balance,

            fee_rate=fee_rate,

            slippage=slippage

        )

        all_results.append(
            result
        )

    # -----------------------------------------------------
    # Overall statistics
    # -----------------------------------------------------

    successful = 0

    failed = 0

    total_profit = 0.0

    total_trades = 0

    total_wins = 0

    total_losses = 0

    for symbol_result in all_results:

        for period_result in symbol_result.get(
            "periods",
            []
        ):

            if period_result.get(
                "status"
            ) == "ok":

                successful += 1

                total_profit += safe_float(
                    period_result.get(
                        "profit"
                    )
                )

                total_trades += int(
                    period_result.get(
                        "total_trades"
                    ) or 0
                )

                total_wins += int(
                    period_result.get(
                        "wins"
                    ) or 0
                )

                total_losses += int(
                    period_result.get(
                        "losses"
                    ) or 0
                )

            else:

                failed += 1

    overall_win_rate = (

        total_wins /
        total_trades *
        100

        if total_trades > 0

        else 0.0

    )

    return native({

        "status": "ok",

        "version": VERSION,

        "strategy": "Signal v1.6.1",

        "symbols": symbols,

        "periods": periods,

        "overall": {

            "successful_tests":
                successful,

            "failed_tests":
                failed,

            "total_profit":
                total_profit,

            "total_trades":
                total_trades,

            "total_wins":
                total_wins,

            "total_losses":
                total_losses,

            "overall_win_rate":
                overall_win_rate

        },

        "results":
            all_results

    })


# =========================================================
# LOCAL TEST
# =========================================================

if __name__ == "__main__":

    print(
        "backtest_v12.py"
    )

    print(
        "VERSION:",
        VERSION
    )

    print(
        "PAIR_MAP:",
        PAIR_MAP
    )

    print(
        "ALLOWED_CANDLES:",
        ALLOWED_CANDLES
    )

    print(
        "run_multi_backtest = OK"
    )
