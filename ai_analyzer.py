import pandas as pd
import numpy as np


VERSION = "1.6.1"


# =========================================================
# EMA
# =========================================================

def calculate_ema(series, period):
    return series.ewm(
        span=period,
        adjust=False
    ).mean()


# =========================================================
# RSI
# =========================================================

def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan
    )

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi.fillna(50)


# =========================================================
# ATR
# =========================================================

def calculate_atr(df, period=14):

    high_low = (
        df["high"] -
        df["low"]
    )

    high_close = (
        df["high"] -
        df["close"].shift(1)
    ).abs()

    low_close = (
        df["low"] -
        df["close"].shift(1)
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    return true_range.rolling(
        period
    ).mean()


# =========================================================
# VWAP
# =========================================================

def calculate_vwap(df):

    # Kraken đã cung cấp VWAP
    if "vwap" in df.columns:

        value = df["vwap"].iloc[-1]

        if pd.notna(value):
            return float(value)

    # Nếu không có VWAP thì tự tính
    typical_price = (
        df["high"] +
        df["low"] +
        df["close"]
    ) / 3

    cumulative_volume = (
        df["volume"].cumsum()
    )

    cumulative_price_volume = (
        typical_price *
        df["volume"]
    ).cumsum()

    vwap = (
        cumulative_price_volume /
        cumulative_volume.replace(
            0,
            np.nan
        )
    )

    return float(
        vwap.iloc[-1]
    )


# =========================================================
# MAIN ANALYZER
# =========================================================

def analyze_market(candles):

    # -----------------------------------------------------
    # Kiểm tra dữ liệu
    # -----------------------------------------------------

    if not candles or len(candles) < 50:

        return {
            "status": "error",
            "message": "Cần ít nhất 50 nến"
        }

    df = pd.DataFrame(
        candles
    ).copy()

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

    # Trades có thể không có
    if "trades" not in df.columns:

        df["trades"] = 0

    df["trades"] = pd.to_numeric(
        df["trades"],
        errors="coerce"
    ).fillna(0)

    df = df.dropna().reset_index(
        drop=True
    )

    if len(df) < 50:

        return {
            "status": "error",
            "message": "Sau khi làm sạch dữ liệu còn dưới 50 nến"
        }

    # -----------------------------------------------------
    # EMA
    # -----------------------------------------------------

    df["ema20"] = calculate_ema(
        df["close"],
        20
    )

    df["ema50"] = calculate_ema(
        df["close"],
        50
    )

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    df["rsi"] = calculate_rsi(
        df["close"],
        14
    )

    # -----------------------------------------------------
    # ATR
    # -----------------------------------------------------

    df["atr"] = calculate_atr(
        df,
        14
    )

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    ema12 = calculate_ema(
        df["close"],
        12
    )

    ema26 = calculate_ema(
        df["close"],
        26
    )

    df["macd"] = (
        ema12 -
        ema26
    )

    df["macd_signal"] = calculate_ema(
        df["macd"],
        9
    )

    df["macd_histogram"] = (
        df["macd"] -
        df["macd_signal"]
    )

    # -----------------------------------------------------
    # VWAP
    # -----------------------------------------------------

    vwap = float(
        calculate_vwap(df)
    )

    # -----------------------------------------------------
    # Current candle
    # -----------------------------------------------------

    current_price = float(
        df["close"].iloc[-1]
    )

    current_open = float(
        df["open"].iloc[-1]
    )

    current_volume = float(
        df["volume"].iloc[-1]
    )

    current_trades = int(
        df["trades"].iloc[-1]
    )

    # -----------------------------------------------------
    # Volume average
    # -----------------------------------------------------

    volume_avg20 = float(
        df["volume"]
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    if volume_avg20 > 0:

        volume_ratio = float(
            current_volume /
            volume_avg20
        )

    else:

        volume_ratio = 0.0

    # -----------------------------------------------------
    # Trades average
    # -----------------------------------------------------

    trades_avg20 = float(
        df["trades"]
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    if trades_avg20 > 0:

        trades_ratio = float(
            current_trades /
            trades_avg20
        )

    else:

        trades_ratio = 0.0

    # -----------------------------------------------------
    # Support / Resistance
    # -----------------------------------------------------

    recent = df.tail(30)

    support = float(
        recent["low"].min()
    )

    resistance = float(
        recent["high"].max()
    )

    # -----------------------------------------------------
    # Breakout / Breakdown
    # -----------------------------------------------------

    previous20 = df.iloc[-21:-1]

    previous_high = float(
        previous20["high"].max()
    )

    previous_low = float(
        previous20["low"].min()
    )

    breakout = bool(
        current_price >
        previous_high
    )

    breakdown = bool(
        current_price <
        previous_low
    )

    # -----------------------------------------------------
    # Candle direction
    # -----------------------------------------------------

    bullish_candle = bool(
        current_price >
        current_open
    )

    bearish_candle = bool(
        current_price <
        current_open
    )

    # -----------------------------------------------------
    # Indicator values
    # -----------------------------------------------------

    ema20 = float(
        df["ema20"].iloc[-1]
    )

    ema50 = float(
        df["ema50"].iloc[-1]
    )

    rsi = float(
        df["rsi"].iloc[-1]
    )

    atr = float(
        df["atr"].iloc[-1]
    )

    macd = float(
        df["macd"].iloc[-1]
    )

    macd_signal = float(
        df["macd_signal"].iloc[-1]
    )

    macd_histogram = float(
        df["macd_histogram"].iloc[-1]
    )

    # Nếu ATR lỗi
    if not np.isfinite(atr):

        atr = float(
            (
                df["high"] -
                df["low"]
            ).tail(14).mean()
        )

    # -----------------------------------------------------
    # SCORE
    # -----------------------------------------------------

    score = 0

    reasons = []

    # =====================================================
    # EMA TREND
    # =====================================================

    if ema20 > ema50:

        score += 2

        reasons.append(
            "EMA20 nằm trên EMA50"
        )

    else:

        score -= 2

        reasons.append(
            "EMA20 nằm dưới EMA50"
        )

    # =====================================================
    # PRICE vs EMA20
    # =====================================================

    if current_price > ema20:

        score += 2

        reasons.append(
            "Giá nằm trên EMA20"
        )

    else:

        score -= 2

        reasons.append(
            "Giá nằm dưới EMA20"
        )

    # =====================================================
    # RSI
    # =====================================================

    if rsi >= 55:

        score += 2

        reasons.append(
            "RSI mạnh"
        )

    elif rsi >= 50:

        score += 1

        reasons.append(
            "RSI hơi tích cực"
        )

    elif rsi <= 35:

        score -= 2

        reasons.append(
            "RSI rất yếu"
        )

    else:

        score -= 1

        reasons.append(
            "RSI yếu"
        )

    # =====================================================
    # MACD
    # =====================================================

    if macd > macd_signal:

        score += 2

        reasons.append(
            "MACD tích cực"
        )

    else:

        score -= 2

        reasons.append(
            "MACD tiêu cực"
        )

    # MACD Histogram

    if macd_histogram > 0:

        score += 1

    else:

        score -= 1

    # =====================================================
    # VWAP
    # =====================================================

    if current_price > vwap:

        score += 2

        reasons.append(
            "Giá nằm trên VWAP"
        )

    else:

        score -= 2

        reasons.append(
            "Giá nằm dưới VWAP"
        )

    # =====================================================
    # VOLUME CONFIRMATION
    # =====================================================

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

    # =====================================================
    # TRADES CONFIRMATION
    # =====================================================

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

    # =====================================================
    # BREAKOUT
    # =====================================================

    if breakout:

        score += 3

        reasons.append(
            "Breakout vượt đỉnh 20 nến"
        )

    # =====================================================
    # BREAKDOWN
    # =====================================================

    if breakdown:

        score -= 3

        reasons.append(
            "Breakdown thủng đáy 20 nến"
        )

    # =====================================================
    # MARKET CONDITION
    # =====================================================

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

    # =====================================================
    # INITIAL SIGNAL
    # =====================================================

    if score >= 8:

        signal = "BUY"

    elif score <= -8:

        signal = "SELL"

    else:

        signal = "HOLD"

    # =====================================================
    # LIQUIDITY CONFIRMATION
    # =====================================================

    low_volume = bool(
        volume_ratio < 0.5
    )

    low_trades = bool(
        trades_ratio < 0.5
    )

    confirmation_warning = bool(
        low_volume or
        low_trades
    )

    # =====================================================
    # FILTER BUY / SELL
    # =====================================================

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

    # =====================================================
    # CONFIDENCE
    # =====================================================

    confidence = (
        abs(float(score)) /
        17.0
    ) * 100.0

    confidence = min(
        confidence,
        95.0
    )

    # Volume thấp
    if low_volume:

        confidence *= 0.75

    # Trades thấp
    if low_trades:

        confidence *= 0.85

    if signal == "HOLD":

        confidence = max(
            50.0,
            confidence
        )

    confidence = round(
        float(confidence),
        2
    )

    # =====================================================
    # RISK MANAGEMENT
    # =====================================================

    entry = float(
        current_price
    )

    stop_loss = None
    take_profit = None
    risk_reward = None

    if signal == "BUY":

        stop_loss = float(
            entry -
            (1.5 * atr)
        )

        take_profit = float(
            entry +
            (3.0 * atr)
        )

        risk_reward = 2.0

    elif signal == "SELL":

        stop_loss = float(
            entry +
            (1.5 * atr)
        )

        take_profit = float(
            entry -
            (3.0 * atr)
        )

        risk_reward = 2.0

    # =====================================================
    # TRADE ALLOWED
    # =====================================================

    trade_allowed = bool(
        signal in ["BUY", "SELL"]
        and not low_volume
        and not low_trades
    )

    # =====================================================
    # CONFIRMATION REASON
    # =====================================================

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

    # =====================================================
    # FINAL JSON-SAFE RESULT
    # =====================================================

    return {

        "status": "ok",

        "version": VERSION,

        "signal": str(
            signal
        ),

        "confidence": float(
            confidence
        ),

        "market_condition": str(
            market_condition
        ),

        "trade_allowed": bool(
            trade_allowed
        ),

        "confirmation_warning": bool(
            confirmation_warning
        ),

        "confirmation_reason": str(
            confirmation_reason
        ),

        "price": float(
            entry
        ),

        "entry": float(
            entry
        ),

        "stop_loss": (
            float(
                round(
                    stop_loss,
                    2
                )
            )
            if stop_loss is not None
            else None
        ),

        "take_profit": (
            float(
                round(
                    take_profit,
                    2
                )
            )
            if take_profit is not None
            else None
        ),

        "risk_reward": (
            float(
                risk_reward
            )
            if risk_reward is not None
            else None
        ),

        "indicators": {

            "ema20": float(
                round(
                    ema20,
                    2
                )
            ),

            "ema50": float(
                round(
                    ema50,
                    2
                )
            ),

            "rsi": float(
                round(
                    rsi,
                    2
                )
            ),

            "atr": float(
                round(
                    atr,
                    2
                )
            ),

            "macd": float(
                round(
                    macd,
                    4
                )
            ),

            "macd_signal": float(
                round(
                    macd_signal,
                    4
                )
            ),

            "macd_histogram": float(
                round(
                    macd_histogram,
                    4
                )
            ),

            "vwap": float(
                round(
                    vwap,
                    2
                )
            ),

            "volume": float(
                round(
                    current_volume,
                    6
                )
            ),

            "volume_avg20": float(
                round(
                    volume_avg20,
                    6
                )
            ),

            "volume_ratio": float(
                round(
                    volume_ratio,
                    2
                )
            ),

            "trades": int(
                current_trades
            ),

            "trades_avg20": float(
                round(
                    trades_avg20,
                    2
                )
            ),

            "trades_ratio": float(
                round(
                    trades_ratio,
                    2
                )
            )
        },

        "support": float(
            round(
                support,
                2
            )
        ),

        "resistance": float(
            round(
                resistance,
                2
            )
        ),

        "breakout": bool(
            breakout
        ),

        "breakdown": bool(
            breakdown
        ),

        "score": int(
            score
        ),

        "reasons": [
            str(reason)
            for reason in reasons
        ],

        "candle_count": int(
            len(df)
        )
    }
```
