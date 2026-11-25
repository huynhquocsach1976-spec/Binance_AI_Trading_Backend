import pandas as pd
import numpy as np


# =========================================================
# AI ANALYZER VERSION 1.5
# =========================================================

VERSION = "1.5.0"


# =========================================================
# EMA
# =========================================================

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


# =========================================================
# RSI
# =========================================================

def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)


# =========================================================
# ATR
# =========================================================

def calculate_atr(df, period=14):

    high_low = df["high"] - df["low"]

    high_close = (
        df["high"] - df["close"].shift(1)
    ).abs()

    low_close = (
        df["low"] - df["close"].shift(1)
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    atr = true_range.rolling(period).mean()

    return atr


# =========================================================
# MACD
# =========================================================

def calculate_macd(series):

    ema12 = series.ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = series.ewm(
        span=26,
        adjust=False
    ).mean()

    macd = ema12 - ema26

    signal = macd.ewm(
        span=9,
        adjust=False
    ).mean()

    histogram = macd - signal

    return macd, signal, histogram


# =========================================================
# VWAP
# =========================================================

def calculate_vwap(df):

    # Nếu dữ liệu đã có VWAP từ Kraken
    if "vwap" in df.columns:

        return df["vwap"]

    # Tự tính VWAP nếu không có
    typical_price = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3

    cumulative_price_volume = (
        typical_price * df["volume"]
    ).cumsum()

    cumulative_volume = (
        df["volume"].cumsum()
    )

    return (
        cumulative_price_volume
        / cumulative_volume
    )


# =========================================================
# PHÂN TÍCH THỊ TRƯỜNG
# =========================================================

def analyze_market(data):

    # -----------------------------------------------------
    # KIỂM TRA DỮ LIỆU
    # -----------------------------------------------------

    if not data:

        return {
            "status": "error",
            "message": "Không có dữ liệu nến"
        }

    if len(data) < 50:

        return {
            "status": "error",
            "message": (
                f"Cần ít nhất 50 nến, "
                f"hiện tại có {len(data)} nến"
            )
        }

    # -----------------------------------------------------
    # DATAFRAME
    # -----------------------------------------------------

    df = pd.DataFrame(data)

    required_columns = [
        "open",
        "high",
        "low",
        "close"
    ]

    for column in required_columns:

        if column not in df.columns:

            return {
                "status": "error",
                "message": (
                    f"Thiếu dữ liệu: {column}"
                )
            }

    # -----------------------------------------------------
    # CHUYỂN KIỂU DỮ LIỆU
    # -----------------------------------------------------

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "vwap",
        "volume",
        "trades"
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    df = df.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close"
        ]
    ).reset_index(drop=True)

    if len(df) < 50:

        return {
            "status": "error",
            "message": "Dữ liệu hợp lệ dưới 50 nến"
        }

    # -----------------------------------------------------
    # INDICATORS
    # -----------------------------------------------------

    close = df["close"]

    # EMA
    df["ema20"] = calculate_ema(
        close,
        20
    )

    df["ema50"] = calculate_ema(
        close,
        50
    )

    # RSI
    df["rsi"] = calculate_rsi(
        close,
        14
    )

    # ATR
    df["atr"] = calculate_atr(
        df,
        14
    )

    # MACD
    (
        df["macd"],
        df["macd_signal"],
        df["macd_histogram"]
    ) = calculate_macd(close)

    # VWAP
    df["calculated_vwap"] = calculate_vwap(df)

    # -----------------------------------------------------
    # LẤY NẾN CUỐI
    # -----------------------------------------------------

    last = df.iloc[-1]

    price = float(last["close"])

    ema20 = float(last["ema20"])

    ema50 = float(last["ema50"])

    rsi = float(last["rsi"])

    atr = float(last["atr"])

    macd = float(last["macd"])

    macd_signal = float(
        last["macd_signal"]
    )

    macd_histogram = float(
        last["macd_histogram"]
    )

    vwap = float(
        last["calculated_vwap"]
    )

    # -----------------------------------------------------
    # VOLUME
    # -----------------------------------------------------

    if "volume" in df.columns:

        volume = float(last["volume"])

        volume_avg20 = float(
            df["volume"]
            .rolling(20)
            .mean()
            .iloc[-1]
        )

        if volume_avg20 > 0:

            volume_ratio = (
                volume / volume_avg20
            )

        else:

            volume_ratio = 1.0

    else:

        volume = 0.0
        volume_avg20 = 0.0
        volume_ratio = 1.0

    # -----------------------------------------------------
    # TRADES
    # -----------------------------------------------------

    if "trades" in df.columns:

        trades = float(last["trades"])

        trades_avg20 = float(
            df["trades"]
            .rolling(20)
            .mean()
            .iloc[-1]
        )

        if trades_avg20 > 0:

            trades_ratio = (
                trades / trades_avg20
            )

        else:

            trades_ratio = 1.0

    else:

        trades = 0.0
        trades_avg20 = 0.0
        trades_ratio = 1.0

    # -----------------------------------------------------
    # SUPPORT / RESISTANCE
    # -----------------------------------------------------

    recent = df.tail(30)

    support = float(
        recent["low"].min()
    )

    resistance = float(
        recent["high"].max()
    )

    # -----------------------------------------------------
    # BREAKOUT / BREAKDOWN
    # -----------------------------------------------------

    previous_20 = df.iloc[-21:-1]

    previous_resistance = float(
        previous_20["high"].max()
    )

    previous_support = float(
        previous_20["low"].min()
    )

    breakout = (
        price > previous_resistance
    )

    breakdown = (
        price < previous_support
    )

    # -----------------------------------------------------
    # SCORE
    # -----------------------------------------------------

    score = 0

    reasons = []

    bullish_signals = []
    bearish_signals = []

    # =====================================================
    # 1. EMA TREND
    # =====================================================

    if ema20 > ema50:

        score += 2

        bullish_signals.append(
            "EMA20 nằm trên EMA50"
        )

    else:

        score -= 2

        bearish_signals.append(
            "EMA20 nằm dưới EMA50"
        )

    # =====================================================
    # 2. PRICE VS EMA20
    # =====================================================

    if price > ema20:

        score += 2

        bullish_signals.append(
            "Giá nằm trên EMA20"
        )

    else:

        score -= 2

        bearish_signals.append(
            "Giá nằm dưới EMA20"
        )

    # =====================================================
    # 3. RSI
    # =====================================================

    if rsi >= 55:

        score += 2

        bullish_signals.append(
            "RSI mạnh"
        )

    elif rsi >= 50:

        score += 1

        bullish_signals.append(
            "RSI trên 50"
        )

    elif rsi <= 35:

        score -= 2

        bearish_signals.append(
            "RSI yếu / gần quá bán"
        )

    elif rsi < 50:

        score -= 1

        bearish_signals.append(
            "RSI yếu"
        )

    # =====================================================
    # 4. MACD
    # =====================================================

    if macd > macd_signal:

        score += 2

        bullish_signals.append(
            "MACD bullish"
        )

    else:

        score -= 2

        bearish_signals.append(
            "MACD bearish"
        )

    # MACD histogram
    if macd_histogram > 0:

        score += 1

        bullish_signals.append(
            "MACD Histogram dương"
        )

    else:

        score -= 1

        bearish_signals.append(
            "MACD Histogram âm"
        )

    # =====================================================
    # 5. VWAP
    # =====================================================

    if price > vwap:

        score += 2

        bullish_signals.append(
            "Giá nằm trên VWAP"
        )

    else:

        score -= 2

        bearish_signals.append(
            "Giá nằm dưới VWAP"
        )

    # =====================================================
    # 6. VOLUME
    # =====================================================

    if volume_ratio >= 1.5:

        if price > last["open"]:

            score += 2

            bullish_signals.append(
                "Volume tăng mạnh kèm nến tăng"
            )

        else:

            score -= 2

            bearish_signals.append(
                "Volume tăng mạnh kèm nến giảm"
            )

    elif volume_ratio >= 1.2:

        if price > last["open"]:

            score += 1

            bullish_signals.append(
                "Volume tăng"
            )

        else:

            score -= 1

            bearish_signals.append(
                "Volume tăng nhưng nến giảm"
            )

    # =====================================================
    # 7. TRADES
    # =====================================================

    if trades_ratio >= 1.5:

        if price > last["open"]:

            score += 1

            bullish_signals.append(
                "Số lệnh giao dịch tăng mạnh"
            )

        else:

            score -= 1

            bearish_signals.append(
                "Số lệnh giao dịch tăng mạnh khi giá giảm"
            )

    # =====================================================
    # 8. BREAKOUT
    # =====================================================

    if breakout:

        score += 3

        bullish_signals.append(
            "Breakout kháng cự"
        )

    # =====================================================
    # 9. BREAKDOWN
    # =====================================================

    if breakdown:

        score -= 3

        bearish_signals.append(
            "Breakdown hỗ trợ"
        )

    # =====================================================
    # TẠO REASONS
    # =====================================================

    if score > 0:

        reasons = bullish_signals[:]

        if not reasons:

            reasons = [
                "Một số chỉ báo đang nghiêng về tăng"
            ]

    elif score < 0:

        reasons = bearish_signals[:]

        if not reasons:

            reasons = [
                "Một số chỉ báo đang nghiêng về giảm"
            ]

    else:

        reasons = [
            "Các chỉ báo đang cân bằng"
        ]

    # =====================================================
    # SIGNAL
    # =====================================================

    if score >= 8:

        signal = "BUY"

    elif score <= -8:

        signal = "SELL"

    else:

        signal = "HOLD"

    # =====================================================
    # CONFIDENCE
    # =====================================================

    max_score = 17

    confidence = (
        abs(score)
        / max_score
        * 100
    )

    confidence = min(
        confidence,
        95
    )

    if signal == "HOLD":

        confidence = max(
            50,
            confidence
        )

    confidence = round(
        confidence,
        2
    )

    # =====================================================
    # STOP LOSS / TAKE PROFIT
    # =====================================================

    if not np.isfinite(atr) or atr <= 0:

        atr = max(
            price * 0.01,
            1
        )

    entry = price

    if signal == "BUY":

        stop_loss = (
            entry - atr * 1.5
        )

        take_profit = (
            entry + atr * 3
        )

    elif signal == "SELL":

        stop_loss = (
            entry + atr * 1.5
        )

        take_profit = (
            entry - atr * 3
        )

    else:

        stop_loss = None
        take_profit = None

    # =====================================================
    # ROUND
    # =====================================================

    entry = round(
        entry,
        2
    )

    stop_loss = (
        round(stop_loss, 2)
        if stop_loss is not None
        else None
    )

    take_profit = (
        round(take_profit, 2)
        if take_profit is not None
        else None
    )

    # =====================================================
    # RESULT
    # =====================================================

    return {

        "status": "ok",

        "version": VERSION,

        "signal": signal,

        "confidence": confidence,

        "price": round(
            price,
            2
        ),

        "entry": entry,

        "stop_loss": stop_loss,

        "take_profit": take_profit,

        "risk_reward": (
            2
            if signal != "HOLD"
            else None
        ),

        "indicators": {

            "ema20": round(
                ema20,
                2
            ),

            "ema50": round(
                ema50,
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
                vwap,
                2
            ),

            "volume": round(
                volume,
                6
            ),

            "volume_avg20": round(
                volume_avg20,
                6
            ),

            "volume_ratio": round(
                volume_ratio,
                2
            ),

            "trades": int(
                trades
            ),

            "trades_avg20": round(
                trades_avg20,
                2
            ),

            "trades_ratio": round(
                trades_ratio,
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
