"""PAPER TRADING (lệnh giả) - BTC khung ngày, chiến lược EMA5/EMA30 cắt lên, dừng lỗ 3 ATR, chỉ MUA (spot).
Chạy mỗi ngày sau 00:00 UTC. KHÔNG kết nối Binance, KHÔNG dùng khóa API, KHÔNG đặt lệnh thật.
Trạng thái lưu trong thư mục paper_trading/ (state.json, trades.csv, log.csv, SUMMARY.md).
"""
import os, json, csv, datetime as dt, urllib.request
import numpy as np, pandas as pd

FAST, SLOW, ATR_N, STOP_ATR = 5, 30, 14, 3.0
FEE, SLIP = 0.001, 0.0002        # phí 0.1% + trượt giá 0.02% mỗi chiều (mức spot thực tế)
RISK = 0.01                      # rủi ro tối đa 1% vốn mỗi lệnh
START_EQUITY = 1000.0
DIR = "paper_trading"
EVENTS = []   # thông báo của lần chạy này (gửi email nếu có)

def fetch_daily():
    url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1440"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        j = json.load(r)
    if j.get("error"): raise RuntimeError(j["error"])
    rows = next(v for k, v in j["result"].items() if k != "last")
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","vwap","vol","n"])
    for c in ["open","high","low","close"]: df[c] = df[c].astype(float)
    df["date"] = pd.to_datetime(df.ts.astype(int), unit="s").dt.strftime("%Y-%m-%d")
    return df[["date","open","high","low","close"]].reset_index(drop=True)

def indicators(df):
    c, h, l = df.close, df.high, df.low
    df = df.copy()
    df["ef"] = c.ewm(span=FAST, adjust=False).mean(); df["es"] = c.ewm(span=SLOW, adjust=False).mean()
    pc = c.shift(); tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_N).mean()
    return df

def load_state():
    p = f"{DIR}/state.json"
    return json.load(open(p)) if os.path.exists(p) else None

def append_csv(path, header, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(header)
        w.writerow(row)

def process(df_all, state, now_date):
    """df_all: nến ngày từ API. Chỉ dùng nến ĐÃ ĐÓNG (ngày < hôm nay UTC); nến hôm nay chỉ lấy giá mở cửa."""
    closed = df_all[df_all.date < now_date].reset_index(drop=True)
    today = df_all[df_all.date == now_date]
    d = indicators(closed)
    if state is None:
        state = dict(start_date=now_date, last_date=closed.date.iloc[-1], equity=START_EQUITY, pos=0, entry=0, stop=0,
                     size=0, entry_date="", pending=None, start_price=float(today.open.iloc[0]) if len(today) else float(closed.close.iloc[-1]))
        print("Khởi tạo paper trading. Bắt đầu theo dõi từ", now_date)
        return state, d
    new = d[d.date > state["last_date"]]
    for _, r in new.iterrows():
        i = int(d.index[d.date == r.date][0])
        # 1) thực thi lệnh chờ ở GIÁ MỞ CỬA của nến này
        pd_ = state["pending"]
        if pd_ == "BUY" and state["pos"] == 0:
            ep = r.open * (1 + SLIP); atr = state["pending_atr"]; stop = ep - STOP_ATR * atr
            size = min(1.0, RISK / ((ep - stop) / ep))
            state.update(pos=1, entry=ep, stop=stop, size=size, entry_date=r.date)
            append_csv(f"{DIR}/log.csv", ["date","event","price","detail"], [r.date, "BUY", round(ep,2), f"stop={stop:.2f} size={size*100:.1f}% vốn"])
            EVENTS.append(f"[{r.date}] ĐÃ MUA (lệnh giả) BTC giá {ep:,.0f} | dừng lỗ {stop:,.0f} | {size*100:.1f}% vốn")
        elif pd_ == "SELL" and state["pos"] == 1:
            state = close_pos(state, r.date, r.open * (1 - SLIP), "TÍN HIỆU (EMA cắt xuống)")
        state["pending"] = None
        # 2) kiểm tra dừng lỗ trong ngày
        if state["pos"] == 1 and r.low <= state["stop"]:
            state = close_pos(state, r.date, state["stop"] * (1 - SLIP), "DỪNG LỖ")
        # 3) tín hiệu theo giá đóng cửa -> lệnh chờ cho ngày kế tiếp
        if i >= 1 and np.isfinite(r.atr):
            if state["pos"] == 0 and r.ef > r.es and d.ef[i-1] <= d.es[i-1]:
                state["pending"] = "BUY"; state["pending_atr"] = float(r.atr)
                EVENTS.append(f"[{r.date}] TÍN HIỆU MUA: EMA{FAST} cắt lên EMA{SLOW}. Lệnh giả sẽ vào ở giá mở cửa ngày kế tiếp.")
            elif state["pos"] == 1 and r.ef < r.es:
                state["pending"] = "SELL"
                EVENTS.append(f"[{r.date}] TÍN HIỆU BÁN: EMA{FAST} cắt xuống EMA{SLOW}. Lệnh giả sẽ thoát ở giá mở cửa ngày kế tiếp.")
        state["last_date"] = r.date
    return state, d

def close_pos(state, date, xp, reason):
    ret = (xp - state["entry"]) / state["entry"]
    pnl = state["size"] * ret - state["size"] * FEE * 2
    state["equity"] *= 1 + pnl
    append_csv(f"{DIR}/trades.csv", ["entry_date","exit_date","entry","exit","size_pct","pnl_pct","equity","reason"],
               [state["entry_date"], date, round(state["entry"],2), round(xp,2), round(state["size"]*100,1), round(pnl*100,2), round(state["equity"],2), reason])
    append_csv(f"{DIR}/log.csv", ["date","event","price","detail"], [date, "SELL", round(xp,2), f"{reason} pnl={pnl*100:.2f}%"])
    EVENTS.append(f"[{date}] ĐÃ ĐÓNG (lệnh giả) giá {xp:,.0f} | {reason} | lãi/lỗ {pnl*100:+.2f}% | vốn giả {state['equity']:.2f}")
    state.update(pos=0, entry=0, stop=0, size=0, entry_date="")
    return state

def summary(state, d, now_date):
    last = d.iloc[-1]
    bh = (float(last.close) / state["start_price"] - 1) * 100
    eq_ret = (state["equity"] / START_EQUITY - 1) * 100
    n = sum(1 for _ in open(f"{DIR}/trades.csv")) - 1 if os.path.exists(f"{DIR}/trades.csv") else 0
    pos = "ĐANG GIỮ BTC" if state["pos"] else "ĐỨNG NGOÀI (tiền mặt)"
    txt = f"""# Paper trading BTC (lệnh giả, KHÔNG phải tiền thật)
Cập nhật: {now_date} (UTC) | Theo dõi từ: {state['start_date']}

- Trạng thái: **{pos}**
- Lệnh chờ ngày mai: {state['pending'] or 'không'}
- Vốn giả: **{state['equity']:.2f}** (bắt đầu {START_EQUITY:.0f}) -> {eq_ret:+.2f}%
- Mua-giữ BTC cùng thời gian: {bh:+.2f}%
- Số lệnh đã đóng: {n}
- Giá đóng cửa gần nhất {last.date}: {last.close:.0f} | EMA{FAST}={last.ef:.0f} EMA{SLOW}={last.es:.0f}
"""
    if state["pos"]: txt += f"- Vào lệnh {state['entry_date']} giá {state['entry']:.0f}, dừng lỗ {state['stop']:.0f}\n"
    txt += "\nChiến lược: mua khi EMA5 cắt lên EMA30 (khung ngày), thoát khi cắt xuống hoặc chạm dừng lỗ 3 ATR. Rủi ro 1% vốn/lệnh.\n"
    open(f"{DIR}/SUMMARY.md", "w").write(txt); print(txt)

def main(df_all=None, now_date=None):
    os.makedirs(DIR, exist_ok=True)
    df_all = fetch_daily() if df_all is None else df_all
    now_date = now_date or dt.datetime.utcnow().strftime("%Y-%m-%d")
    state, d = process(df_all, load_state(), now_date)
    json.dump(state, open(f"{DIR}/state.json", "w"), indent=1)
    summary(state, d, now_date)
    open(os.environ.get("NOTIFY_FILE", "notify.txt"), "w").write("\n".join(EVENTS))

if __name__ == "__main__":
    main()
