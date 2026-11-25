import pandas as pd
import numpy as np


def calculate_rsi(close, period=14):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    return tr.rolling(period).mean()


def analyze_market(candles):

    if len(candles) < 50:
        return {
            "status": "error",
            "message": "Cần ít nhất 50 nến để phân tích"
        }

    df = pd.DataFrame(candles)

    required = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for column in required:
        if column not in df.columns:
            return {
                "status": "error",
                "message": f"Thiếu dữ liệu: {column}"
            }

    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    df["rsi"] = calculate_rsi(df["close"])
    df["atr"] = calculate_atr(df)

    last = df.iloc[-1]

    price = float(last["close"])
    ema20 = float(last["ema20"])
    ema50 = float(last["ema50"])
    rsi = float(last["rsi"])
    atr = float(last["atr"])

    # ------------------------------------------------
    # XÁC ĐỊNH SUPPORT / RESISTANCE
    # ------------------------------------------------

    recent = df.tail(30)

    support = float(recent["low"].min())
    resistance = float(recent["high"].max())

    # ------------------------------------------------
    # ĐIỂM TÍN HIỆU
    # ------------------------------------------------

    score = 0
    reasons = []

    # EMA trend
    if ema20 > ema50:
        score += 25
        reasons.append("EMA20 nằm trên EMA50")
    else:
        score -= 25
        reasons.append("EMA20 nằm dưới EMA50")

    # Price vs EMA20
    if price > ema20:
        score += 15
        reasons.append("Giá nằm trên EMA20")
    else:
        score -= 15
        reasons.append("Giá nằm dưới EMA20")

    # RSI
    if 50 <= rsi <= 70:
        score += 15
        reasons.append("RSI tích cực")
    elif rsi < 30:
        score += 10
        reasons.append("RSI quá bán")
    elif rsi > 70:
        score -= 10
        reasons.append("RSI quá mua")
    else:
        score -= 5
        reasons.append("RSI yếu")

    # Volume
    avg_volume = df["volume"].tail(20).mean()

    if last["volume"] > avg_volume * 1.2:
        if score > 0:
            score += 15
            reasons.append("Volume tăng xác nhận xu hướng")
        else:
            score -= 15
            reasons.append("Volume tăng khi xu hướng giảm")

    # ------------------------------------------------
    # TÍN HIỆU
    # ------------------------------------------------

    if score >= 30:
        signal = "BUY"

    elif score <= -30:
        signal = "SELL"

    else:
        signal = "HOLD"

    # ------------------------------------------------
    # CONFIDENCE
    # ------------------------------------------------

    confidence = min(abs(score) / 70 * 100, 95)

    if signal == "HOLD":
        confidence = max(50, 100 - abs(score))

    confidence = round(confidence, 2)

    # ------------------------------------------------
    # ENTRY / SL / TP
    # ------------------------------------------------

    if signal == "BUY":

        entry = price

        stop_loss = entry - atr * 1.5

        take_profit = entry + atr * 3

    elif signal == "SELL":

        entry = price

        stop_loss = entry + atr * 1.5

        take_profit = entry - atr * 3

    else:

        entry = price
        stop_loss = None
        take_profit = None

    # ------------------------------------------------
    # RISK / REWARD
    # ------------------------------------------------

    if signal != "HOLD":

        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)

        risk_reward = round(reward / risk, 2)

    else:

        risk_reward = None

    return {
        "status": "ok",

        "symbol": "BTCUSDT",

        "timeframe": "1h",

        "signal": signal,

        "confidence": confidence,

        "price": round(price, 2),

        "entry": round(entry, 2),

        "stop_loss": (
            round(stop_loss, 2)
            if stop_loss is not None
            else None
        ),

        "take_profit": (
            round(take_profit, 2)
            if take_profit is not None
            else None
        ),

        "risk_reward": risk_reward,

        "indicators": {
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "rsi": round(rsi, 2),
            "atr": round(atr, 2)
        },

        "support": round(support, 2),

        "resistance": round(resistance, 2),

        "score": score,

        "reasons": reasons
    }
