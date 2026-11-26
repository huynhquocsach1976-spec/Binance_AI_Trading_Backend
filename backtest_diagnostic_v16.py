import math
import pandas as pd
import numpy as np

from ai_analyzer import analyze_market


VERSION = "1.6.0"
STRATEGY = "Signal v1.6.1"


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        value = float(value)
        if not math.isfinite(value):
            return default
        return value
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def normalize_data(data):
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        raise ValueError("Data phải là DataFrame hoặc list.")

    rename_map = {}

    if "timestamp" in df.columns and "time" not in df.columns:
        rename_map["timestamp"] = "time"

    if "date" in df.columns and "time" not in df.columns:
        rename_map["date"] = "time"

    if "Timestamp" in df.columns and "time" not in df.columns:
        rename_map["Timestamp"] = "time"

    if rename_map:
        df = df.rename(columns=rename_map)

    required = ["open", "high", "low", "close", "volume"]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Thiếu cột bắt buộc: {col}")

    if "trades" not in df.columns:
        if "count" in df.columns:
            df["trades"] = df["count"]
        else:
            df["trades"] = 1.0

    numeric_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trades",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])

    if len(df) < 100:
        raise ValueError("Cần ít nhất 100 candles.")

    return df.reset_index(drop=True)


# ============================================================
# PRICE / RETURN HELPERS
# ============================================================

def apply_entry_slippage(price, signal, slippage):
    price = safe_float(price)

    if signal == "BUY":
        return price * (1 + slippage)

    if signal == "SELL":
        return price * (1 - slippage)

    return price


def apply_exit_slippage(price, signal, slippage):
    price = safe_float(price)

    if signal == "BUY":
        return price * (1 - slippage)

    if signal == "SELL":
        return price * (1 + slippage)

    return price


def calculate_trade_return(entry_price, exit_price, signal):
    entry_price = safe_float(entry_price)
    exit_price = safe_float(exit_price)

    if entry_price <= 0:
        return 0.0

    if signal == "BUY":
        return (exit_price - entry_price) / entry_price

    if signal == "SELL":
        return (entry_price - exit_price) / entry_price

    return 0.0


# ============================================================
# SCORE GROUP
# ============================================================

def score_group(signal, score):
    if signal == "BUY":
        if score <= 9:
            return "BUY_8_9"
        if score <= 11:
            return "BUY_10_11"
        if score <= 14:
            return "BUY_12_14"
        return "BUY_15_PLUS"

    if signal == "SELL":
        if score >= -9:
            return "SELL_-8_-9"
        if score >= -11:
            return "SELL_-10_-11"
        if score >= -14:
            return "SELL_-12_-14"
        return "SELL_-15_MINUS"

    return "OTHER"


# ============================================================
# EXIT ANALYSIS
# ============================================================

def calculate_holding_candles(entry_index, exit_index):
    try:
        return max(1, int(exit_index) - int(entry_index) + 1)
    except Exception:
        return 1


# ============================================================
# SINGLE TRADE ANALYSIS
# ============================================================

def analyze_trade_record(
    df,
    signal_result,
    signal,
    i,
    initial_balance,
    fee_rate,
    slippage,
):
    entry_index = i + 1

    if entry_index >= len(df):
        return None

    raw_entry = safe_float(df.iloc[entry_index]["open"])

    entry_price = apply_entry_slippage(
        raw_entry,
        signal,
        slippage,
    )

    atr = safe_float(signal_result.get("atr"), 0.0)

    if atr <= 0:
        start_atr = max(0, i - 13)

        ranges = (
            df.iloc[start_atr:i + 1]["high"]
            - df.iloc[start_atr:i + 1]["low"]
        )

        atr = safe_float(ranges.mean(), 0.0)

    if atr <= 0:
        return None

    stop_loss = safe_float(
        signal_result.get("stop_loss"),
        0.0,
    )

    take_profit = safe_float(
        signal_result.get("take_profit"),
        0.0,
    )

    if stop_loss <= 0 or take_profit <= 0:

        if signal == "BUY":
            stop_loss = entry_price - 1.5 * atr
            take_profit = entry_price + 3.0 * atr

        else:
            stop_loss = entry_price + 1.5 * atr
            take_profit = entry_price - 3.0 * atr

    exit_index = None
    exit_price_raw = None
    exit_reason = None

    # --------------------------------------------------------
    # SEARCH EXIT
    # --------------------------------------------------------

    for j in range(entry_index, len(df)):

        candle_high = safe_float(df.iloc[j]["high"])
        candle_low = safe_float(df.iloc[j]["low"])

        if signal == "BUY":

            # SL first
            if candle_low <= stop_loss:
                exit_index = j
                exit_price_raw = stop_loss
                exit_reason = "SL"
                break

            # TP second
            if candle_high >= take_profit:
                exit_index = j
                exit_price_raw = take_profit
                exit_reason = "TP"
                break

        elif signal == "SELL":

            # SL first
            if candle_high >= stop_loss:
                exit_index = j
                exit_price_raw = stop_loss
                exit_reason = "SL"
                break

            # TP second
            if candle_low <= take_profit:
                exit_index = j
                exit_price_raw = take_profit
                exit_reason = "TP"
                break

    # --------------------------------------------------------
    # END OF DATA
    # --------------------------------------------------------

    if exit_index is None:

        exit_index = len(df) - 1

        exit_price_raw = safe_float(
            df.iloc[exit_index]["close"]
        )

        exit_reason = "EOD"

    exit_price = apply_exit_slippage(
        exit_price_raw,
        signal,
        slippage,
    )

    trade_return = calculate_trade_return(
        entry_price,
        exit_price,
        signal,
    )

    profit_before_fee = initial_balance * trade_return

    entry_fee = initial_balance * fee_rate

    exit_balance_before_fee = (
        initial_balance + profit_before_fee
    )

    exit_fee = (
        exit_balance_before_fee * fee_rate
    )

    trade_fee = entry_fee + exit_fee

    profit_after_fee = (
        profit_before_fee - trade_fee
    )

    holding_candles = calculate_holding_candles(
        entry_index,
        exit_index,
    )

    # --------------------------------------------------------
    # INDICATORS FROM SIGNAL
    # --------------------------------------------------------

    ema20 = safe_float(signal_result.get("ema20"), 0.0)
    ema50 = safe_float(signal_result.get("ema50"), 0.0)
    rsi = safe_float(signal_result.get("rsi"), 0.0)
    atr_value = safe_float(signal_result.get("atr"), atr)
    macd = safe_float(signal_result.get("macd"), 0.0)
    macd_signal = safe_float(
        signal_result.get("macd_signal"),
        0.0,
    )
    macd_histogram = safe_float(
        signal_result.get("macd_histogram"),
        0.0,
    )
    vwap = safe_float(signal_result.get("vwap"), 0.0)
    volume_ratio = safe_float(
        signal_result.get("volume_ratio"),
        0.0,
    )
    trades_ratio = safe_float(
        signal_result.get("trades_ratio"),
        0.0,
    )

    close_price = safe_float(
        df.iloc[i]["close"]
    )

    # --------------------------------------------------------
    # FEATURE FLAGS
    # --------------------------------------------------------

    ema_bearish = (
        ema20 < ema50
    )

    price_below_ema20 = (
        close_price < ema20
    )

    rsi_weak = (
        rsi < 50
    )

    macd_bearish = (
        macd < macd_signal
    )

    macd_hist_bearish = (
        macd_histogram < 0
    )

    below_vwap = (
        close_price < vwap
        if vwap > 0
        else False
    )

    low_volume = (
        volume_ratio < 0.5
    )

    low_trades = (
        trades_ratio < 0.5
    )

    return {
        "signal": signal,

        "score": safe_int(
            signal_result.get("score"),
            0,
        ),

        "score_group": score_group(
            signal,
            safe_int(signal_result.get("score"), 0),
        ),

        "market_condition": signal_result.get(
            "market_condition"
        ),

        "entry_index": entry_index,
        "exit_index": exit_index,

        "entry_price": entry_price,
        "exit_price": exit_price,

        "stop_loss": stop_loss,
        "take_profit": take_profit,

        "exit_reason": exit_reason,

        "return_pct": trade_return * 100,

        "profit_before_fee": profit_before_fee,

        "fees": trade_fee,

        "profit": profit_after_fee,

        "holding_candles": holding_candles,

        "atr": atr_value,

        "rsi": rsi,

        "ema20": ema20,
        "ema50": ema50,

        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,

        "vwap": vwap,

        "volume_ratio": volume_ratio,
        "trades_ratio": trades_ratio,

        "ema_bearish": ema_bearish,
        "price_below_ema20": price_below_ema20,
        "rsi_weak": rsi_weak,
        "macd_bearish": macd_bearish,
        "macd_hist_bearish": macd_hist_bearish,
        "below_vwap": below_vwap,
        "low_volume": low_volume,
        "low_trades": low_trades,
    }


# ============================================================
# AGGREGATION
# ============================================================

def aggregate_trades(trades):

    if not trades:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit": 0.0,
            "profit_before_fees": 0.0,
            "fees": 0.0,
            "profit_factor": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "avg_holding_candles": 0.0,
        }

    profits = [
        safe_float(x["profit"])
        for x in trades
    ]

    positive = [
        x for x in profits
        if x > 0
    ]

    negative = [
        x for x in profits
        if x < 0
    ]

    gross_profit = sum(positive)
    gross_loss = abs(sum(negative))

    pf = (
        gross_profit / gross_loss
        if gross_loss > 0
        else 0.0
    )

    wins = len(positive)
    losses = len(negative)

    return {
        "trades": len(trades),

        "wins": wins,

        "losses": losses,

        "win_rate": (
            wins / len(trades) * 100
            if trades
            else 0.0
        ),

        "profit": sum(profits),

        "profit_before_fees": sum(
            safe_float(x["profit_before_fee"])
            for x in trades
        ),

        "fees": sum(
            safe_float(x["fees"])
            for x in trades
        ),

        "profit_factor": pf,

        "avg_profit": (
            sum(positive) / wins
            if wins
            else 0.0
        ),

        "avg_loss": (
            sum(negative) / losses
            if losses
            else 0.0
        ),

        "avg_holding_candles": (
            sum(
                safe_float(x["holding_candles"])
                for x in trades
            )
            / len(trades)
        ),
    }


# ============================================================
# FEATURE DIAGNOSTIC
# ============================================================

def feature_diagnostic(trades):

    if not trades:
        return {}

    feature_names = [
        "ema_bearish",
        "price_below_ema20",
        "rsi_weak",
        "macd_bearish",
        "macd_hist_bearish",
        "below_vwap",
        "low_volume",
        "low_trades",
    ]

    result = {}

    for feature in feature_names:

        active = [
            x for x in trades
            if bool(x.get(feature))
        ]

        inactive = [
            x for x in trades
            if not bool(x.get(feature))
        ]

        active_stats = aggregate_trades(active)
        inactive_stats = aggregate_trades(inactive)

        result[feature] = {
            "active": active_stats,
            "inactive": inactive_stats,
        }

    return result


# ============================================================
# SCORE DIAGNOSTIC
# ============================================================

def score_diagnostic(trades):

    groups = {}

    for trade in trades:

        group = trade["score_group"]

        if group not in groups:
            groups[group] = []

        groups[group].append(trade)

    result = {}

    for group, items in groups.items():

        result[group] = aggregate_trades(items)

    return result


# ============================================================
# EXIT DIAGNOSTIC
# ============================================================

def exit_diagnostic(trades):

    result = {}

    reasons = ["SL", "TP", "EOD"]

    for reason in reasons:

        items = [
            x for x in trades
            if x["exit_reason"] == reason
        ]

        result[reason] = aggregate_trades(items)

    return result


# ============================================================
# MARKET CONDITION DIAGNOSTIC
# ============================================================

def market_condition_diagnostic(trades):

    groups = {}

    for trade in trades:

        condition = trade.get(
            "market_condition"
        )

        if condition is None:
            condition = "UNKNOWN"

        if condition not in groups:
            groups[condition] = []

        groups[condition].append(trade)

    return {
        condition: aggregate_trades(items)
        for condition, items in groups.items()
    }


# ============================================================
# ATR DIAGNOSTIC
# ============================================================

def atr_diagnostic(trades):

    if not trades:
        return {}

    atr_values = [
        safe_float(x["atr"])
        for x in trades
        if safe_float(x["atr"]) > 0
    ]

    if not atr_values:
        return {}

    return {
        "min": min(atr_values),
        "max": max(atr_values),
        "average": sum(atr_values) / len(atr_values),
    }


# ============================================================
# RSI DIAGNOSTIC
# ============================================================

def rsi_diagnostic(trades):

    groups = {
        "RSI_LT_30": [],
        "RSI_30_40": [],
        "RSI_40_50": [],
        "RSI_50_60": [],
        "RSI_GTE_60": [],
    }

    for trade in trades:

        rsi = safe_float(
            trade.get("rsi")
        )

        if rsi < 30:
            groups["RSI_LT_30"].append(trade)

        elif rsi < 40:
            groups["RSI_30_40"].append(trade)

        elif rsi < 50:
            groups["RSI_40_50"].append(trade)

        elif rsi < 60:
            groups["RSI_50_60"].append(trade)

        else:
            groups["RSI_GTE_60"].append(trade)

    return {
        group: aggregate_trades(items)
        for group, items in groups.items()
    }


# ============================================================
# HOLDING TIME DIAGNOSTIC
# ============================================================

def holding_diagnostic(trades):

    groups = {
        "1_3": [],
        "4_8": [],
        "9_20": [],
        "21_PLUS": [],
    }

    for trade in trades:

        candles = safe_int(
            trade.get("holding_candles"),
            0,
        )

        if candles <= 3:
            groups["1_3"].append(trade)

        elif candles <= 8:
            groups["4_8"].append(trade)

        elif candles <= 20:
            groups["9_20"].append(trade)

        else:
            groups["21_PLUS"].append(trade)

    return {
        group: aggregate_trades(items)
        for group, items in groups.items()
    }


# ============================================================
# MAIN DIAGNOSTIC
# ============================================================

def run_diagnostic(
    data,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001,
):

    df = normalize_data(data)

    all_trades = []

    signal_cache = {}

    analyzer_error_count = 0

    first_analyzer_error = None

    signal_buy_count = 0
    signal_sell_count = 0
    signal_hold_count = 0

    # --------------------------------------------------------
    # CACHE SIGNAL ONCE PER CANDLE
    # --------------------------------------------------------

    for i in range(100, len(df) - 1):

        analysis_df = df.iloc[:i + 1].copy()

        try:

            try:
                signal_result = analyze_market(
                    analysis_df
                )

            except TypeError:

                signal_result = analyze_market(
                    data=analysis_df
                )

            if not isinstance(signal_result, dict):
                signal_result = {}

        except Exception as exc:

            analyzer_error_count += 1

            if first_analyzer_error is None:
                first_analyzer_error = str(exc)

            continue

        signal_cache[i] = signal_result

        signal = str(
            signal_result.get(
                "signal",
                "HOLD"
            )
        ).upper()

        if signal == "BUY":
            signal_buy_count += 1

        elif signal == "SELL":
            signal_sell_count += 1

        else:
            signal_hold_count += 1

    # --------------------------------------------------------
    # EXECUTE DIAGNOSTIC TRADES
    # --------------------------------------------------------

    i = 100

    while i < len(df) - 1:

        if i not in signal_cache:
            i += 1
            continue

        signal_result = signal_cache[i]

        signal = str(
            signal_result.get(
                "signal",
                "HOLD"
            )
        ).upper()

        trade_allowed = bool(
            signal_result.get(
                "trade_allowed",
                signal in ["BUY", "SELL"]
            )
        )

        if signal not in ["BUY", "SELL"]:
            i += 1
            continue

        if not trade_allowed:
            i += 1
            continue

        trade = analyze_trade_record(
            df=df,
            signal_result=signal_result,
            signal=signal,
            i=i,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

        if trade is None:
            i += 1
            continue

        all_trades.append(trade)

        # EXACT ENGINE BEHAVIOR:
        # after trade, jump after exit candle

        i = trade["exit_index"] + 1

    # ========================================================
    # SPLIT BUY / SELL
    # ========================================================

    buy_trades = [
        x for x in all_trades
        if x["signal"] == "BUY"
    ]

    sell_trades = [
        x for x in all_trades
        if x["signal"] == "SELL"
    ]

    # ========================================================
    # COMPARISON
    # ========================================================

    buy_stats = aggregate_trades(
        buy_trades
    )

    sell_stats = aggregate_trades(
        sell_trades
    )

    # ========================================================
    # DIFFERENCE
    # ========================================================

    comparison = {
        "profit_difference_buy_minus_sell":
            buy_stats["profit"]
            - sell_stats["profit"],

        "win_rate_difference_pct":
            buy_stats["win_rate"]
            - sell_stats["win_rate"],

        "profit_factor_difference":
            buy_stats["profit_factor"]
            - sell_stats["profit_factor"],

        "avg_profit_difference":
            buy_stats["avg_profit"]
            - sell_stats["avg_profit"],

        "avg_loss_difference":
            buy_stats["avg_loss"]
            - sell_stats["avg_loss"],

        "avg_holding_difference":
            buy_stats["avg_holding_candles"]
            - sell_stats["avg_holding_candles"],
    }

    # ========================================================
    # FINAL
    # ========================================================

    return {
        "status": "ok",

        "version": VERSION,

        "symbol": "BTCUSDT",

        "timeframe": "1h",

        "candles": len(df),

        "actual_candles": len(df),

        "strategy": STRATEGY,

        "method": (
            "Diagnostic BUY vs SELL sử dụng "
            "cùng Signal v1.6.1 và execution mechanics "
            "của backtest_engine.py v1.1.2."
        ),

        "warning": (
            "Diagnostic không thay đổi Signal v1.6.1 "
            "và không thay đổi backtest_engine.py."
        ),

        "debug": {
            "signal_calculations": len(signal_cache),

            "signal_buy_count": signal_buy_count,

            "signal_sell_count": signal_sell_count,

            "signal_hold_count": signal_hold_count,

            "analyzer_error_count":
                analyzer_error_count,

            "first_analyzer_error":
                first_analyzer_error,
        },

        "overall": aggregate_trades(
            all_trades
        ),

        "buy": {
            "summary": buy_stats,

            "score_groups":
                score_diagnostic(
                    buy_trades
                ),

            "market_conditions":
                market_condition_diagnostic(
                    buy_trades
                ),

            "exit_reasons":
                exit_diagnostic(
                    buy_trades
                ),

            "rsi":
                rsi_diagnostic(
                    buy_trades
                ),

            "atr":
                atr_diagnostic(
                    buy_trades
                ),

            "holding":
                holding_diagnostic(
                    buy_trades
                ),

            "features":
                feature_diagnostic(
                    buy_trades
                ),
        },

        "sell": {
            "summary": sell_stats,

            "score_groups":
                score_diagnostic(
                    sell_trades
                ),

            "market_conditions":
                market_condition_diagnostic(
                    sell_trades
                ),

            "exit_reasons":
                exit_diagnostic(
                    sell_trades
                ),

            "rsi":
                rsi_diagnostic(
                    sell_trades
                ),

            "atr":
                atr_diagnostic(
                    sell_trades
                ),

            "holding":
                holding_diagnostic(
                    sell_trades
                ),

            "features":
                feature_diagnostic(
                    sell_trades
                ),
        },

        "comparison": comparison,

        "trades": all_trades,
    }
