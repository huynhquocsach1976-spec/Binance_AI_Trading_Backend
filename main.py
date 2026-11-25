from fastapi import FastAPI
from datetime import datetime
from pydantic import BaseModel
import requests

from ai_analyzer import analyze_market
from backtest_engine import run_backtest
from backtest_v12 import run_multi_backtest, build_summary


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Binance AI Trading Pro Backend",
    description="AI phân tích và backtest thị trường crypto",
    version="1.2.0"
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Binance AI Trading Pro Backend đang chạy!",
        "version": "1.2.0",
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
        "backtest_version": "1.2.0"
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
# Giữ API cũ
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
# Cho phép test riêng một coin
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

        from backtest_v12 import run_symbol_backtest

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
