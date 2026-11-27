"""Gửi email khi paper trading có sự kiện mới (tín hiệu / lệnh giả). Không có sự kiện -> không gửi.
Cần 3 GitHub Secrets: EMAIL_USER (địa chỉ Gmail), EMAIL_APP_PASSWORD (mật khẩu ứng dụng), EMAIL_TO (nơi nhận)."""
import os, smtplib, ssl
from email.message import EmailMessage

events = open("notify.txt").read().strip() if os.path.exists("notify.txt") else ""
if not events:
    print("Không có sự kiện mới -> không gửi email."); raise SystemExit(0)
summary = open("paper_trading/SUMMARY.md").read() if os.path.exists("paper_trading/SUMMARY.md") else ""
body = "Paper trading BTC (LỆNH GIẢ - không phải tiền thật)\n\nSự kiện mới:\n" + events + "\n\n----\n" + summary
user, pw, to = (os.environ.get(k, "").strip() for k in ("EMAIL_USER", "EMAIL_APP_PASSWORD", "EMAIL_TO"))
if os.environ.get("DRY_RUN") or not (user and pw and to):
    print("[Chưa cấu hình email hoặc DRY_RUN] Nội dung sẽ gửi:\n" + body); raise SystemExit(0)
m = EmailMessage(); m["Subject"] = "Paper trading BTC: có tín hiệu mới"; m["From"] = user; m["To"] = to; m.set_content(body)
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
    s.login(user, pw); s.send_message(m)
print("Đã gửi email tới", to)
