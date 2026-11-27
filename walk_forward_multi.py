"""Walk-forward nhiều năm, nhiều mã, khung 4h và 1 ngày. Chiến lược: theo xu hướng (Donchian / EMA cross) + dừng lỗ ATR.
Tham số chọn trên đoạn CŨ (train), chỉ đánh giá trên đoạn MỚI (test). So sánh với mua-giữ cùng đoạn test.
"""
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

FEE  = 0.0005   # phí mỗi chiều (0.05%)
SLIP = 0.0002   # trượt giá mỗi chiều
SYMBOLS = os.environ.get("SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")
TFS = {"4h": dict(train=1500, test=500), "1d": dict(train=500, test=150)}

def load(sym, tf):
    raw = pd.read_csv(f"historical/{sym}_1h.csv")
    raw["t"] = pd.to_datetime(raw.timestamp, unit="s")
    rule = {"4h": "4h", "1d": "1D"}[tf]
    d = raw.set_index("t").resample(rule).agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna().reset_index()
    return d

class Data:
    def __init__(s, d):
        s.t = d.t.values; s.O, s.H, s.L, s.C = [d[k].values for k in ("open","high","low","close")]
        pc = np.r_[s.C[0], s.C[:-1]]
        tr = np.maximum.reduce([s.H - s.L, np.abs(s.H - pc), np.abs(s.L - pc)])
        s.ATR = pd.Series(tr).rolling(14).mean().values
        s.N = len(s.C); s._c = {}
    def ema(s, n):
        k = ("e", n)
        if k not in s._c: s._c[k] = pd.Series(s.C).ewm(span=n, adjust=False).mean().values
        return s._c[k]
    def roll(s, arr, n, fn):
        k = (fn, n, id(arr))
        if k not in s._c:
            r = pd.Series(arr).rolling(n); s._c[k] = (r.max() if fn == "max" else r.min()).shift(1).values
        return s._c[k]

def sim(D, p, start, end):
    kind, a, b, k, side = p
    O, H, L, C, ATR = D.O, D.H, D.L, D.C, D.ATR
    if kind == "donch":
        hi, lo = D.roll(H, a, "max"), D.roll(L, a, "min"); xl, xh = D.roll(L, b, "min"), D.roll(H, b, "max")
    else:
        ef, es = D.ema(a), D.ema(b)
    pos = 0; trades = []; start = max(start, 210)
    for i in range(start, end - 1):
        if pos == 0:
            s = 0
            if kind == "donch":
                if C[i] > hi[i]: s = 1
                elif C[i] < lo[i]: s = -1
            else:
                if ef[i] > es[i] and ef[i-1] <= es[i-1]: s = 1
                elif ef[i] < es[i] and ef[i-1] >= es[i-1]: s = -1
            if (s == 1 and side == "short") or (s == -1 and side == "long"): s = 0
            if s and np.isfinite(ATR[i]):
                pos = s; ep = O[i+1] * (1 + SLIP * s); stop = ep - s * k * ATR[i]; ei = i + 1
        else:
            if i < ei: continue
            xp = None
            if (pos == 1 and L[i] <= stop) or (pos == -1 and H[i] >= stop): xp = stop
            elif kind == "donch" and ((pos == 1 and C[i] < xl[i]) or (pos == -1 and C[i] > xh[i])): xp = O[i+1]
            elif kind == "ema" and ((pos == 1 and ef[i] < es[i]) or (pos == -1 and ef[i] > es[i])): xp = O[i+1]
            if xp is not None:
                xp *= 1 - SLIP * pos; trades.append(pos * (xp - ep) / ep - 2 * FEE); pos = 0
    if pos != 0:  # đóng lệnh còn mở ở cuối đoạn
        xp = C[end-1] * (1 - SLIP * pos); trades.append(pos * (xp - ep) / ep - 2 * FEE)
    return trades

def stats(tr):
    if not tr: return dict(n=0, ret=0.0, wr=0, pf=0.0, dd=0.0)
    p = np.array(tr); g = p[p > 0].sum(); l = -p[p < 0].sum(); eq = np.cumprod(1 + p)
    return dict(n=len(p), ret=round((eq[-1]-1)*100, 1), wr=round((p > 0).mean()*100), pf=round(g/l, 2) if l else 9.99,
                dd=round((1 - eq/np.maximum.accumulate(eq)).max()*100, 1))

def grid():
    g = [("donch", a, b, k, s) for a in (10,20,30,55) for b in (5,10,20) for k in (2,3,4) for s in ("both","long") if b < a]
    g += [("ema", a, b, k, s) for a in (5,10,20) for b in (30,50,100) for k in (2,3,4) for s in ("both","long") if a < b]
    return g

def run(sym, tf):
    d = load(sym, tf); D = Data(d); cfg = TFS[tf]; G = grid()
    if D.N < cfg["train"] + cfg["test"] + 210:
        print(f"[{sym} {tf}] quá ít nến ({D.N}), bỏ qua"); return None
    print(f"\n=== {sym} {tf}: {D.N} nến {str(D.t[0])[:10]} -> {str(D.t[-1])[:10]}")
    a = 210; oos = []; folds = []; bh = 1.0
    while a + cfg["train"] + cfg["test"] <= D.N:
        m, e = a + cfg["train"], a + cfg["train"] + cfg["test"]
        best = None
        for p in G:
            r = stats(sim(D, p, a, m))
            if r["n"] >= 10 and r["pf"] < 9 and (best is None or r["pf"] > best[1]["pf"]): best = (p, r)
        if best is None: a += cfg["test"]; continue
        tr = sim(D, best[0], m, e); r = stats(tr); oos += tr
        bhr = D.C[e-1] / D.O[m] - 1; bh *= 1 + bhr
        folds.append(r["ret"])
        print(f"  {str(D.t[m])[:10]}..{str(D.t[e-1])[:10]} train PF={best[1]['pf']} -> TEST n={r['n']} ret={r['ret']}% PF={r['pf']} | mua-giữ {bhr*100:.1f}%  {best[0]}")
        a += cfg["test"]
    s = stats(oos)
    pos_folds = sum(1 for x in folds if x > 0)
    print(f"  >> OOS tổng: n={s['n']} ret={s['ret']}% PF={s['pf']} dd={s['dd']}% win={s['wr']}% | lượt dương {pos_folds}/{len(folds)} | mua-giữ cùng giai đoạn {(bh-1)*100:.1f}%")
    ok = s["n"] >= 100 and s["pf"] >= 1.3 and s["ret"] > 0 and pos_folds > len(folds) / 2
    return dict(sym=sym, tf=tf, **s, folds=len(folds), pos=pos_folds, bh=round((bh-1)*100, 1), ok=ok)

if __name__ == "__main__":
    res = []
    for sym in SYMBOLS:
        if not os.path.exists(f"historical/{sym}_1h.csv"): print("thiếu file", sym); continue
        for tf in TFS:
            r = run(sym, tf)
            if r: res.append(r)
    print("\n================ TỔNG KẾT ================")
    print("Tiêu chuẩn đạt: >=100 lệnh OOS, PF>=1.3, lãi>0, đa số lượt test dương")
    for r in res:
        print(f"{r['sym']:8s}{r['tf']:3s} n={r['n']:4d} OOS={r['ret']:7.1f}% PF={r['pf']:.2f} dd={r['dd']:.1f}% lượt+={r['pos']}/{r['folds']} mua-giữ={r['bh']:.1f}%  -> {'ĐẠT' if r['ok'] else 'KHÔNG ĐẠT'}")
    print("\nKẾT LUẬN:", "có ứng viên đáng theo dõi (vẫn cần paper trading)" if any(r["ok"] for r in res) else "chưa có chiến lược nào đạt tiêu chuẩn -> không giao dịch tiền thật")
