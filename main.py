
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
  
  3. Tạo requirements.txt
  
  Tạo file:
  requirements.txt
  
  Nội dung:
  
  fastapi
  uvicorn
  python-dotenv
  requests
  
  4. Tạo render.yaml
  
  Tạo file:
  render.yaml
  
  Nội dung:
  
  services:
    - type: web
      name: binance-ai-trading-backend
      runtime: python
      buildCommand: pip install -r requirements.txt
      startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
  
  5. Deploy lên Render
  
  Vào Render → New → Web Service.
  
  Chọn repository:
  Binance_AI_Trading_Backend
  
  Render sẽ đọc render.yaml.
  
  Nếu Render hỏi:
  Build Command:
  pip install -r requirements.txt
  
  Start Command:
  uvicorn main:app --host 0.0.0.0 --port $PORT
  
  Sau đó bấm Deploy Web Service.
  
  6. Kiểm tra
  
  Khi Render báo Live, bạn sẽ có địa chỉ dạng:
  
  https://binance-ai-trading-backend.onrender.com
  
  Mở:
  
  https://.../docs
  
  Nếu thấy Swagger với tiêu đề:
  
  Binance AI Trading Pro Backend
  
  là BƯỚC 1 thành công.
  
  Kiểm tra thêm:
  
  /health
  
  Kết quả phải tương tự:
  
  {
    "status": "healthy",
    "message": "Backend hoạt động bình thường"
  }
  
  ⚠️ Chưa tạo BINANCE_API_KEY hoặc BINANCE_SECRET_KEY ở bước này. Chưa cấp quyền giao dịch cho bất kỳ API key nào.
  
  Sau khi Render chạy thành công, BƯỚC 2 sẽ tạo Streamlit Dashboard và kết nối nó với URL Backend Render này.
</text>
