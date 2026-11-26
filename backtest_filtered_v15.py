import math
import pandas as pd
import numpy as np

from ai_analyzer import analyze_market


VERSION = "1.5.2"
STRATEGY = "Signal v1.6.1"


# =========================================================
# SAFE HELPERS
# =========================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return float(default)

        value = float(value)

        if not math.isfinite(value):
            return float(default)

        return value

    except Exception:
        return float(default)


def safe_int(value, default=0):
    try:
        if value is None:
            return int(default)

        return int(value)

    except Exception:
        return int(default)


def native(value):

    if isinstance(value, dict):
        return {
            str(k): native(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            native(v)
            for v in value
        ]

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    if isinstance(value, np.bool_):
        return bool(value)

    if isinstance(value, float):

        if not math.isfinite(value):
            return None

    return value


# =========================================================
# NORMALIZE DATA
#
# Giữ giống backtest_engine.py
# =========================================================

def normalize_data(data):

    if isinstance(data, pd.DataFrame):

        df = data.copy()

    elif isinstance(data, list):

        df = pd.DataFrame(data)

    else:

        raise ValueError(
            "data phải là DataFrame hoặc list candles"
        )

    if df.empty:

        raise ValueError(
            "Không có dữ liệu candle"
        )

    rename_map = {}

    if "timestamp" in df.columns and "time" not in df.columns:
        rename_map["timestamp"] = "time"

    if "date" in df.columns and "time" not in df.columns:
        rename_map["date"] = "time"

    if "Timestamp" in df.columns and "time" not in df.columns:
        rename_map["Timestamp"] = "time"

    if rename_map:
        df = df.rename(columns=rename_map)

    required = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for col in required:

        if col not in df.columns:

            raise ValueError(
                f"Thiếu column: {col}"
            )

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
        "trades"
    ]

    for col in numeric_cols:

        df[col] = pd.to_numeric(
            df[col],
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

    if len(df) < 100:

        raise ValueError(
            f"Không đủ dữ liệu để backtest: {len(df)} candles"
        )

    return df


# =========================================================
# SLIPPAGE
#
# Giữ giống backtest_engine.py
# =========================================================

def apply_entry_slippage(
    price,
    signal,
    slippage
):

    price = safe_float(price)
    slippage = safe_float(slippage)

    if signal == "BUY":

        return price * (1.0 + slippage)

    if signal == "SELL":

        return price * (1.0 - slippage)

    return price


def apply_exit_slippage(
    price,
    signal,
    slippage
):

    price = safe_float(price)
    slippage = safe_float(slippage)

    if signal == "BUY":

        return price * (1.0 - slippage)

    if signal == "SELL":

        return price * (1.0 + slippage)

    return price


# =========================================================
# TRADE RETURN
#
# Giữ giống backtest_engine.py
# =========================================================

def calculate_trade_return(
    signal,
    entry_price,
    exit_price
):

    entry_price = safe_float(entry_price)
    exit_price = safe_float(exit_price)

    if entry_price <= 0:

        return 0.0

    if signal == "BUY":

        return (
            exit_price - entry_price
        ) / entry_price

    if signal == "SELL":

        return (
            entry_price - exit_price
        ) / entry_price

    return 0.0


# =========================================================
# SIGNAL HELPERS
# =========================================================

def get_score(signal_result):

    value = signal_result.get("score")

    if value is None:
        return None

    try:
        return safe_int(value, 0)
    except Exception:
        return None


def get_market_condition(signal_result):

    value = signal_result.get(
        "market_condition",
        signal_result.get(
            "market_regime",
            signal_result.get(
                "regime",
                signal_result.get(
                    "condition",
                    None
                )
            )
        )
    )

    if value is None:
        return "UNKNOWN"

    value = str(value).upper().strip()

    if not value:
        return "UNKNOWN"

    return value


def should_remove_trade(
    mode,
    signal,
    score
):

    if score is None:
        return False

    # -----------------------------------------------------
    # REMOVE SELL score -8 / -9
    # -----------------------------------------------------

    if mode in [
        "REMOVE_SELL_-8_-9",
        "REMOVE_BOTH"
    ]:

        if (
            signal == "SELL"
            and -9 <= score <= -8
        ):

            return True

    # -----------------------------------------------------
    # REMOVE BUY score 12 / 13 / 14
    # -----------------------------------------------------

    if mode in [
        "REMOVE_BUY_12_14",
        "REMOVE_BOTH"
    ]:

        if (
            signal == "BUY"
            and 12 <= score <= 14
        ):

            return True

    return False


# =========================================================
# SIGNAL CACHE
#
# QUAN TRỌNG:
# Engine bắt đầu từ i = 100.
# =========================================================

def build_signal_cache(df):

    cache = {}

    signal_buy_count = 0
    signal_sell_count = 0
    signal_hold_count = 0

    analyzer_error_count = 0
    first_analyzer_error = None

    # =====================================================
    # GIỐNG BACKTEST ENGINE:
    #
    # i = 100
    # while i < len(df) - 1
    # =====================================================

    for i in range(100, len(df) - 1):

        analysis_df = df.iloc[
            :i + 1
        ].copy()

        try:

            signal_result = analyze_market(
                analysis_df
            )

        except TypeError:

            try:

                signal_result = analyze_market(
                    data=analysis_df
                )

            except Exception as e:

                analyzer_error_count += 1

                if first_analyzer_error is None:

                    first_analyzer_error = (
                        f"{type(e).__name__}: {str(e)}"
                    )

                cache[i] = None

                continue

        except Exception as e:

            analyzer_error_count += 1

            if first_analyzer_error is None:

                first_analyzer_error = (
                    f"{type(e).__name__}: {str(e)}"
                )

            cache[i] = None

            continue

        if not isinstance(
            signal_result,
            dict
        ):

            analyzer_error_count += 1

            if first_analyzer_error is None:

                first_analyzer_error = (
                    "analyze_market không trả về dict"
                )

            cache[i] = None

            continue

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

        cache[i] = signal_result

    return {
        "cache": cache,

        "signal_buy_count": signal_buy_count,

        "signal_sell_count": signal_sell_count,

        "signal_hold_count": signal_hold_count,

        "analyzer_error_count": analyzer_error_count,

        "first_analyzer_error": first_analyzer_error
    }


# =========================================================
# RUN FILTERED BACKTEST
#
# Đây là execution logic bám sát backtest_engine.py.
#
# Khác biệt DUY NHẤT:
# trước khi ENTRY, filter có thể chặn trade.
# =========================================================

def run_filtered_backtest(
    df,
    signal_cache,
    mode,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):

    initial_balance = safe_float(
        initial_balance,
        1000.0
    )

    fee_rate = safe_float(
        fee_rate,
        0.0004
    )

    slippage = safe_float(
        slippage,
        0.0001
    )

    balance = initial_balance

    trades = []

    equity_curve = []

    wins = 0
    losses = 0

    buy_trades = 0
    buy_wins = 0

    sell_trades = 0
    sell_wins = 0

    gross_profit = 0.0
    gross_loss = 0.0

    total_fees = 0.0

    max_balance = initial_balance
    max_drawdown = 0.0

    current_win_streak = 0
    current_loss_streak = 0

    max_win_streak = 0
    max_loss_streak = 0

    trade_allowed_false_count = 0

    filter_sell_count = 0
    filter_buy_count = 0

    # =====================================================
    # EXACT ENGINE LOOP
    # =====================================================

    i = 100

    while i < len(df) - 1:

        signal_result = signal_cache.get(i)

        # -------------------------------------------------
        # Analyzer error / missing result
        # -------------------------------------------------

        if not isinstance(
            signal_result,
            dict
        ):

            i += 1
            continue

        # -------------------------------------------------
        # SIGNAL
        # -------------------------------------------------

        signal = str(
            signal_result.get(
                "signal",
                "HOLD"
            )
        ).upper()

        # -------------------------------------------------
        # Signal must be BUY / SELL
        # -------------------------------------------------

        if signal not in [
            "BUY",
            "SELL"
        ]:

            i += 1
            continue

        # -------------------------------------------------
        # TRADE ALLOWED
        #
        # EXACTLY like engine
        # -------------------------------------------------

        trade_allowed = signal_result.get(
            "trade_allowed",
            signal in [
                "BUY",
                "SELL"
            ]
        )

        trade_allowed = bool(
            trade_allowed
        )

        if not trade_allowed:

            trade_allowed_false_count += 1

            i += 1
            continue

        # -------------------------------------------------
        # FILTER
        #
        # Filter được áp dụng SAU Signal
        # và SAU trade_allowed.
        #
        # Không thay đổi Signal v1.6.1.
        # -------------------------------------------------

        score = get_score(
            signal_result
        )

        if should_remove_trade(
            mode,
            signal,
            score
        ):

            if (
                signal == "SELL"
                and score is not None
                and -9 <= score <= -8
            ):

                filter_sell_count += 1

            if (
                signal == "BUY"
                and score is not None
                and 12 <= score <= 14
            ):

                filter_buy_count += 1

            i += 1
            continue

        # =================================================
        # ENTRY
        # =================================================

        entry_index = i + 1

        entry_candle = df.iloc[
            entry_index
        ]

        raw_entry_price = safe_float(
            entry_candle["open"]
        )

        if raw_entry_price <= 0:

            i += 1
            continue

        entry_price = apply_entry_slippage(
            raw_entry_price,
            signal,
            slippage
        )

        # =================================================
        # SL / TP
        #
        # EXACTLY like engine
        # =================================================

        stop_loss = safe_float(
            signal_result.get(
                "stop_loss"
            ),
            0
        )

        take_profit = safe_float(
            signal_result.get(
                "take_profit"
            ),
            0
        )

        # -------------------------------------------------
        # Fallback ATR
        # -------------------------------------------------

        if (
            stop_loss <= 0
            or take_profit <= 0
        ):

            atr = safe_float(
                signal_result.get(
                    "atr"
                ),
                0
            )

            if atr <= 0:

                high_low = (
                    df["high"] -
                    df["low"]
                )

                atr = safe_float(
                    high_low.iloc[
                        max(0, i - 13):i + 1
                    ].mean(),
                    0
                )

            if atr <= 0:

                i += 1
                continue

            if signal == "BUY":

                stop_loss = (
                    entry_price -
                    1.5 * atr
                )

                take_profit = (
                    entry_price +
                    3.0 * atr
                )

            else:

                stop_loss = (
                    entry_price +
                    1.5 * atr
                )

                take_profit = (
                    entry_price -
                    3.0 * atr
                )

        # =================================================
        # SEARCH EXIT
        #
        # EXACTLY like engine
        # =================================================

        exit_index = None
        exit_price = None
        exit_reason = None

        j = entry_index

        while j < len(df):

            candle = df.iloc[j]

            high = safe_float(
                candle["high"]
            )

            low = safe_float(
                candle["low"]
            )

            close = safe_float(
                candle["close"]
            )

            # -------------------------------------------------
            # BUY
            # -------------------------------------------------

            if signal == "BUY":

                hit_sl = (
                    low <= stop_loss
                )

                hit_tp = (
                    high >= take_profit
                )

                # Same candle:
                # SL first
                if hit_sl:

                    exit_price = stop_loss
                    exit_reason = "STOP_LOSS"

                elif hit_tp:

                    exit_price = take_profit
                    exit_reason = "TAKE_PROFIT"

            # -------------------------------------------------
            # SELL
            # -------------------------------------------------

            else:

                hit_sl = (
                    high >= stop_loss
                )

                hit_tp = (
                    low <= take_profit
                )

                # Same candle:
                # SL first
                if hit_sl:

                    exit_price = stop_loss
                    exit_reason = "STOP_LOSS"

                elif hit_tp:

                    exit_price = take_profit
                    exit_reason = "TAKE_PROFIT"

            if exit_reason is not None:

                exit_index = j

                break

            j += 1

        # =================================================
        # END OF DATA
        # =================================================

        if exit_index is None:

            exit_index = len(df) - 1

            exit_price = safe_float(
                df.iloc[-1]["close"]
            )

            exit_reason = "END_OF_DATA"

        # =================================================
        # EXIT SLIPPAGE
        # =================================================

        actual_exit_price = apply_exit_slippage(
            exit_price,
            signal,
            slippage
        )

        # =================================================
        # RETURN
        #
        # EXACTLY like engine
        # =================================================

        trade_return = calculate_trade_return(
            signal,
            entry_price,
            actual_exit_price
        )

        # =================================================
        # POSITION = ENTIRE BALANCE
        #
        # QUAN TRỌNG:
        # Không dùng quantity.
        #
        # Engine dùng:
        # profit_before_fee = balance * return
        # =================================================

        profit_before_fee = (
            balance *
            trade_return
        )

        # =================================================
        # FEES
        #
        # EXACTLY like engine
        # =================================================

        entry_fee = (
            balance *
            fee_rate
        )

        exit_balance_before_fee = (
            balance +
            profit_before_fee
        )

        exit_fee = (
            exit_balance_before_fee *
            fee_rate
        )

        trade_fee = (
            entry_fee +
            exit_fee
        )

        profit_after_fee = (
            profit_before_fee -
            trade_fee
        )

        # -------------------------------------------------
        # Update balance
        # -------------------------------------------------

        balance += profit_after_fee

        total_fees += trade_fee

        # =================================================
        # STATISTICS
        # =================================================

        if profit_after_fee > 0:

            wins += 1

            gross_profit += (
                profit_after_fee
            )

            current_win_streak += 1
            current_loss_streak = 0

            max_win_streak = max(
                max_win_streak,
                current_win_streak
            )

        else:

            losses += 1

            gross_loss += abs(
                profit_after_fee
            )

            current_loss_streak += 1
            current_win_streak = 0

            max_loss_streak = max(
                max_loss_streak,
                current_loss_streak
            )

        if signal == "BUY":

            buy_trades += 1

            if profit_after_fee > 0:

                buy_wins += 1

        elif signal == "SELL":

            sell_trades += 1

            if profit_after_fee > 0:

                sell_wins += 1

        # =================================================
        # DRAWDOWN
        # =================================================

        if balance > max_balance:

            max_balance = balance

        drawdown = (
            max_balance -
            balance
        )

        max_drawdown = max(
            max_drawdown,
            drawdown
        )

        # =================================================
        # EQUITY
        # =================================================

        equity_curve.append(
            {
                "trade": len(trades) + 1,
                "balance": balance
            }
        )

        # =================================================
        # TRADE RECORD
        # =================================================

        trade = {

            "trade_id": len(trades) + 1,

            "signal": signal,

            "score": score,

            "market_condition": (
                get_market_condition(
                    signal_result
                )
            ),

            "entry_index": entry_index,

            "exit_index": exit_index,

            "entry_price": entry_price,

            "exit_price": actual_exit_price,

            "stop_loss": stop_loss,

            "take_profit": take_profit,

            "reason": exit_reason,

            "exit_reason": exit_reason,

            "return_pct": (
                trade_return * 100
            ),

            "profit_before_fee": (
                profit_before_fee
            ),

            "fees": trade_fee,

            "profit": profit_after_fee,

            "balance": balance
        }

        trades.append(
            native(trade)
        )

        # =================================================
        # MOVE AFTER EXIT
        #
        # EXACTLY like engine
        # =================================================

        i = exit_index + 1

    # =====================================================
    # FINAL STATISTICS
    # =====================================================

    total_trades = len(trades)

    win_rate = (
        wins /
        total_trades *
        100
        if total_trades > 0
        else 0.0
    )

    buy_win_rate = (
        buy_wins /
        buy_trades *
        100
        if buy_trades > 0
        else 0.0
    )

    sell_win_rate = (
        sell_wins /
        sell_trades *
        100
        if sell_trades > 0
        else 0.0
    )

    average_win = (
        gross_profit /
        wins
        if wins > 0
        else 0.0
    )

    average_loss = (
        -gross_loss /
        losses
        if losses > 0
        else 0.0
    )

    profit_before_fees = sum(
        safe_float(
            trade["profit_before_fee"]
        )
        for trade in trades
    )

    total_profit = (
        balance -
        initial_balance
    )

    return_pct = (
        total_profit /
        initial_balance *
        100
        if initial_balance != 0
        else 0
    )

    if gross_loss > 0:

        profit_factor = (
            gross_profit /
            gross_loss
        )

    elif gross_profit > 0:

        profit_factor = None

    else:

        profit_factor = 0.0

    max_drawdown_pct = (
        max_drawdown /
        max_balance *
        100
        if max_balance > 0
        else 0
    )

    # =====================================================
    # RESULT
    # =====================================================

    result = {

        "status": "ok",

        "version": VERSION,

        "mode": mode,

        "strategy": STRATEGY,

        "data": {
            "candles": len(df)
        },

        "settings": {

            "initial_balance": initial_balance,

            "fee_rate": fee_rate,

            "slippage": slippage
        },

        "filter_counts": {

            "SELL_-8_-9": filter_sell_count,

            "BUY_12_14": filter_buy_count
        },

        "debug": {

            "trade_allowed_false_count": (
                trade_allowed_false_count
            )
        },

        "summary": {

            "initial_balance": initial_balance,

            "final_balance": balance,

            "profit": total_profit,

            "return_pct": return_pct,

            "total_trades": total_trades,

            "wins": wins,

            "losses": losses,

            "win_rate": win_rate,

            "buy_trades": buy_trades,

            "buy_wins": buy_wins,

            "buy_win_rate": buy_win_rate,

            "sell_trades": sell_trades,

            "sell_wins": sell_wins,

            "sell_win_rate": sell_win_rate,

            "average_win": average_win,

            "average_loss": average_loss,

            "gross_profit": gross_profit,

            "gross_loss": gross_loss,

            "profit_before_fees": (
                profit_before_fees
            ),

            "total_fees": total_fees,

            "profit_factor": profit_factor,

            "max_drawdown": max_drawdown,

            "max_drawdown_pct": max_drawdown_pct,

            "max_win_streak": max_win_streak,

            "max_loss_streak": max_loss_streak
        },

        "equity_curve": native(
            equity_curve
        ),

        "trades": native(
            trades
        )
    }

    return native(result)


# =========================================================
# FILTERED DIAGNOSTIC v1.5
# =========================================================

def run_filtered_diagnostic_v15(
    data,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):

    df = normalize_data(data)

    initial_balance = safe_float(
        initial_balance,
        1000.0
    )

    fee_rate = safe_float(
        fee_rate,
        0.0004
    )

    slippage = safe_float(
        slippage,
        0.0001
    )

    # =====================================================
    # BUILD SIGNAL CACHE ONCE
    # =====================================================

    cache_result = build_signal_cache(df)

    signal_cache = cache_result["cache"]

    modes = [
        "BASELINE",
        "REMOVE_SELL_-8_-9",
        "REMOVE_BUY_12_14",
        "REMOVE_BOTH"
    ]

    results = {}

    # =====================================================
    # RUN 4 MODES
    # =====================================================

    for mode in modes:

        results[mode] = run_filtered_backtest(
            df=df,
            signal_cache=signal_cache,
            mode=mode,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        # -------------------------------------------------
        # Add common debug information
        # -------------------------------------------------

        results[mode]["debug"].update({

            "signal_buy_count": (
                cache_result[
                    "signal_buy_count"
                ]
            ),

            "signal_sell_count": (
                cache_result[
                    "signal_sell_count"
                ]
            ),

            "signal_hold_count": (
                cache_result[
                    "signal_hold_count"
                ]
            ),

            "analyzer_error_count": (
                cache_result[
                    "analyzer_error_count"
                ]
            ),

            "first_analyzer_error": (
                cache_result[
                    "first_analyzer_error"
                ]
            )
        })

    # =====================================================
    # RESULT
    # =====================================================

    return native({

        "status": "ok",

        "version": VERSION,

        "method": (
            "True filtered backtest using "
            "the exact execution mechanics of "
            "backtest_engine.py v1.1.2, "
            "with Signal v1.6.1 cached once "
            "and filters applied only before entry."
        ),

        "optimization": {

            "enabled": True,

            "description": (
                "analyze_market() chỉ chạy một lần "
                "cho mỗi candle từ i=100; "
                "4 filter modes dùng chung Signal cache."
            ),

            "signal_calculations": (
                len(signal_cache)
            ),

            "filter_modes": 4
        },

        "warning": (
            "Signal v1.6.1 được giữ nguyên. "
            "Filter chỉ được áp dụng sau khi "
            "Signal tạo BUY/SELL và trade_allowed=True."
        ),

        "results": results
    })


# =========================================================
# LOCAL TEST
# =========================================================

if __name__ == "__main__":

    print(
        "backtest_filtered_v15.py VERSION:",
        VERSION
    )

    print(
        "STRATEGY:",
        STRATEGY
    )

    print(
        "run_filtered_diagnostic_v15 = OK"
    )
