import os
import io
import csv
import zipfile
import tempfile
from datetime import datetime, timezone

import requests

from backtest_engine import run_backtest


VERSION = "1.2.3"
TIMEFRAME = "1h"

PAIR_MAP = {
    "BTCUSDT": "XBTUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD",
}

ALLOWED_CANDLES = {
    720,
    1440,
    2160,
    2880,
}

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

KRAKEN_HISTORICAL_BASE = (
    "https://assets.kraken.com/marketing/institutions/"
)

# Có thể truyền thư mục dữ liệu lịch sử bằng biến môi trường:
#
# KRAKEN_HISTORICAL_DIR=/data/kraken
#
# Trong thư mục này có thể đặt:
#
# XBTUSD_60.csv
# ETHUSD_60.csv
# SOLUSD_60.csv
#
# Mỗi dòng:
# timestamp,open,high,low,close,volume,trades

HISTORICAL_DIR = os.getenv(
    "KRAKEN_HISTORICAL_DIR",
    os.path.join(os.path.dirname(__file__), "historical"),
)


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def normalize_symbol(symbol):
    return str(symbol).upper().replace("/", "").replace("-", "")


def get_pair(symbol):
    symbol = normalize_symbol(symbol)

    if symbol not in PAIR_MAP:
        raise ValueError(
            f"Symbol không được hỗ trợ: {symbol}. "
            f"Hỗ trợ: {', '.join(PAIR_MAP.keys())}"
        )

    return PAIR_MAP[symbol]


def validate_candle_count(candles):
    candles = safe_int(candles, 720)

    if candles not in ALLOWED_CANDLES:
        raise ValueError(
            f"candles phải là một trong: "
            f"{sorted(ALLOWED_CANDLES)}"
        )

    return candles


# ============================================================
# CONVERT KRAKEN DATA
# ============================================================

def calculate_vwap(candle_rows):
    """
    Tính VWAP tích lũy.

    Không sửa Signal v1.6.1.
    Chỉ tạo field vwap để engine nhận dữ liệu giống cấu trúc cũ.
    """

    cumulative_pv = 0.0
    cumulative_volume = 0.0

    result = []

    for row in candle_rows:
        close = safe_float(row["close"])
        high = safe_float(row["high"])
        low = safe_float(row["low"])
        volume = safe_float(row["volume"])

        typical_price = (
            high + low + close
        ) / 3.0

        cumulative_pv += (
            typical_price * volume
        )

        cumulative_volume += volume

        if cumulative_volume > 0:
            vwap = (
                cumulative_pv /
                cumulative_volume
            )
        else:
            vwap = close

        new_row = dict(row)
        new_row["vwap"] = vwap

        result.append(new_row)

    return result


def normalize_rows(rows):
    """
    Chuẩn hóa dữ liệu về format mà backtest_engine
    đang sử dụng.
    """

    result = []

    for row in rows:

        try:
            timestamp = safe_int(row["time"])

            if timestamp <= 0:
                continue

            open_price = safe_float(row["open"])
            high_price = safe_float(row["high"])
            low_price = safe_float(row["low"])
            close_price = safe_float(row["close"])
            volume = safe_float(row["volume"])
            trades = safe_int(row.get("trades", 0))

            if (
                open_price <= 0
                or high_price <= 0
                or low_price <= 0
                or close_price <= 0
            ):
                continue

            result.append(
                {
                    "time": timestamp,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                    "trades": trades,
                }
            )

        except Exception:
            continue

    result.sort(key=lambda x: x["time"])

    # Remove duplicate timestamps
    unique = {}

    for row in result:
        unique[row["time"]] = row

    result = list(unique.values())

    result.sort(key=lambda x: x["time"])

    return calculate_vwap(result)


# ============================================================
# LOCAL CSV
# ============================================================

def find_local_csv(symbol):
    pair = get_pair(symbol)

    filename = f"{pair}_60.csv"

    candidates = [
        os.path.join(
            HISTORICAL_DIR,
            filename,
        ),

        os.path.join(
            os.getcwd(),
            "historical",
            filename,
        ),

        os.path.join(
            os.getcwd(),
            filename,
        ),
    ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def load_local_csv(symbol, candle_count):
    """
    Đọc Kraken OHLCVT CSV.

    Format:
    timestamp,open,high,low,close,volume,trades
    """

    path = find_local_csv(symbol)

    if not path:
        return None

    rows = []

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as file:

            reader = csv.reader(file)

            for values in reader:

                if not values:
                    continue

                if len(values) < 7:
                    continue

                # Bỏ header nếu file có header
                try:
                    timestamp = int(float(values[0]))
                except Exception:
                    continue

                row = {
                    "time": timestamp,
                    "open": safe_float(values[1]),
                    "high": safe_float(values[2]),
                    "low": safe_float(values[3]),
                    "close": safe_float(values[4]),
                    "volume": safe_float(values[5]),
                    "trades": safe_int(values[6]),
                }

                rows.append(row)

        rows = normalize_rows(rows)

        if len(rows) < candle_count:
            return {
                "status": "insufficient",
                "rows": rows,
                "available": len(rows),
                "path": path,
            }

        return {
            "status": "ok",
            "rows": rows[-candle_count:],
            "available": len(rows),
            "path": path,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
            "rows": [],
            "available": 0,
            "path": path,
        }


# ============================================================
# KRAKEN REST OHLC
# ============================================================

def fetch_kraken_ohlc(symbol, candle_count):
    """
    Fallback API.

    Kraken REST OHLC hiện chỉ cung cấp tối đa
    khoảng 720 candles.

    Vì vậy hàm này KHÔNG giả vờ trả 1440.
    """

    pair = get_pair(symbol)

    params = {
        "pair": pair,
        "interval": 60,
    }

    response = requests.get(
        KRAKEN_OHLC_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("error"):
        raise RuntimeError(
            f"Kraken API error: {data['error']}"
        )

    result = data.get("result", {})

    pair_key = None

    for key in result.keys():
        if key != "last":
            pair_key = key
            break

    if not pair_key:
        raise RuntimeError(
            "Không tìm thấy dữ liệu OHLC từ Kraken."
        )

    raw_rows = result[pair_key]

    rows = []

    for item in raw_rows:

        if len(item) < 8:
            continue

        rows.append(
            {
                "time": safe_int(item[0]),
                "open": safe_float(item[1]),
                "high": safe_float(item[2]),
                "low": safe_float(item[3]),
                "close": safe_float(item[4]),
                "vwap": safe_float(item[5]),
                "volume": safe_float(item[6]),
                "trades": safe_int(item[7]),
            }
        )

    rows.sort(key=lambda x: x["time"])

    # Không lấy vượt quá số API thực tế
    rows = rows[-min(candle_count, len(rows)):]

    return rows


# ============================================================
# MAIN DATA LOADER
# ============================================================

def get_historical_candles(symbol, candle_count):
    """
    Quy tắc:

    1. Nếu có CSV OHLCVT local:
       dùng CSV.

    2. Nếu không có CSV và yêu cầu <=720:
       dùng Kraken REST OHLC.

    3. Nếu yêu cầu >720 nhưng không có CSV:
       trả lỗi rõ ràng.

    Không được giả mạo 1440 thành 720.
    """

    symbol = normalize_symbol(symbol)

    candle_count = validate_candle_count(
        candle_count
    )

    # --------------------------------------------------------
    # 1. LOCAL HISTORICAL DATA
    # --------------------------------------------------------

    local = load_local_csv(
        symbol,
        candle_count,
    )

    if local:

        if local["status"] == "ok":

            rows = local["rows"]

            return {
                "status": "ok",
                "source": "Kraken OHLCVT CSV",
                "symbol": symbol,
                "pair": get_pair(symbol),
                "requested_candles": candle_count,
                "actual_candles": len(rows),
                "rows": rows,
                "data_path": local["path"],
            }

        if local["status"] == "insufficient":

            # Không fallback API nếu cần >720.
            if candle_count > 720:

                return {
                    "status": "error",
                    "source": "Kraken OHLCVT CSV",
                    "symbol": symbol,
                    "pair": get_pair(symbol),
                    "requested_candles": candle_count,
                    "actual_candles": local["available"],
                    "message": (
                        "File OHLCVT local tồn tại nhưng "
                        "không đủ dữ liệu."
                    ),
                    "data_path": local["path"],
                }

    # --------------------------------------------------------
    # 2. KRAKEN REST API
    # --------------------------------------------------------

    if candle_count <= 720:

        rows = fetch_kraken_ohlc(
            symbol,
            candle_count,
        )

        return {
            "status": "ok",
            "source": "Kraken",
            "symbol": symbol,
            "pair": get_pair(symbol),
            "requested_candles": candle_count,
            "actual_candles": len(rows),
            "rows": rows,
        }

    # --------------------------------------------------------
    # 3. >720 WITHOUT HISTORICAL CSV
    # --------------------------------------------------------

    return {
        "status": "error",
        "source": "Kraken",
        "symbol": symbol,
        "pair": get_pair(symbol),
        "requested_candles": candle_count,
        "actual_candles": 0,
        "message": (
            "Kraken REST OHLC chỉ cung cấp tối đa "
            "720 candles. Muốn backtest "
            f"{candle_count} candles cần file "
            "Kraken OHLCVT lịch sử "
            f"{get_pair(symbol)}_60.csv."
        ),
    }


# ============================================================
# SUMMARY
# ============================================================

def build_summary(result):
    """
    Chuyển kết quả backtest_engine thành summary gọn.
    """

    if not isinstance(result, dict):
        return {
            "status": "error",
            "message": "Backtest result không hợp lệ.",
        }

    account = result.get("account", {})
    trades = result.get("trades", {})
    buy = result.get("buy", {})
    sell = result.get("sell", {})
    performance = result.get(
        "performance",
        {},
    )
    risk = result.get(
        "risk",
        {},
    )

    return {
        "account": {
            "initial_balance": account.get(
                "initial_balance",
                0,
            ),
            "final_balance": account.get(
                "final_balance",
                0,
            ),
            "total_profit": account.get(
                "total_profit",
                0,
            ),
            "total_return_percent": account.get(
                "total_return_percent",
                0,
            ),
        },

        "trades": {
            "total": trades.get(
                "total",
                0,
            ),
            "wins": trades.get(
                "wins",
                0,
            ),
            "losses": trades.get(
                "losses",
                0,
            ),
            "win_rate": trades.get(
                "win_rate",
                0,
            ),
        },

        "buy": {
            "trades": buy.get(
                "trades",
                0,
            ),
            "wins": buy.get(
                "wins",
                0,
            ),
            "losses": buy.get(
                "losses",
                0,
            ),
            "win_rate": buy.get(
                "win_rate",
                0,
            ),
        },

        "sell": {
            "trades": sell.get(
                "trades",
                0,
            ),
            "wins": sell.get(
                "wins",
                0,
            ),
            "losses": sell.get(
                "losses",
                0,
            ),
            "win_rate": sell.get(
                "win_rate",
                0,
            ),
        },

        "performance": {
            "average_win": performance.get(
                "average_win",
                0,
            ),
            "average_loss": performance.get(
                "average_loss",
                0,
            ),
            "profit_factor": performance.get(
                "profit_factor",
                0,
            ),
            "gross_profit": performance.get(
                "gross_profit",
                0,
            ),
            "gross_loss": performance.get(
                "gross_loss",
                0,
            ),
            "profit_before_fees": performance.get(
                "profit_before_fees",
                0,
            ),
            "total_fees": performance.get(
                "total_fees",
                0,
            ),
        },

        "risk": {
            "max_drawdown": risk.get(
                "max_drawdown",
                0,
            ),
            "max_drawdown_percent": risk.get(
                "max_drawdown_percent",
                0,
            ),
            "max_win_streak": risk.get(
                "max_win_streak",
                0,
            ),
            "max_loss_streak": risk.get(
                "max_loss_streak",
                0,
            ),
        },

        "settings": result.get(
            "settings",
            {},
        ),

        "equity_curve": result.get(
            "equity_curve",
            [],
        ),

        "trade_history": result.get(
            "trade_history",
            [],
        ),
    }


# ============================================================
# SINGLE SYMBOL BACKTEST
# ============================================================

def run_symbol_backtest(
    symbol,
    candle_count=720,
    candles=None,
):
    """
    Backtest một symbol.

    Hỗ trợ cả:
        candle_count=1440

    và:
        candles=1440

    để tránh lỗi keyword argument
    giữa main.py và backtest_v12.py.
    """

    symbol = normalize_symbol(symbol)

    if candles is not None:
        candle_count = candles

    candle_count = validate_candle_count(
        candle_count
    )

    data = get_historical_candles(
        symbol,
        candle_count,
    )

    if data["status"] != "ok":

        return {
            "status": "error",
            "version": VERSION,
            "symbol": symbol,
            "timeframe": TIMEFRAME,
            "requested_candles": candle_count,
            "actual_candles": data.get(
                "actual_candles",
                0,
            ),
            "source": data.get(
                "source",
                "Kraken",
            ),
            "message": data.get(
                "message",
                "Không lấy được dữ liệu.",
            ),
        }

    rows = data["rows"]

    if len(rows) < 100:

        return {
            "status": "error",
            "version": VERSION,
            "symbol": symbol,
            "timeframe": TIMEFRAME,
            "requested_candles": candle_count,
            "actual_candles": len(rows),
            "source": data["source"],
            "message": (
                "Không đủ dữ liệu để chạy backtest."
            ),
        }

    # --------------------------------------------------------
    # RUN ORIGINAL BACKTEST ENGINE
    # --------------------------------------------------------

    try:

        result = run_backtest(
            rows
        )

    except TypeError:

        # Một số phiên bản engine nhận data=
        result = run_backtest(
            data=rows
        )

    except Exception as exc:

        return {
            "status": "error",
            "version": VERSION,
            "symbol": symbol,
            "timeframe": TIMEFRAME,
            "requested_candles": candle_count,
            "actual_candles": len(rows),
            "source": data["source"],
            "message": (
                f"Lỗi backtest_engine: {exc}"
            ),
        }

    return {
        "status": "ok",
        "version": VERSION,
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "requested_candles": candle_count,
        "actual_candles": len(rows),
        "source": data["source"],
        "result": result,
    }


# ============================================================
# MULTI PERIOD
# ============================================================

def run_multi_period_backtest(
    symbol,
    periods=None,
):
    if periods is None:
        periods = [
            720,
            1440,
            2160,
            2880,
        ]

    results = []

    for period in periods:

        try:

            result = run_symbol_backtest(
                symbol,
                candle_count=period,
            )

            results.append(result)

        except Exception as exc:

            results.append(
                {
                    "status": "error",
                    "symbol": symbol,
                    "candles": period,
                    "message": str(exc),
                }
            )

    return {
        "status": "ok",
        "version": VERSION,
        "symbol": normalize_symbol(symbol),
        "timeframe": TIMEFRAME,
        "periods": results,
    }


# ============================================================
# MULTI SYMBOL
# ============================================================

def run_multi_backtest(
    symbols=None,
    periods=None,
):
    if symbols is None:
        symbols = [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
        ]

    if periods is None:
        periods = [
            720,
            1440,
            2160,
            2880,
        ]

    output = []

    for symbol in symbols:

        symbol = normalize_symbol(symbol)

        symbol_results = []

        for period in periods:

            try:

                result = run_symbol_backtest(
                    symbol,
                    candle_count=period,
                )

            except Exception as exc:

                result = {
                    "status": "error",
                    "version": VERSION,
                    "symbol": symbol,
                    "requested_candles": period,
                    "actual_candles": 0,
                    "message": str(exc),
                }

            symbol_results.append(result)

        output.append(
            {
                "symbol": symbol,
                "results": symbol_results,
            }
        )

    return {
        "status": "ok",
        "version": VERSION,
        "timeframe": TIMEFRAME,
        "symbols": output,
    }


# ============================================================
# SIMPLE TEST
# ============================================================

if __name__ == "__main__":

    print(
        f"Backtest v{VERSION}"
    )

    print(
        "Historical directory:",
        HISTORICAL_DIR,
    )

    for symbol in PAIR_MAP:

        print(
            symbol,
            "=>",
            get_pair(symbol),
        )

    print(
        "Allowed periods:",
        sorted(ALLOWED_CANDLES),
    )
