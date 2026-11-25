from fastapi import FastAPI
from datetime import datetime
import requests

app = FastAPI(
    title="Binance AI Trading Pro Backend",
    description="Backend theo dõi và phân tích thị trường crypto",
    version="1.2.0"
)


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Binance AI Trading Pro Backend đang chạy!",
        "time": datetime.now().isoformat()
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "message": "Backend hoạt động bình thường"
    }


# =========================================================
# LẤY GIÁ CRYPTO
# =========================================================

@app.get("/price/{symbol}")
def get_price(symbol: str):

    symbol = symbol.upper()

    coin_map = {
        "BTCUSDT": "bitcoin",
        "ETHUSDT": "ethereum",
        "SOLUSDT": "solana"
    }

    if symbol not in coin_map:
        return {
            "status": "error",
            "symbol": symbol,
            "message": "Symbol chưa được hỗ trợ"
        }

    coin_id = coin_map[symbol]

    url = "https://api.coingecko.com/api/v3/simple/price"

    try:
        response = requests.get(
            url,
            params={
                "ids": coin_id,
                "vs_currencies": "usd"
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

        price = data[coin_id]["usd"]

        return {
            "status": "ok",
            "symbol": symbol,
            "price": price,
            "currency": "USD",
            "source": "CoinGecko"
        }

    except Exception as e:

        return {
            "status": "error",
            "symbol": symbol,
            "message": str(e)
        }
