"""Tải nến 1h nhiều năm từ kho dữ liệu công khai của Binance (data.binance.vision).
Kết quả: historical/<SYMBOL>_1h.csv  (timestamp[giây], open, high, low, close, volume, trades)
"""
import io, os, sys, zipfile, datetime as dt
import urllib.request, urllib.error
import pandas as pd

SYMBOLS = os.environ.get("SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")
MONTHS = int(os.environ.get("MONTHS", "48"))
BASE = "https://data.binance.vision/data/spot/monthly/klines/{s}/1h/{s}-1h-{y}-{m:02d}.zip"
COLS = ["open_time","open","high","low","close","volume","close_time","qvol","trades","tb","tq","ignore"]

def parse_zip(raw: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        df = pd.read_csv(z.open(z.namelist()[0]), header=None, names=COLS)
    df = df[pd.to_numeric(df["open_time"], errors="coerce").notna()].copy()   # bỏ dòng tiêu đề nếu có
    for c in ["open_time","open","high","low","close","volume","trades"]:
        df[c] = pd.to_numeric(df[c])
    ot = df["open_time"].astype("int64")
    ot = ot.where(ot < 10**14, ot // 1000)           # file từ 2025 dùng micro-giây -> đổi về mili-giây
    df["timestamp"] = ot // 1000
    return df[["timestamp","open","high","low","close","volume","trades"]]

def month_list(n):
    today = dt.date.today().replace(day=1)
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        m -= 1
        if m == 0: y, m = y - 1, 12
        out.append((y, m))
    return out[::-1]

def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404: return None
        raise

def main():
    os.makedirs("historical", exist_ok=True)
    ok = 0
    for s in SYMBOLS:
        parts = []
        for y, m in month_list(MONTHS):
            raw = fetch(BASE.format(s=s, y=y, m=m))
            if raw is None:
                print(f"  {s} {y}-{m:02d}: không có file (bỏ qua)"); continue
            parts.append(parse_zip(raw))
        if not parts:
            print(f"!! {s}: không tải được tháng nào"); continue
        df = pd.concat(parts).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
        df.to_csv(f"historical/{s}_1h.csv", index=False)
        t0 = pd.to_datetime(df.timestamp.iloc[0], unit="s"); t1 = pd.to_datetime(df.timestamp.iloc[-1], unit="s")
        print(f"{s}: {len(df)} nến, {t0} -> {t1}"); ok += 1
    if ok == 0:
        print("Không tải được dữ liệu nào."); sys.exit(1)

if __name__ == "__main__":
    main()
