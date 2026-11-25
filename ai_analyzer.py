import pandas as pd
import numpy as np


VERSION = "1.6.0"


def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)


def calculate_atr(df, period=14):
    high_low = df["high"] - df["low"]

    high_close = (
        df["high"] - df["close"].shift(1)
    ).abs()

    low_close = (
        df["low"] - df["close"].shift(1)
    ).abs()

    true_range = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    return true_range.rolling(period).mean()


def calculate_vwap(df):
    if "vwap" in df.columns:
        return df["vwap"].iloc[-1]

    typical_price = (
        df["high"] +
        df["low"] +
        df["close"]
    ) / 3

    cumulative_volume = df["volume"].cumsum()

    cumulative_price_volume = (
        typical_price * df["volume"]
    ).cumsum()

    vwap = (
        cumulative_price_volume /
        cumulative_volume
    )

    return vwap.iloc[-1]


def analyze_market(candles):

    if not candles or len(candles) < 50:
        return {
            "status": "error",
            "message": "Cần ít nhất 50 nến"
        }

    df = pd.DataFrame(candles).copy()

    required_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for column in required_columns:
        if column not in df.columns:
            return {
                "status": "error",
                "message": f"Thiếu dữ liệu: {column}"
            }

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    if "trades" not in df.columns:
        df["trades"] = 0

    df["trades"] = pd.to_numeric(
        df["trades"],
        errors="coerce"
    ).fillna(0)

    df = df.dropna().reset_index(drop=True)

    close = df["close"]

    # =========================
    # EMA
    # =========================

    df["ema20"] = calculate_ema(close, 20)
    df["ema50"] = calculate_ema(close, 50)

    # =========================
    # RSI
    # =========================

    df["rsi"] = calculate_rsi(close, 14)

    # =========================
    # ATR
    # =========================

    df["atr"] = calculate_atr(df, 14)

    # =========================
    # MACD
    # =========================

    ema12 = calculate_ema(close, 12)
    ema26 = calculate_ema(close, 26)

    df["macd"] = ema12 - ema26
    df["macd_signal"] = calculate_ema(
        df["macd"],
        9
    )

    df["macd_histogram"] = (
        df["macd"] -
        df["macd_signal"]
    )

    # =========================
    # VWAP
    # =========================

    vwap = calculate_vwap(df)

    # =========================
    # Volume
    # =========================

    volume_avg20 = df["volume"].rolling(20).mean().iloc[-1]

    current_volume = df["volume"].iloc[-1]

    if volume_avg20 > 0:
        volume_ratio = (
            current_volume /
            volume_avg20
        )
    else:
        volume_ratio = 0

    # =========================
    # Trades
    # =========================

    trades_avg20 = (
        df["trades"]
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    current_trades = df["trades"].iloc[-1]

    if trades_avg20 > 0:
        trades_ratio = (
            current_trades /
            trades_avg20
        )
    else:
        trades_ratio = 0

    # =========================
    # Support / Resistance
    # =========================

    recent = df.tail(30)

    support = float(
        recent["low"].min()
    )

    resistance = float(
        recent["high"].max()
    )

    # =========================
    # Breakout / Breakdown
    # =========================

    previous20 = df.iloc[-21:-1]

    previous_high = previous20["high"].max()
    previous_low = previous20["low"].min()

    current_price = float(
        df["close"].iloc[-1]
    )

    breakout = (
        current_price >
        previous_high
    )

    breakdown = (
        current_price <
        previous_low
    )

    # =========================
    # Current candle
    # =========================

    current_open = float(
        df["open"].iloc[-1]
    )

    bullish_candle = (
        current_price >
        current_open
    )

    bearish_candle = (
        current_price <
        current_open
    )

    # =========================
    # Score
    # =========================

    score = 0
    reasons = []

    # EMA trend
    if df["ema20"].iloc[-1] > df["ema50"].iloc[-1]:
        score += 2
        reasons.append("EMA20 nằm trên EMA50")
    else:
        score -= 2
        reasons.append("EMA20 nằm dưới EMA50")

    # Price vs EMA20
    if current_price > df["ema20"].iloc[-1]:
        score += 2
        reasons.append("Giá nằm trên EMA20")
    else:
        score -= 2
        reasons.append("Giá nằm dưới EMA20")

    # RSI
    rsi = float(df["rsi"].iloc[-1])

    if rsi >= 55:
        score += 2
        reasons.append("RSI mạnh")
    elif rsi >= 50:
        score += 1
        reasons.append("RSI hơi tích cực")
    elif rsi <= 35:
        score -= 2
        reasons.append("RSI rất yếu")
    else:
        score -= 1
        reasons.append("RSI yếu")

    # MACD
    macd = float(df["macd"].iloc[-1])
    macd_signal = float(
        df["macd_signal"].iloc[-1]
    )
    macd_histogram = float(
        df["macd_histogram"].iloc[-1]
    )

    if macd > macd_signal:
        score += 2
        reasons.append("MACD tích cực")
    else:
        score -= 2
        reasons.append("MACD tiêu cực")

    if macd_histogram > 0:
        score += 1
    else:
        score -= 1

    # VWAP
    if current_price > vwap:
        score += 2
        reasons.append("Giá nằm trên VWAP")
    else:
        score -= 2
        reasons.append("Giá nằm dưới VWAP")

    # =========================
    # Volume confirmation
    # =========================

    if volume_ratio >= 1.5:

        if bullish_candle:
            score += 2
            reasons.append(
                "Volume tăng mạnh xác nhận bên mua"
            )

        elif bearish_candle:
            score -= 2
            reasons.append(
                "Volume tăng mạnh xác nhận bên bán"
            )

    elif volume_ratio >= 1.2:

        if bullish_candle:
            score += 1
            reasons.append(
                "Volume cao hơn trung bình"
            )

        elif bearish_candle:
            score -= 1
            reasons.append(
                "Volume cao hơn trung bình"
            )

    else:

        reasons.append(
            "Volume thấp, chưa xác nhận xu hướng"
        )

    # =========================
    # Trades confirmation
    # =========================

    if trades_ratio >= 1.5:

        if bullish_candle:
            score += 1
            reasons.append(
                "Số lệnh tăng mạnh xác nhận bên mua"
            )

        elif bearish_candle:
            score -= 1
            reasons.append(
                "Số lệnh tăng mạnh xác nhận bên bán"
            )

    elif trades_ratio < 0.5:

        reasons.append(
            "Số lệnh thấp, thị trường thiếu xác nhận"
        )

    # =========================
    # Breakout
    # =========================

    if breakout:
        score += 3
        reasons.append(
            "Breakout vượt đỉnh 20 nến"
        )

    if breakdown:
        score -= 3
        reasons.append(
            "Breakdown thủng đáy 20 nến"
        )

    # =========================
    # Market condition
    # =========================

    if score >= 6:
        market_condition = "BULLISH"

    elif score <= -6:
        market_condition = "BEARISH"

    elif score > 0:
        market_condition = "WEAK_BULLISH"

    elif score < 0:
        market_condition = "WEAK_BEARISH"

    else:
        market_condition = "SIDEWAYS"

    # =========================
    # Signal
    # =========================

    if score >= 8:
        signal = "BUY"

    elif score <= -8:
        signal = "SELL"

    else:
        signal = "HOLD"

    # =========================
    # Confirmation filter
    # =========================

    low_volume = volume_ratio < 0.5
    low_trades = trades_ratio < 0.5

    confirmation_warning = False

    if low_volume or low_trades:
        confirmation_warning = True

    # Nếu volume/trades quá thấp
    # không cho BUY/SELL mạnh
    if signal in ["BUY", "SELL"]:

        if low_volume and low_trades:

            signal = "HOLD"

            reasons.append(
                "Tín hiệu bị hạ xuống HOLD vì "
                "Volume và Trades quá thấp"
            )

        elif low_volume:

            signal = "HOLD"

            reasons.append(
                "Tín hiệu bị hạ xuống HOLD vì "
                "Volume quá thấp"
            )

        elif low_trades:

            signal = "HOLD"

            reasons.append(
                "Tín hiệu bị hạ xuống HOLD vì "
                "Trades quá thấp"
            )

    # =========================
    # Confidence
    # =========================

    confidence = (
        abs(score) / 17
    ) * 100

    confidence = min(
        confidence,
        95
    )

    # giảm confidence khi thiếu volume
    if low_volume:
        confidence *= 0.75

    # giảm thêm khi trades thấp
    if low_trades:
        confidence *= 0.85

    if signal == "HOLD":
        confidence = max(
            50,
            confidence
        )

    confidence = round(
        confidence,
        2
    )

    # =========================
    # ATR / Risk management
    # =========================

    atr = float(
        df["atr"].iloc[-1]
    )

    entry = current_price

    stop_loss = None
    take_profit = None
    risk_reward = None

    if signal == "BUY":

        stop_loss = entry - (
            1.5 * atr
        )

        take_profit = entry + (
            3 * atr
        )

        risk_reward = 2

    elif signal == "SELL":

        stop_loss = entry + (
            1.5 * atr
        )

        take_profit = entry - (
            3 * atr
        )

        risk_reward = 2

    # =========================
    # Trade allowed
    # =========================

    trade_allowed = (
        signal in ["BUY", "SELL"]
        and not low_volume
        and not low_trades
    )

    # =========================
    # Reason summary
    # =========================

    if trade_allowed:

        if signal == "BUY":

            confirmation_reason = (
                "Tín hiệu BUY được xác nhận "
                "bởi xu hướng và thanh khoản"
            )

        else:

            confirmation_reason = (
                "Tín hiệu SELL được xác nhận "
                "bởi xu hướng và thanh khoản"
            )

    else:

        if low_volume and low_trades:

            confirmation_reason = (
                "Xu hướng chưa đủ xác nhận: "
                "Volume và Trades thấp"
            )

        elif low_volume:

            confirmation_reason = (
                "Xu hướng chưa đủ xác nhận: "
                "Volume thấp"
            )

        elif low_trades:

            confirmation_reason = (
                "Xu hướng chưa đủ xác nhận: "
                "Trades thấp"
            )

        else:

            confirmation_reason = (
                "Chưa có tín hiệu giao dịch đủ mạnh"
            )

    # =========================
    # Return
    # =========================

    return {
        "status": "ok",
        "version": VERSION,

        "signal": signal,
        "confidence": confidence,

        "market_condition": market_condition,

        "trade_allowed": trade_allowed,

        "confirmation_warning": confirmation_warning,

        "confirmation_reason": confirmation_reason,

        "price": entry,
        "entry": entry,

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
            "ema20": round(
                float(df["ema20"].iloc[-1]),
                2
            ),

            "ema50": round(
                float(df["ema50"].iloc[-1]),
                2
            ),

            "rsi": round(
                rsi,
                2
            ),

            "atr": round(
                atr,
                2
            ),

            "macd": round(
                macd,
                4
            ),

            "macd_signal": round(
                macd_signal,
                4
            ),

            "macd_histogram": round(
                macd_histogram,
                4
            ),

            "vwap": round(
                float(vwap),
                2
            ),

            "volume": round(
                current_volume,
                6
            ),

            "volume_avg20": round(
                float(volume_avg20),
                6
            ),

            "volume_ratio": round(
                float(volume_ratio),
                2
            ),

            "trades": int(
                current_trades
            ),

            "trades_avg20": round(
                float(trades_avg20),
                2
            ),

            "trades_ratio": round(
                float(trades_ratio),
                2
            )
        },

        "support": round(
            support,
            2
        ),

        "resistance": round(
            resistance,
            2
        ),

        "breakout": breakout,
        "breakdown": breakdown,

        "score": score,

        "reasons": reasons,

        "candle_count": len(df)
    }
