from fastapi import FastAPI
from datetime import datetime
from ai_analyzer import analyze_market
from pydantic import BaseModel
from backtest_engine import run_backtest
import requests


app = FastAPI(
    title="Binance AI Trading Pro Backend",
    description="Backend theo dõi và phân tích thị trường crypto",
    version="1.4.1"
)


# =========================================================
# TRANG CHỦ
# =========================================================

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Binance AI Trading Pro Backend đang chạy!",
        "time": datetime.now().isoformat()
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "message": "Backend hoạt động bình thường"
    }


# =========================================================
# GIÁ HIỆN TẠI
# =========================================================

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
            timeout=10
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
            "currency": "USD",
            "source": "Kraken"
        }

    except Exception as e:

        return {
            "status": "error",
            "symbol": symbol,
            "message": str(e)
        }


# =========================================================
# LỊCH SỬ GIÁ OHLC
# =========================================================

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
            timeout=10
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
            value for key, value in result.items()
            if key != "last"
        )

        history = []

        for candle in candles[-100:]:

            history.append({
                "time": candle[0],
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


# =========================================================
# AI ANALYSIS REQUEST
# =========================================================

class AIAnalysisRequest(BaseModel):
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    data: list


# =========================================================
# AI PHÂN TÍCH THỊ TRƯỜNG
# =========================================================

@app.post("/ai/analyze")
def ai_analyze(request: AIAnalysisRequest):

    try:

        data = request.data

        # -------------------------------------------------
        # TRƯỜNG HỢP 1:
        # data = [100 candles]
        # -------------------------------------------------

        if data and isinstance(data[0], dict) and "close" in data[0]:

            candles = data

        # -------------------------------------------------
        # TRƯỜNG HỢP 2:
        # data = [
        #     {
        #         "status": "ok",
        #         "data": [100 candles]
        #     }
        # ]
        # -------------------------------------------------

        elif (
            data
            and isinstance(data[0], dict)
            and "data" in data[0]
        ):

            candles = data[0]["data"]

        else:

            return {
                "status": "error",
                "message": "Cấu trúc dữ liệu nến không hợp lệ"
            }

        # -------------------------------------------------
        # KIỂM TRA SỐ LƯỢNG NẾN
        # -------------------------------------------------

        if len(candles) < 50:

            return {
                "status": "error",
                "message": f"Cần ít nhất 50 nến, hiện tại có {len(candles)} nến"
            }

        # -------------------------------------------------
        # GỌI AI ANALYZER
        # -------------------------------------------------

        result = analyze_market(candles)

        # -------------------------------------------------
        # THÔNG TIN THỊ TRƯỜNG
        # -------------------------------------------------

        result["symbol"] = request.symbol.upper()
        result["timeframe"] = request.interval
        result["candle_count"] = len(candles)

        return result

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }
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
            timeout=10
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

        history = []

        for candle in candles[-100:]:

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

        result = run_backtest(
            history,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        result["symbol"] = symbol
        result["timeframe"] = "1h"
        result["candle_count"] = len(history)
        result["source"] = "Kraken"

        return result

    except Exception as e:

        return {
            "status": "error",
            "symbol": symbol,
            "message": str(e)
        }
