from fastapi import FastAPI
from datetime import datetime
from pydantic import BaseModel

import requests
import os
import csv

from ai_analyzer import analyze_market
from backtest_engine import run_backtest
from backtest_diagnostic_v16 import run_diagnostic

from backtest_v12 import (
    run_multi_backtest,
    build_summary,
    run_symbol_backtest,
)

from backtest_diagnostic import run_diagnostic

from backtest_diagnostic_v14 import (
    run_diagnostic_v14,
)

from backtest_filtered_v15 import (
    run_filtered_diagnostic_v15,
)

from backtest_parity_check_v15 import (
    run_parity_check,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Binance AI Trading Backend",
    description="AI Trading Backend - Signal v1.6.1 / Backtest / Diagnostic / Parity",
    version="1.5.0",
)


# ============================================================
# CONFIG
# ============================================================

PAIR_MAP = {
    "BTCUSDT": "XBTUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD",
}

KRAKEN_OHLC_URL = (
    "https://api.kraken.com/0/public/OHLC"
)

ALLOWED_CANDLES = [
    720,
    1440,
    2160,
    2880,
]


# ============================================================
# MODELS
# ============================================================

class AnalyzeRequest(BaseModel):
    symbol: str = "BTCUSDT"


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "ok",
        "message": "Binance AI Trading Backend đang chạy!",
        "version": "1.5.0",
        "strategy": "Signal v1.6.1",
        "docs": "/docs",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "version": "1.5.0",
        "message": "Backend hoạt động bình thường",
        "time": datetime.utcnow().isoformat(),
    }


# ============================================================
# PRICE
# ============================================================

@app.get("/backtest-diagnostic-v16/{symbol}")
def backtest_diagnostic_v16(
    symbol: str,
    candles: int = 2880
):
    try:

        # ----------------------------------------------------
        # GIỐNG CÁCH BACKTEST HIỆN TẠI:
        # dùng endpoint /history/{symbol}
        # hoặc hàm lấy historical data hiện có
        # ----------------------------------------------------

        data_result = get_history_data(
            symbol,
            candles
        )

        result = run_diagnostic(
            data_result
        )

        result["symbol"] = symbol.upper()

        result["candles"] = candles

        return result

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc)
        }
@app.get("/price/{symbol}")
def get_price(symbol: str):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        return {
            "status": "error",
            "message": (
                f"Symbol không hỗ trợ: {symbol}. "
                f"Hỗ trợ: {list(PAIR_MAP.keys())}"
            ),
        }

    pair = PAIR_MAP[symbol]

    try:

        response = requests.get(
            KRAKEN_OHLC_URL,
            params={
                "pair": pair,
                "interval": 60,
            },
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("error"):
            return {
                "status": "error",
                "message": data["error"],
            }

        result = data.get("result", {})

        pair_key = None

        for key in result.keys():
            if key != "last":
                pair_key = key
                break

        if not pair_key:
            return {
                "status": "error",
                "message": "Không tìm thấy dữ liệu Kraken.",
            }

        rows = result[pair_key]

        if not rows:
            return {
                "status": "error",
                "message": "Không có dữ liệu.",
            }

        row = rows[-1]

        return {
            "status": "ok",
            "symbol": symbol,
            "price": float(row[4]),
            "time": int(float(row[0])),
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# HISTORY
# ============================================================

@app.get("/history/{symbol}")
def get_history(
    symbol: str,
    candles: int = 720,
):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        return {
            "status": "error",
            "message": (
                f"Symbol không hỗ trợ: {symbol}"
            ),
        }

    if candles not in ALLOWED_CANDLES:
        return {
            "status": "error",
            "message": (
                f"candles phải là một trong: "
                f"{ALLOWED_CANDLES}"
            ),
        }

    pair = PAIR_MAP[symbol]

    try:

        response = requests.get(
            KRAKEN_OHLC_URL,
            params={
                "pair": pair,
                "interval": 60,
            },
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("error"):
            return {
                "status": "error",
                "message": data["error"],
            }

        result = data.get("result", {})

        pair_key = None

        for key in result.keys():
            if key != "last":
                pair_key = key
                break

        if not pair_key:
            return {
                "status": "error",
                "message": "Không tìm thấy dữ liệu.",
            }

        rows = result[pair_key]

        rows = rows[-candles:]

        output = []

        for row in rows:

            if len(row) < 8:
                continue

            output.append(
                {
                    "time": int(float(row[0])),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "vwap": float(row[5]),
                    "volume": float(row[6]),
                    "trades": int(float(row[7])),
                }
            )

        return {
            "status": "ok",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": len(output),
            "data": output,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# AI ANALYZE
# ============================================================

@app.post("/ai/analyze")
def ai_analyze(request: AnalyzeRequest):

    symbol = request.symbol.upper()

    try:

        result = analyze_market(
            symbol
        )

        return result

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# BACKTEST ORIGINAL
# ============================================================

@app.get("/backtest/{symbol}")
def backtest(
    symbol: str,
    candles: int = 720,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001,
):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        return {
            "status": "error",
            "message": f"Symbol không hỗ trợ: {symbol}",
        }

    try:

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
            "version": "1.0.0",
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
            "result": result,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# BACKTEST V12
# ============================================================

@app.get("/backtest-v12/{symbol}")
def backtest_v12(
    symbol: str,
    candles: int = 720,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001,
):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        return {
            "status": "error",
            "message": f"Symbol không hỗ trợ: {symbol}",
        }

    if candles not in ALLOWED_CANDLES:
        return {
            "status": "error",
            "message": (
                f"candles phải là một trong "
                f"{ALLOWED_CANDLES}"
            ),
        }

    try:

        result = run_symbol_backtest(
            symbol=symbol,
            candles=candles,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        return result

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# BACKTEST ALL
# ============================================================

@app.get("/backtest-all")
def backtest_all(
    candles: int = 720,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001,
):

    try:

        result = run_multi_backtest(
            candles=candles,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        return result

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# BACKTEST DIAGNOSTIC
# ============================================================

@app.get("/backtest-diagnostic/{symbol}")
def backtest_diagnostic(
    symbol: str,
    candles: int = 2880,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001,
):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        return {
            "status": "error",
            "message": f"Symbol không hỗ trợ: {symbol}",
        }

    try:

        data = get_backtest_candles(
            symbol,
            candles,
        )

        result = run_diagnostic(
            data,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        return {
            "status": "ok",
            "version": "1.0.0",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": len(data),
            "strategy": "Signal v1.6.1",
            "diagnostic": result,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# BACKTEST DIAGNOSTIC V14
# ============================================================

@app.get("/backtest-diagnostic-v14/{symbol}")
def backtest_diagnostic_v14(
    symbol: str,
    candles: int = 2880,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001,
):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        return {
            "status": "error",
            "message": f"Symbol không hỗ trợ: {symbol}",
        }

    try:

        data = get_backtest_candles(
            symbol,
            candles,
        )

        result = run_diagnostic_v14(
            data,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        return {
            "status": "ok",
            "version": "1.4.0",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": len(data),
            "strategy": "Signal v1.6.1",
            "diagnostic": result,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# LOAD FILTERED CANDLES
# ============================================================

def load_filtered_candles(
    symbol: str,
    candles_count: int,
):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        raise ValueError(
            f"Symbol không hỗ trợ: {symbol}"
        )

    if candles_count not in ALLOWED_CANDLES:
        raise ValueError(
            f"candles phải là một trong: "
            f"{ALLOWED_CANDLES}"
        )

    pair = PAIR_MAP[symbol]

    # ========================================================
    # 720 -> KRAKEN
    # ========================================================

    if candles_count == 720:

        response = requests.get(
            KRAKEN_OHLC_URL,
            params={
                "pair": pair,
                "interval": 60,
            },
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
                "Không tìm thấy pair data từ Kraken."
            )

        rows = result[pair_key]

        rows = rows[-candles_count:]

        output = []

        for row in rows:

            if len(row) < 8:
                continue

            output.append(
                {
                    "time": int(float(row[0])),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "vwap": float(row[5]),
                    "volume": float(row[6]),
                    "trades": int(float(row[7])),
                }
            )

        if len(output) < candles_count:
            raise RuntimeError(
                f"Kraken chỉ có {len(output)} candles, "
                f"cần {candles_count}."
            )

        return output[-candles_count:]

    # ========================================================
    # >720 -> LOCAL CSV
    # ========================================================

    csv_path = os.path.join(
        "historical",
        f"{pair}_60.csv",
    )

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Không tìm thấy file: {csv_path}"
        )

    output = []

    with open(
        csv_path,
        "r",
        encoding="utf-8",
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise RuntimeError(
                f"CSV không có header: {csv_path}"
            )

        headers = {
            h.strip().lower(): h
            for h in reader.fieldnames
            if h
        }

        def get_column(row, names):

            for name in names:

                if name in headers:
                    value = row.get(
                        headers[name]
                    )

                    if value not in [
                        None,
                        "",
                    ]:
                        return value

            return None

        for row in reader:

            timestamp = get_column(
                row,
                [
                    "time",
                    "timestamp",
                    "ts",
                    "date",
                ],
            )

            open_price = get_column(
                row,
                ["open"],
            )

            high_price = get_column(
                row,
                ["high"],
            )

            low_price = get_column(
                row,
                ["low"],
            )

            close_price = get_column(
                row,
                ["close"],
            )

            vwap = get_column(
                row,
                ["vwap"],
            )

            volume = get_column(
                row,
                ["volume"],
            )

            trades = get_column(
                row,
                [
                    "trades",
                    "count",
                ],
            )

            if (
                open_price is None
                or high_price is None
                or low_price is None
                or close_price is None
                or volume is None
            ):
                continue

            if vwap is None:
                vwap = close_price

            if trades is None:
                trades = 0

            output.append(
                {
                    "time": int(float(timestamp))
                    if timestamp is not None
                    else 0,
                    "open": float(open_price),
                    "high": float(high_price),
                    "low": float(low_price),
                    "close": float(close_price),
                    "vwap": float(vwap),
                    "volume": float(volume),
                    "trades": int(float(trades)),
                }
            )

    if len(output) < candles_count:
        raise RuntimeError(
            f"CSV chỉ có {len(output)} candles, "
            f"cần {candles_count} candles"
        )

    return output[-candles_count:]


# ============================================================
# BACKTEST CANDLE HELPER
# ============================================================

def get_backtest_candles(
    symbol: str,
    candles: int,
):

    return load_filtered_candles(
        symbol,
        candles,
    )


# ============================================================
# FILTERED BACKTEST V15
# ============================================================

@app.get("/backtest-filtered-v15/{symbol}")
def backtest_filtered_v15(
    symbol: str,
    candles: int = 720,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001,
):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        return {
            "status": "error",
            "message": f"Symbol không hỗ trợ: {symbol}",
        }

    if candles not in ALLOWED_CANDLES:
        return {
            "status": "error",
            "message": (
                f"candles phải là một trong "
                f"{ALLOWED_CANDLES}"
            ),
        }

    try:

        data = load_filtered_candles(
            symbol,
            candles,
        )

        result = run_filtered_diagnostic_v15(
            data,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        return {
            "status": "ok",
            "version": "1.5.0",
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

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# ⭐ BACKTEST PARITY CHECK V15
# ============================================================

@app.get("/backtest-parity-v15/{symbol}")
def backtest_parity_v15(
    symbol: str,
    candles: int = 720,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001,
):

    """
    So sánh:

    backtest_engine.py

    VS

    backtest_filtered_v15.py BASELINE

    Hai engine nhận CHÍNH XÁC cùng một bộ candles.

    Mục tiêu:
    xác định Filtered Backtest v1.5 có parity
    với backtest_engine.py hay không.
    """

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        return {
            "status": "error",
            "message": f"Symbol không hỗ trợ: {symbol}",
        }

    if candles != 720:
        return {
            "status": "error",
            "message": (
                "Parity Check v1.5 hiện chỉ chạy "
                "với chính xác 720 candles."
            ),
        }

    try:

        # ====================================================
        # QUAN TRỌNG:
        # CHỈ LOAD DATA MỘT LẦN.
        #
        # Cả hai engine dùng cùng data.
        # ====================================================

        data = load_filtered_candles(
            symbol,
            candles,
        )

        if len(data) != candles:
            return {
                "status": "error",
                "message": (
                    f"Actual candles = {len(data)}, "
                    f"expected = {candles}"
                ),
            }

        # ====================================================
        # PARITY
        # ====================================================

        result = run_parity_check(
            data,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        return {
            "status": "ok",
            "version": "1.5.0",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": len(data),
            "source": "Kraken",
            "strategy": "Signal v1.6.1",
            "backtest_parity": result,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }
