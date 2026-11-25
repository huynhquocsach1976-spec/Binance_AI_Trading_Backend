from fastapi import FastAPI
from datetime import datetime
import requests

app = FastAPI(
    title="Binance AI Trading Pro Backend",
    description="Backend theo dõi và phân tích giao dịch Binance",
    version="1.1.0"
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


@app.get("/price/{symbol}")
def get_price(symbol: str):

    symbol = symbol.upper()

    url = "https://api.binance.com/api/v3/ticker/price"

    response = requests.get(
        url,
        params={"symbol": symbol},
        timeout=10
    )

    if response.status_code != 200:
        return {
            "status": "error",
            "symbol": symbol,
            "message": response.text
        }

    data = response.json()

    return {
        "status": "ok",
        "symbol": data["symbol"],
        "price": float(data["price"]),
        "source": "Binance"
    }
