from fastapi import FastAPI
from datetime import datetime
from pydantic import BaseModel

import requests
import os
import csv


# ============================================================
# IMPORTS
# ============================================================

from ai_analyzer import analyze_market

from backtest_engine import run_backtest

# Diagnostic v1.6
from backtest_diagnostic_v16 import (
    run_diagnostic as run_diagnostic_v16,
)

# Diagnostic cũ
from backtest_diagnostic import (
    run_diagnostic,
)

# Diagnostic v1.4
from backtest_diagnostic_v14 import (
    run_diagnostic_v14,
)

# Filtered Backtest v1.5
from backtest_filtered_v15 import (
    run_filtered_diagnostic_v15,
)

# Parity Check v1.5
from backtest_parity_check_v15 import (
    run_parity_check,
)

from backtest_v12 import (
    run_multi_backtest,
    build_summary,
    run_symbol_backtest,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Binance AI Trading Backend",
    description="AI Trading Backend - Signal v1.6.1",
    version="1.6.0",
)


# ============================================================
# CONFIG
# ============================================================

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

PAIR_MAP = {
    "BTCUSDT": "XBTUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD",
}

ALLOWED_CANDLES = [720, 1440, 2160, 2880]

HISTORICAL_DIR = "historical"


# ============================================================
# MODELS
# ============================================================

class AnalyzeRequest(BaseModel):
    symbol: str = "BTCUSDT"


# ============================================================
# BASIC
# ============================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Binance AI Trading Backend đang chạy!",
        "version": "1.6.0",
        "strategy": "Signal v1.6.1",
        "time": datetime.utcnow().isoformat(),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "message": "Backend hoạt động bình thường",
        "version": "1.6.0",
    }


# ============================================================
# SYMBOL VALIDATION
# ============================================================

def validate_symbol(symbol: str):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        raise ValueError(
            f"Symbol không được hỗ trợ: {symbol}. "
            f"Hỗ trợ: {list(PAIR_MAP.keys())}"
        )

    return symbol


# ============================================================
# KRAKEN OHLC
# ============================================================

def get_kraken_ohlc(
    symbol: str,
    interval: int = 60,
):
    symbol = validate_symbol(symbol)

    pair = PAIR_MAP[symbol]

    params = {
        "pair": pair,
        "interval": interval,
    }

    response = requests.get(
        KRAKEN_OHLC_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()

    if result.get("error"):
        raise ValueError(
            f"Kraken API error: {result['error']}"
        )

    result_data = result.get("result", {})

    candles = result_data.get(pair)

    if candles is None:

        # Kraken đôi khi trả key khác
        possible_keys = [
            key
            for key in result_data.keys()
            if key != "last"
        ]

        if possible_keys:
            candles = result_data[possible_keys[0]]

    if not candles:
        raise ValueError(
            f"Kraken không trả dữ liệu cho {symbol}"
        )

    return candles


# ============================================================
# CONVERT KRAKEN DATA
# ============================================================

def convert_kraken_candles(candles):

    data = []

    for row in candles:

        if len(row) < 7:
            continue

        try:

            timestamp = int(float(row[0]))

            open_price = float(row[1])
            high_price = float(row[2])
            low_price = float(row[3])
            close_price = float(row[4])
            volume = float(row[6])

            data.append(
                {
                    "time": datetime.utcfromtimestamp(
                        timestamp
                    ).isoformat(),

                    "timestamp": timestamp,

                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,

                    # Kraken OHLC có thể không có trades
                    "trades": 1.0,
                }
            )

        except Exception:
            continue

    return data


# ============================================================
# HISTORY - KRAKEN
# ============================================================

def get_history_data(
    symbol: str,
    candles: int = 720,
):

    symbol = validate_symbol(symbol)

    if candles not in ALLOWED_CANDLES:
        raise ValueError(
            f"candles phải là một trong: "
            f"{ALLOWED_CANDLES}"
        )

    raw = get_kraken_ohlc(
        symbol,
        interval=60,
    )

    data = convert_kraken_candles(raw)

    if not data:
        raise ValueError(
            "Không có dữ liệu lịch sử."
        )

    return data[-candles:]


# ============================================================
# GET PRICE
# ============================================================

@app.get("/price/{symbol}")
def get_price(symbol: str):

    try:

        symbol = validate_symbol(symbol)

        pair = PAIR_MAP[symbol]

        response = requests.get(
            "https://api.kraken.com/0/public/Ticker",
            params={
                "pair": pair
            },
            timeout=20,
        )

        response.raise_for_status()

        result = response.json()

        if result.get("error"):
            return {
                "status": "error",
                "message": result["error"],
            }

        ticker_data = result.get(
            "result",
            {}
        )

        if not ticker_data:
            raise ValueError(
                "Kraken không trả ticker."
            )

        ticker = next(
            iter(ticker_data.values())
        )

        return {
            "status": "ok",
            "symbol": symbol,
            "price": float(ticker["c"][0]),
            "source": "Kraken",
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# HISTORY ENDPOINT
# ============================================================

@app.get("/history/{symbol}")
def history(
    symbol: str,
    candles: int = 720,
):

    try:

        data = get_history_data(
            symbol,
            candles,
        )

        return {
            "status": "ok",
            "symbol": symbol.upper(),
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": len(data),
            "source": "Kraken",
            "data": data,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# AI ANALYZE
# ============================================================

@app.post("/ai/analyze")
def ai_analyze(request: AnalyzeRequest):

    try:

        symbol = validate_symbol(
            request.symbol
        )

        data = get_history_data(
            symbol,
            720,
        )

        result = analyze_market(
            data
        )

        return {
            "status": "ok",
            "symbol": symbol,
            "strategy": "Signal v1.6.1",
            "result": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# HISTORICAL CSV
# ============================================================

def load_csv_file(filepath: str):

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Không tìm thấy file CSV: {filepath}"
        )

    data = []

    with open(
        filepath,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            try:

                timestamp = (
                    row.get("timestamp")
                    or row.get("time")
                    or row.get("date")
                )

                open_price = row.get("open")
                high_price = row.get("high")
                low_price = row.get("low")
                close_price = row.get("close")
                volume = row.get("volume")

                if not all(
                    [
                        timestamp,
                        open_price,
                        high_price,
                        low_price,
                        close_price,
                    ]
                ):
                    continue

                try:
                    timestamp_value = float(
                        timestamp
                    )
                except Exception:
                    timestamp_value = timestamp

                try:
                    if float(timestamp_value) > 10_000_000_000:
                        timestamp_seconds = (
                            float(timestamp_value)
                            / 1000
                        )
                    else:
                        timestamp_seconds = float(
                            timestamp_value
                        )

                    time_value = datetime.utcfromtimestamp(
                        timestamp_seconds
                    ).isoformat()

                except Exception:
                    time_value = str(timestamp)

                data.append(
                    {
                        "time": time_value,
                        "timestamp": timestamp_value,

                        "open": float(open_price),
                        "high": float(high_price),
                        "low": float(low_price),
                        "close": float(close_price),

                        "volume": float(
                            volume or 0
                        ),

                        "trades": float(
                            row.get("trades")
                            or row.get("count")
                            or 1
                        ),
                    }
                )

            except Exception:
                continue

    if not data:
        raise ValueError(
            f"CSV không có dữ liệu hợp lệ: {filepath}"
        )

    return data


# ============================================================
# LOAD FILTERED CANDLES
# ============================================================

def load_filtered_candles(
    symbol: str,
    candles: int,
):

    symbol = validate_symbol(symbol)

    if candles not in ALLOWED_CANDLES:
        raise ValueError(
            f"candles phải là một trong: "
            f"{ALLOWED_CANDLES}"
        )

    # --------------------------------------------------------
    # 720 CANDLES -> KRAKEN
    # --------------------------------------------------------

    if candles == 720:

        data = get_history_data(
            symbol,
            720,
        )

        if len(data) < 720:
            raise ValueError(
                f"Kraken chỉ trả "
                f"{len(data)} candles, "
                f"cần 720 candles"
            )

        return data[-720:]

    # --------------------------------------------------------
    # >720 -> LOCAL CSV
    # --------------------------------------------------------

    pair = PAIR_MAP[symbol]

    filename = f"{pair}_60.csv"

    filepath = os.path.join(
        HISTORICAL_DIR,
        filename,
    )

    data = load_csv_file(
        filepath
    )

    if len(data) < candles:
        raise ValueError(
            f"CSV chỉ có {len(data)} candles, "
            f"cần {candles} candles"
        )

    return data[-candles:]


# ============================================================
# BACKTEST CANDLES
# ============================================================

def get_backtest_candles(
    symbol: str,
    candles: int = 2880,
):

    return load_filtered_candles(
        symbol,
        candles,
    )


# ============================================================
# BACKTEST
# ============================================================

@app.get("/backtest/{symbol}")
def backtest(
    symbol: str,
    candles: int = 720,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0002,
):

    try:

        symbol = validate_symbol(
            symbol
        )

        data = get_backtest_candles(
            symbol,
            candles,
        )

        result = run_backtest(
            data,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        return {
            "status": "ok",
            "version": "1.1.2",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": len(data),
            "source": (
                "Kraken"
                if candles == 720
                else "local_csv"
            ),
            "strategy": "Signal v1.6.1",
            "backtest": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# BACKTEST V1.2
# ============================================================

@app.get("/backtest-v12/{symbol}")
def backtest_v12(
    symbol: str,
    candles: int = 720,
):

    try:

        symbol = validate_symbol(
            symbol
        )

        data = get_backtest_candles(
            symbol,
            candles,
        )

        result = run_symbol_backtest(
            symbol,
            data,
        )

        return {
            "status": "ok",
            "symbol": symbol,
            "candles": candles,
            "result": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# BACKTEST ALL
# ============================================================

@app.get("/backtest-all")
def backtest_all(
    initial_balance: float = 1000.0,
):

    try:

        result = run_multi_backtest(
            initial_balance=initial_balance
        )

        return {
            "status": "ok",
            "result": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# DIAGNOSTIC V1.3
# ============================================================

@app.get("/backtest-diagnostic/{symbol}")
def backtest_diagnostic(
    symbol: str,
    candles: int = 2880,
):

    try:

        symbol = validate_symbol(
            symbol
        )

        data = get_backtest_candles(
            symbol,
            candles,
        )

        result = run_diagnostic(
            data
        )

        result["symbol"] = symbol
        result["candles"] = candles

        return {
            "status": "ok",
            "version": "1.3.0",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": len(data),
            "source": (
                "Kraken"
                if candles == 720
                else "local_csv"
            ),
            "strategy": "Signal v1.6.1",
            "diagnostic": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# DIAGNOSTIC V1.4
# ============================================================

@app.get("/backtest-diagnostic-v14/{symbol}")
def backtest_diagnostic_v14(
    symbol: str,
    candles: int = 2880,
):

    try:

        symbol = validate_symbol(
            symbol
        )

        data = get_backtest_candles(
            symbol,
            candles,
        )

        result = run_diagnostic_v14(
            data
        )

        return {
            "status": "ok",
            "version": "1.4.0",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": len(data),
            "source": (
                "Kraken"
                if candles == 720
                else "local_csv"
            ),
            "strategy": "Signal v1.6.1",
            "diagnostic": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# FILTERED BACKTEST V1.5
# ============================================================

@app.get("/backtest-filtered-v15/{symbol}")
def backtest_filtered_v15(
    symbol: str,
    candles: int = 2880,
    mode: str = "BASELINE",
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0002,
):

    try:

        symbol = validate_symbol(
            symbol
        )

        data = get_backtest_candles(
            symbol,
            candles,
        )

        result = run_filtered_diagnostic_v15(
            data,
            mode=mode,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        return {
            "status": "ok",
            "version": "1.5.2",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": len(data),
            "source": (
                "Kraken"
                if candles == 720
                else "local_csv"
            ),
            "strategy": "Signal v1.6.1",
            "mode": mode,
            "backtest": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# PARITY CHECK V1.5
# ============================================================

@app.get("/backtest-parity-v15/{symbol}")
def backtest_parity_v15(
    symbol: str,
    candles: int = 720,
):

    try:

        symbol = validate_symbol(
            symbol
        )

        if candles != 720:

            raise ValueError(
                "Parity Check v1.5 "
                "hiện kiểm tra chính xác 720 candles."
            )

        data = get_backtest_candles(
            symbol,
            candles,
        )

        result = run_parity_check(
            data
        )

        return {
            "status": "ok",
            "version": "1.5.1",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": len(data),
            "source": "Kraken",
            "strategy": "Signal v1.6.1",
            "parity": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ============================================================
# DIAGNOSTIC V1.6
# BUY vs SELL
# ============================================================

@app.get("/backtest-diagnostic-v16/{symbol}")
def backtest_diagnostic_v16(
    symbol: str,
    candles: int = 2880,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0002,
):

    try:

        # ----------------------------------------------------
        # VALIDATE
        # ----------------------------------------------------

        symbol = validate_symbol(
            symbol
        )

        if candles not in ALLOWED_CANDLES:

            raise ValueError(
                f"candles phải là một trong: "
                f"{ALLOWED_CANDLES}"
            )

        # ----------------------------------------------------
        # LOAD DATA
        # ----------------------------------------------------

        data = get_backtest_candles(
            symbol,
            candles,
        )

        if len(data) < candles:

            raise ValueError(
                f"Chỉ có {len(data)} candles, "
                f"cần {candles} candles"
            )

        # ----------------------------------------------------
        # RUN DIAGNOSTIC V1.6
        # ----------------------------------------------------

        result = run_diagnostic_v16(
            data,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return {
            "status": "ok",

            "version": "1.6.0",

            "symbol": symbol,

            "timeframe": "1h",

            "candles": candles,

            "actual_candles": len(data),

            "source": (
                "Kraken"
                if candles == 720
                else "local_csv"
            ),

            "strategy": "Signal v1.6.1",

            "diagnostic": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }
