from fastapi import FastAPI
from datetime import datetime
import requests

app = FastAPI(
    title="Binance AI Trading Pro Backend",
    description="Backend theo dõi và phân tích thị trường crypto",
    version="1.4.0"
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
