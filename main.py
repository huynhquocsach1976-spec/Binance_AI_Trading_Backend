from fastapi import FastAPI
from datetime import datetime

app = FastAPI(
    title="Binance AI Trading Pro Backend",
    description="Backend theo dõi và phân tích giao dịch Binance",
    version="1.0.0"
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
