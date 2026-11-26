from fastapi import FastAPI
from datetime import datetime
from pydantic import BaseModel
import requests
import os
import csv

from ai_analyzer import analyze_market
from backtest_engine import run_backtest
from backtest_v12 import (
    run_multi_backtest,
    build_summary,
    run_symbol_backtest
)
from backtest_diagnostic import run_diagnostic
from backtest_diagnostic_v14 import run_diagnostic_v14
from backtest_filtered_v15 import run_filtered_diagnostic_v15


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Binance AI Trading Pro Backend",
    description="AI phân tích và backtest thị trường crypto",
    version="1.5.0"
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Binance AI Trading Pro Backend đang chạy!",
        "version": "1.5.0",
        "signal_version": "1.6.1",
        "time": datetime.now().isoformat()
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "message": "Backend đang hoạt động bình thường",
        "signal_version": "1.6.1",
        "backtest_version": "1.2.0",
        "diagnostic_version": "1.4.0",
        "filtered_backtest_version": "1.5.0"
    }


# ============================================================
# PRICE
# ============================================================

@app.get("/price/{symbol}")
def get_price(symbol: str):

    symbol = symbol.upper()

    pair_map = {
        "BTCUSDT": "XBTUSD",
        "ETHUSDT": "ETHUSD",
        "SOLUSDT": "SOLUSD"
    }

    if symbol not in pair_map:
        return {
            "status": "error",
            "symbol": symbol,
            "message": "Symbol chưa được hỗ trợ"
        }

    pair = pair_map[symbol]

    url = "https://api.kraken.com/0/public/Ticker"

    try:

        response = requests.get(
            url,
            params={
                "pair": pair
            },
            timeout=15
        )

        if response.status_code != 200:
            return {
                "status": "error",
                "symbol": symbol,
                "message": response.text
            }

        data = response.json()

        if data.get("error"):
            return {
                "status": "error",
                "symbol": symbol,
                "message": data["error"]
            }

        result = data["result"]

        ticker = next(iter(result.values()))

        price = float(ticker["c"][0])

        return {
            "status": "ok",
            "symbol": symbol,
            "price": price,
            "source": "Kraken"
        }

    except Exception as e:

        return {
            "status": "error",
            "symbol": symbol,
            "message": str(e)
        }


# ============================================================
# HISTORY
# ============================================================

@app.get("/history/{symbol}")
def get_history(symbol: str):

    symbol = symbol.upper()

    pair_map = {
        "BTCUSDT": "XBTUSD",
        "ETHUSDT": "ETHUSD",
        "SOLUSDT": "SOLUSD"
    }

    if symbol not in pair_map:
        return {
            "status": "error",
            "symbol": symbol,
            "message": "Symbol chưa được hỗ trợ"
        }

    pair = pair_map[symbol]

    url = "https://api.kraken.com/0/public/OHLC"

    try:

        response = requests.get(
            url,
            params={
                "pair": pair,
                "interval": 60
            },
            timeout=15
        )

        if response.status_code != 200:
            return {
                "status": "error",
                "symbol": symbol,
                "message": response.text
            }

        data = response.json()

        if data.get("error"):
            return {
                "status": "error",
                "symbol": symbol,
                "message": data["error"]
            }

        result = data["result"]

        candles = next(
            value
            for key, value in result.items()
            if key != "last"
        )

        candles = candles[-100:]

        history = []

        for candle in candles:

            history.append({
                "time": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "vwap": float(candle[5]),
                "volume": float(candle[6]),
                "trades": int(candle[7])
            })

        return {
            "status": "ok",
            "symbol": symbol,
            "interval": "1h",
            "count": len(history),
            "data": history,
            "source": "Kraken"
        }

    except Exception as e:

        return {
            "status": "error",
            "symbol": symbol,
            "message": str(e)
        }


# ============================================================
# AI ANALYZE
# Signal v1.6.1
# ============================================================

class AnalyzeRequest(BaseModel):

    data: list


@app.post("/ai/analyze")
def ai_analyze(request: AnalyzeRequest):

    try:

        candles = request.data

        if len(candles) < 50:
            return {
                "status": "error",
                "message": "Cần ít nhất 50 candles"
            }

        result = analyze_market(candles)

        return result

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }


# ============================================================
# BACKTEST v1.1
# ============================================================

@app.get("/backtest/{symbol}")
def backtest_symbol(
    symbol: str,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001
):

    symbol = symbol.upper()

    pair_map = {
        "BTCUSDT": "XBTUSD",
        "ETHUSDT": "ETHUSD",
        "SOLUSDT": "SOLUSD"
    }

    if symbol not in pair_map:
        return {
            "status": "error",
            "symbol": symbol,
            "message": "Symbol chưa được hỗ trợ"
        }

    pair = pair_map[symbol]

    url = "https://api.kraken.com/0/public/OHLC"

    try:

        response = requests.get(
            url,
            params={
                "pair": pair,
                "interval": 60
            },
            timeout=15
        )

        if response.status_code != 200:
            return {
                "status": "error",
                "symbol": symbol,
                "message": response.text
            }

        data = response.json()

        if data.get("error"):
            return {
                "status": "error",
                "symbol": symbol,
                "message": data["error"]
            }

        result = data["result"]

        candles = next(
            value
            for key, value in result.items()
            if key != "last"
        )

        candles = candles[-720:]

        history = []

        for candle in candles:

            history.append({
                "time": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "vwap": float(candle[5]),
                "volume": float(candle[6]),
                "trades": int(candle[7])
            })

        backtest_result = run_backtest(
            history,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        backtest_result["symbol"] = symbol
        backtest_result["timeframe"] = "1h"
        backtest_result["candle_count"] = len(history)
        backtest_result["source"] = "Kraken"

        return backtest_result

    except Exception as e:

        return {
            "status": "error",
            "symbol": symbol,
            "message": str(e)
        }


# ============================================================
# BACKTEST v1.2
# MULTI-SYMBOL + MULTI-PERIOD
# ============================================================

@app.get("/backtest-all")
def backtest_all(
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001
):

    try:

        result = run_multi_backtest(
            symbols=[
                "BTCUSDT",
                "ETHUSDT",
                "SOLUSDT"
            ],
            periods=[
                720,
                1440,
                2160,
                2880
            ],
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        result["summary"] = build_summary(
            result["results"]
        )

        return result

    except Exception as e:

        return {
            "status": "error",
            "version": "1.2.0",
            "message": str(e)
        }


# ============================================================
# BACKTEST v1.2 - 1 SYMBOL
# ============================================================

@app.get("/backtest-v12/{symbol}")
def backtest_v12_symbol(
    symbol: str,
    candles: int = 720,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001
):

    symbol = symbol.upper()

    allowed_periods = [
        720,
        1440,
        2160,
        2880
    ]

    if candles not in allowed_periods:

        return {
            "status": "error",
            "symbol": symbol,
            "message": (
                "candles phải là một trong: "
                "720, 1440, 2160, 2880"
            )
        }

    try:

        result = run_symbol_backtest(
            symbol=symbol,
            candle_count=candles,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        return result

    except Exception as e:

        return {
            "status": "error",
            "symbol": symbol,
            "message": str(e)
        }


# ============================================================
# BACKTEST DIAGNOSTIC v1.0
# ============================================================

@app.get("/backtest-diagnostic/{symbol}")
def backtest_diagnostic(
    symbol: str,
    candles: int = 2880,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001
):

    symbol = symbol.upper()

    allowed_periods = [
        720,
        1440,
        2160,
        2880
    ]

    if candles not in allowed_periods:

        return {
            "status": "error",
            "symbol": symbol,
            "message": (
                "candles phải là một trong: "
                "720, 1440, 2160, 2880"
            )
        }

    try:

        backtest_result = run_symbol_backtest(
            symbol=symbol,
            candle_count=candles,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        if backtest_result.get("status") != "ok":
            return backtest_result

        engine_result = backtest_result.get(
            "result",
            {}
        )

        diagnostic = run_diagnostic(
            engine_result
        )

        return {
            "status": "ok",
            "version": "1.0.0",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": backtest_result.get(
                "actual_candles"
            ),
            "source": backtest_result.get(
                "source"
            ),
            "strategy": "Signal v1.6.1",
            "diagnostic": diagnostic
        }

    except Exception as e:

        return {
            "status": "error",
            "symbol": symbol,
            "message": str(e)
        }


# ============================================================
# BACKTEST DIAGNOSTIC v1.4
# ============================================================

@app.get("/backtest-diagnostic-v14/{symbol}")
def backtest_diagnostic_v14(
    symbol: str,
    candles: int = 2880,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001
):

    symbol = symbol.upper()

    allowed_periods = [
        720,
        1440,
        2160,
        2880
    ]

    if candles not in allowed_periods:

        return {
            "status": "error",
            "symbol": symbol,
            "message": (
                "candles phải là một trong: "
                "720, 1440, 2160, 2880"
            )
        }

    try:

        backtest_result = run_symbol_backtest(
            symbol=symbol,
            candle_count=candles,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        if backtest_result.get("status") != "ok":
            return backtest_result

        engine_result = backtest_result.get(
            "result",
            {}
        )

        diagnostic = run_diagnostic_v14(
            engine_result=engine_result,
            initial_balance=initial_balance
        )

        return {
            "status": "ok",
            "version": "1.4.0",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": backtest_result.get(
                "actual_candles"
            ),
            "source": backtest_result.get(
                "source"
            ),
            "strategy": "Signal v1.6.1",
            "diagnostic": diagnostic
        }

    except Exception as e:

        return {
            "status": "error",
            "symbol": symbol,
            "message": str(e)
        }


# ============================================================
# HELPER:
# LOAD HISTORICAL CANDLES FOR FILTERED BACKTEST v1.5
# ============================================================

def load_filtered_candles(
    symbol: str,
    candles_count: int
):

    symbol = symbol.upper()

    pair_map = {
        "BTCUSDT": "XBTUSD",
        "ETHUSDT": "ETHUSD",
        "SOLUSDT": "SOLUSD"
    }

    if symbol not in pair_map:

        raise ValueError(
            "Symbol chưa được hỗ trợ"
        )

    pair = pair_map[symbol]

    # --------------------------------------------------------
    # 720 candles:
    # Lấy trực tiếp Kraken
    # --------------------------------------------------------

    if candles_count == 720:

        url = "https://api.kraken.com/0/public/OHLC"

        response = requests.get(
            url,
            params={
                "pair": pair,
                "interval": 60
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if data.get("error"):
            raise ValueError(
                str(data["error"])
            )

        result = data["result"]

        raw_candles = next(
            value
            for key, value in result.items()
            if key != "last"
        )

        raw_candles = raw_candles[-720:]

        history = []

        for candle in raw_candles:

            history.append({
                "time": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "vwap": float(candle[5]),
                "volume": float(candle[6]),
                "trades": int(candle[7])
            })

        return history

    # --------------------------------------------------------
    # >720:
    # Local historical CSV
    # --------------------------------------------------------

    filename = f"{pair}_60.csv"

    csv_path = os.path.join(
        os.path.dirname(__file__),
        "historical",
        filename
    )

    if not os.path.exists(csv_path):

        raise FileNotFoundError(
            f"Không tìm thấy file lịch sử: {csv_path}"
        )

    rows = []

    with open(
        csv_path,
        "r",
        encoding="utf-8"
    ) as f:

        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(
                "CSV không có header"
            )

        fields = {
            str(x).strip().lower(): x
            for x in reader.fieldnames
        }

        def find_field(*names):

            for name in names:

                if name in fields:
                    return fields[name]

            return None

        time_field = find_field(
            "time",
            "timestamp",
            "ts",
            "date"
        )

        open_field = find_field(
            "open"
        )

        high_field = find_field(
            "high"
        )

        low_field = find_field(
            "low"
        )

        close_field = find_field(
            "close"
        )

        vwap_field = find_field(
            "vwap"
        )

        volume_field = find_field(
            "volume",
            "vol"
        )

        trades_field = find_field(
            "trades",
            "count"
        )

        required = [
            open_field,
            high_field,
            low_field,
            close_field,
            volume_field
        ]

        if any(
            field is None
            for field in required
        ):

            raise ValueError(
                "CSV thiếu một trong các cột "
                "open/high/low/close/volume"
            )

        for row in reader:

            try:

                candle = {
                    "time": (
                        int(
                            float(
                                row[time_field]
                            )
                        )
                        if time_field
                        else 0
                    ),

                    "open": float(
                        row[open_field]
                    ),

                    "high": float(
                        row[high_field]
                    ),

                    "low": float(
                        row[low_field]
                    ),

                    "close": float(
                        row[close_field]
                    ),

                    "vwap": (
                        float(
                            row[vwap_field]
                        )
                        if vwap_field
                        and row[vwap_field] != ""
                        else float(
                            row[close_field]
                        )
                    ),

                    "volume": float(
                        row[volume_field]
                    ),

                    "trades": (
                        int(
                            float(
                                row[trades_field]
                            )
                        )
                        if trades_field
                        and row[trades_field] != ""
                        else 0
                    )
                }

                rows.append(candle)

            except Exception:
                continue

    if len(rows) < candles_count:

        raise ValueError(
            f"CSV chỉ có {len(rows)} candles, "
            f"cần {candles_count} candles"
        )

    # Giống Backtest v1.2:
    # lấy candles cuối cùng
    rows = rows[-candles_count:]

    return rows


# ============================================================
# BACKTEST FILTERED v1.5
# TRUE COMPOUNDING
# ============================================================

@app.get("/backtest-filtered-v15/{symbol}")
def backtest_filtered_v15(
    symbol: str,
    candles: int = 2880,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001
):

    symbol = symbol.upper()

    allowed_periods = [
        720,
        1440,
        2160,
        2880
    ]

    if candles not in allowed_periods:

        return {
            "status": "error",
            "version": "1.5.0",
            "symbol": symbol,
            "message": (
                "candles phải là một trong: "
                "720, 1440, 2160, 2880"
            )
        }

    try:

        # ----------------------------------------------------
        # Load đúng dữ liệu lịch sử
        # ----------------------------------------------------

        candles_data = load_filtered_candles(
            symbol=symbol,
            candles_count=candles
        )

        actual_candles = len(
            candles_data
        )

        # ----------------------------------------------------
        # Chạy TRUE filtered backtest
        # ----------------------------------------------------

        diagnostic = run_filtered_diagnostic_v15(
            candles=candles_data,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        return {
            "status": "ok",
            "version": "1.5.0",
            "symbol": symbol,
            "timeframe": "1h",
            "candles": candles,
            "actual_candles": actual_candles,
            "source": (
                "Kraken"
                if candles == 720
                else "local_csv"
            ),
            "strategy": "Signal v1.6.1",
            "backtest": diagnostic
        }

    except Exception as e:

        return {
            "status": "error",
            "version": "1.5.0",
            "symbol": symbol,
            "message": str(e)
        }
