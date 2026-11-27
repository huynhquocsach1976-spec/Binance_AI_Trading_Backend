import math
import pandas as pd
import numpy as np

from ai_analyzer import analyze_market


VERSION = "1.0.0"
STRATEGY = "Signal v1.6.1"


# ============================================================
# SAFE HELPERS
# ============================================================

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


# ============================================================
# NORMALIZE
# ============================================================

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
            f"Không đủ dữ liệu: {len(df)} candles"
        )

    return df


# ============================================================
# SLIPPAGE
# ============================================================

def apply_entry_slippage(price, signal, slippage):

    price = safe_float(price)
    slippage = safe_float(slippage)

    if signal == "BUY":

        return price * (1.0 + slippage)

    if signal == "SELL":

        return price * (1.0 - slippage)

    return price


def apply_exit_slippage(price, signal, slippage):

    price = safe_float(price)
    slippage = safe_float(slippage)

    if signal == "BUY":

        return price * (1.0 - slippage)

    if signal == "SELL":

        return price * (1.0 + slippage)

    return price


# ============================================================
# RETURN
# ============================================================

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


# ============================================================
# GET INDICATORS
# ============================================================

def get_indicators(signal_result):

    indicators = signal_result.get(
        "indicators",
        {}
    )

    if not isinstance(indicators, dict):

        indicators = {}

    return indicators


# ============================================================
# SCORE GROUP
# ============================================================

def get_score_group(signal, score):

    if score is None:
        return "UNKNOWN"

    score = safe_int(score)

    if signal == "BUY":

        if score >= 15:
            return "BUY_15_PLUS"

        if score >= 12:
            return "BUY_12_14"

        if score >= 10:
            return "BUY_10_11"

        if score >= 8:
            return "BUY_8_9"

    if signal == "SELL":

        if score <= -15:
            return "SELL_-15_MINUS"

        if score <= -12:
            return "SELL_-12_-14"

        if score <= -10:
            return "SELL_-10_-11"

        if score <= -8:
            return "SELL_-8_-9"

    return "OTHER"


# ============================================================
# SELL FILTER DEFINITIONS
# ============================================================

def build_sell_filters():

    return {

        # ----------------------------------------------------
        # BASELINE
        # ----------------------------------------------------

        "BASELINE": lambda x: True,

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        "RSI_GE_25": lambda x:
            x["rsi"] >= 25,

        "RSI_GE_30": lambda x:
            x["rsi"] >= 30,

        "RSI_GE_35": lambda x:
            x["rsi"] >= 35,

        "RSI_GE_40": lambda x:
            x["rsi"] >= 40,

        # ----------------------------------------------------
        # EMA
        # ----------------------------------------------------

        "EMA20_LT_EMA50": lambda x:
            x["ema20"] < x["ema50"],

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        "PRICE_LT_EMA20": lambda x:
            x["price"] < x["ema20"],

        "PRICE_LT_VWAP": lambda x:
            x["price"] < x["vwap"],

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        "MACD_BEARISH": lambda x:
            x["macd"] < x["macd_signal"],

        "MACD_HIST_LT_0": lambda x:
            x["macd_hist"] < 0,

        # ----------------------------------------------------
        # VOLUME
        # ----------------------------------------------------

        "VOLUME_GE_1": lambda x:
            x["volume_ratio"] >= 1.0,

        "TRADES_GE_1": lambda x:
            x["trades_ratio"] >= 1.0,

        # ----------------------------------------------------
        # COMBINATIONS
        # ----------------------------------------------------

        "RSI30_EMA_BEARISH": lambda x:
            (
                x["rsi"] >= 30
                and
                x["ema20"] < x["ema50"]
            ),

        "RSI35_EMA_BEARISH": lambda x:
            (
                x["rsi"] >= 35
                and
                x["ema20"] < x["ema50"]
            ),

        "RSI30_PRICE_EMA20": lambda x:
            (
                x["rsi"] >= 30
                and
                x["price"] < x["ema20"]
            ),

        "RSI35_PRICE_EMA20": lambda x:
            (
                x["rsi"] >= 35
                and
                x["price"] < x["ema20"]
            ),

        "RSI30_EMA_PRICE": lambda x:
            (
                x["rsi"] >= 30
                and
                x["ema20"] < x["ema50"]
                and
                x["price"] < x["ema20"]
            ),

        "RSI35_EMA_PRICE": lambda x:
            (
                x["rsi"] >= 35
                and
                x["ema20"] < x["ema50"]
                and
                x["price"] < x["ema20"]
            ),

        "RSI30_FULL": lambda x:
            (
                x["rsi"] >= 30
                and
                x["ema20"] < x["ema50"]
                and
                x["price"] < x["ema20"]
                and
                x["price"] < x["vwap"]
                and
                x["macd"] < x["macd_signal"]
                and
                x["macd_hist"] < 0
            ),

        "RSI35_FULL": lambda x:
            (
                x["rsi"] >= 35
                and
                x["ema20"] < x["ema50"]
                and
                x["price"] < x["ema20"]
                and
                x["price"] < x["vwap"]
                and
                x["macd"] < x["macd_signal"]
                and
                x["macd_hist"] < 0
            )
    }


# ============================================================
# EXTRACT SELL FEATURES
# ============================================================

def extract_features(
    signal_result,
    entry_price
):

    indicators = get_indicators(
        signal_result
    )

    return {

        "price": safe_float(
            entry_price
        ),

        "rsi": safe_float(
            indicators.get("rsi")
        ),

        "ema20": safe_float(
            indicators.get("ema20")
        ),

        "ema50": safe_float(
            indicators.get("ema50")
        ),

        "macd": safe_float(
            indicators.get("macd")
        ),

        "macd_signal": safe_float(
            indicators.get("macd_signal")
        ),

        "macd_hist": safe_float(
            indicators.get(
                "macd_histogram",
                indicators.get(
                    "macd_hist",
                    0
                )
            )
        ),

        "vwap": safe_float(
            indicators.get("vwap")
        ),

        "volume_ratio": safe_float(
            indicators.get(
                "volume_ratio"
            )
        ),

        "trades_ratio": safe_float(
            indicators.get(
                "trades_ratio"
            )
        ),

        "atr": safe_float(
            indicators.get("atr")
        )
    }


# ============================================================
# EXECUTE ONE TRADE
# ============================================================

def execute_trade(
    df,
    signal_result,
    i,
    balance,
    fee_rate,
    slippage
):

    signal = str(
        signal_result.get(
            "signal",
            "HOLD"
        )
    ).upper()

    if signal not in [
        "BUY",
        "SELL"
    ]:

        return None

    entry_index = i + 1

    if entry_index >= len(df):

        return None

    raw_entry_price = safe_float(
        df.iloc[entry_index]["open"]
    )

    if raw_entry_price <= 0:

        return None

    entry_price = apply_entry_slippage(
        raw_entry_price,
        signal,
        slippage
    )

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

    # --------------------------------------------------------
    # ATR fallback
    # --------------------------------------------------------

    if (
        stop_loss <= 0
        or
        take_profit <= 0
    ):

        indicators = get_indicators(
            signal_result
        )

        atr = safe_float(
            indicators.get("atr"),
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

            return None

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

    # --------------------------------------------------------
    # EXIT
    # --------------------------------------------------------

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

        if signal == "BUY":

            hit_sl = (
                low <= stop_loss
            )

            hit_tp = (
                high >= take_profit
            )

            # Giữ nguyên engine:
            # SL trước nếu cùng candle

            if hit_sl:

                exit_price = stop_loss
                exit_reason = "STOP_LOSS"

            elif hit_tp:

                exit_price = take_profit
                exit_reason = "TAKE_PROFIT"

        else:

            hit_sl = (
                high >= stop_loss
            )

            hit_tp = (
                low <= take_profit
            )

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

    # --------------------------------------------------------
    # END DATA
    # --------------------------------------------------------

    if exit_index is None:

        exit_index = len(df) - 1

        exit_price = safe_float(
            df.iloc[-1]["close"]
        )

        exit_reason = "END_OF_DATA"

    # --------------------------------------------------------
    # EXIT SLIPPAGE
    # --------------------------------------------------------

    actual_exit_price = apply_exit_slippage(
        exit_price,
        signal,
        slippage
    )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    trade_return = calculate_trade_return(
        signal,
        entry_price,
        actual_exit_price
    )

    # --------------------------------------------------------
    # PROFIT
    # --------------------------------------------------------

    profit_before_fee = (
        balance *
        trade_return
    )

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

    new_balance = (
        balance +
        profit_after_fee
    )

    return {

        "signal": signal,

        "entry_index": entry_index,

        "exit_index": exit_index,

        "entry_price": entry_price,

        "exit_price": actual_exit_price,

        "stop_loss": stop_loss,

        "take_profit": take_profit,

        "exit_reason": exit_reason,

        "return_pct": (
            trade_return * 100
        ),

        "profit_before_fee": (
            profit_before_fee
        ),

        "fees": trade_fee,

        "profit": profit_after_fee,

        "balance": new_balance
    }


# ============================================================
# RUN ONE FILTER
# ============================================================

def run_filter(
    df,
    filter_name,
    sell_filter,
    initial_balance,
    fee_rate,
    slippage
):

    balance = initial_balance

    trades = []

    wins = 0
    losses = 0

    buy_trades = 0
    buy_wins = 0

    sell_trades = 0
    sell_wins = 0

    gross_profit = 0.0
    gross_loss = 0.0

    profit_before_fees = 0.0
    total_fees = 0.0

    max_balance = balance
    max_drawdown = 0.0

    signal_buy_count = 0
    signal_sell_count = 0
    signal_hold_count = 0

    sell_blocked = 0

    i = 100

    while i < len(df) - 1:

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

            except Exception:

                i += 1
                continue

        except Exception:

            i += 1
            continue

        if not isinstance(
            signal_result,
            dict
        ):

            i += 1
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

        # ----------------------------------------------------
        # Không phải BUY/SELL
        # ----------------------------------------------------

        if signal not in [
            "BUY",
            "SELL"
        ]:

            i += 1
            continue

        trade_allowed = bool(
            signal_result.get(
                "trade_allowed",
                True
            )
        )

        if not trade_allowed:

            i += 1
            continue

        # ----------------------------------------------------
        # SELL FILTER
        # ----------------------------------------------------

        if signal == "SELL":

            entry_index = i + 1

            if entry_index >= len(df):

                break

            raw_entry = safe_float(
                df.iloc[
                    entry_index
                ]["open"]
            )

            entry_price = apply_entry_slippage(
                raw_entry,
                signal,
                slippage
            )

            features = extract_features(
                signal_result,
                entry_price
            )

            try:

                allow_sell = bool(
                    sell_filter(
                        features
                    )
                )

            except Exception:

                allow_sell = False

            if not allow_sell:

                sell_blocked += 1

                # Không mở trade.
                # Tiếp tục tìm tín hiệu ở candle sau.

                i += 1

                continue

        # ----------------------------------------------------
        # EXECUTE
        # ----------------------------------------------------

        trade = execute_trade(
            df=df,
            signal_result=signal_result,
            i=i,
            balance=balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        if trade is None:

            i += 1
            continue

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        balance = trade["balance"]

        profit = safe_float(
            trade["profit"]
        )

        profit_before = safe_float(
            trade["profit_before_fee"]
        )

        fees = safe_float(
            trade["fees"]
        )

        profit_before_fees += (
            profit_before
        )

        total_fees += fees

        if profit > 0:

            wins += 1

            gross_profit += profit

        else:

            losses += 1

            gross_loss += abs(
                profit
            )

        if signal == "BUY":

            buy_trades += 1

            if profit > 0:

                buy_wins += 1

        elif signal == "SELL":

            sell_trades += 1

            if profit > 0:

                sell_wins += 1

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

        # ----------------------------------------------------
        # SAVE TRADE
        # ----------------------------------------------------

        trade_record = dict(
            trade
        )

        trade_record["trade_id"] = (
            len(trades) + 1
        )

        trade_record["score"] = safe_int(
            signal_result.get(
                "score",
                0
            )
        )

        trade_record["score_group"] = (
            get_score_group(
                signal,
                signal_result.get(
                    "score"
                )
            )
        )

        indicators = get_indicators(
            signal_result
        )

        trade_record["rsi"] = safe_float(
            indicators.get("rsi")
        )

        trade_record["ema20"] = safe_float(
            indicators.get("ema20")
        )

        trade_record["ema50"] = safe_float(
            indicators.get("ema50")
        )

        trade_record["vwap"] = safe_float(
            indicators.get("vwap")
        )

        trades.append(
            native(trade_record)
        )

        # ----------------------------------------------------
        # MOVE AFTER EXIT
        # ----------------------------------------------------

        i = (
            trade["exit_index"] +
            1
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    total_trades = len(trades)

    total_profit = (
        balance -
        initial_balance
    )

    return_pct = (
        total_profit /
        initial_balance *
        100
        if initial_balance != 0
        else 0.0
    )

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
        else 0.0
    )

    return {

        "filter": filter_name,

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

            "gross_profit": gross_profit,

            "gross_loss": gross_loss,

            "profit_before_fees": (
                profit_before_fees
            ),

            "total_fees": total_fees,

            "profit_factor": profit_factor,

            "max_drawdown": max_drawdown,

            "max_drawdown_pct": (
                max_drawdown_pct
            ),

            "sell_blocked": sell_blocked,

            "signal_buy_count": (
                signal_buy_count
            ),

            "signal_sell_count": (
                signal_sell_count
            ),

            "signal_hold_count": (
                signal_hold_count
            )
        },

        "trades": trades
    }


# ============================================================
# RUN ALL FILTERS
# ============================================================

def run_sell_filter_diagnostic(
    data,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):

    df = normalize_data(data)

    filters = build_sell_filters()

    results = []

    for filter_name, sell_filter in filters.items():

        print(
            f"Running filter: {filter_name}"
        )

        result = run_filter(
            df=df,
            filter_name=filter_name,
            sell_filter=sell_filter,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

        results.append(
            result
        )

    # ========================================================
    # COMPARISON TABLE
    # ========================================================

    comparison = []

    baseline_profit = None

    for result in results:

        summary = result["summary"]

        if (
            result["filter"] ==
            "BASELINE"
        ):

            baseline_profit = safe_float(
                summary["profit"]
            )

    for result in results:

        summary = result["summary"]

        profit = safe_float(
            summary["profit"]
        )

        improvement = (
            profit -
            baseline_profit
            if baseline_profit is not None
            else 0.0
        )

        comparison.append({

            "filter": result["filter"],

            "final_balance": safe_float(
                summary["final_balance"]
            ),

            "profit": profit,

            "return_pct": safe_float(
                summary["return_pct"]
            ),

            "improvement_vs_baseline": (
                improvement
            ),

            "total_trades": safe_int(
                summary["total_trades"]
            ),

            "wins": safe_int(
                summary["wins"]
            ),

            "losses": safe_int(
                summary["losses"]
            ),

            "win_rate": safe_float(
                summary["win_rate"]
            ),

            "buy_trades": safe_int(
                summary["buy_trades"]
            ),

            "buy_win_rate": safe_float(
                summary["buy_win_rate"]
            ),

            "sell_trades": safe_int(
                summary["sell_trades"]
            ),

            "sell_win_rate": safe_float(
                summary["sell_win_rate"]
            ),

            "profit_before_fees": safe_float(
                summary["profit_before_fees"]
            ),

            "total_fees": safe_float(
                summary["total_fees"]
            ),

            "profit_factor": (
                summary["profit_factor"]
            ),

            "max_drawdown": safe_float(
                summary["max_drawdown"]
            ),

            "max_drawdown_pct": safe_float(
                summary["max_drawdown_pct"]
            ),

            "sell_blocked": safe_int(
                summary["sell_blocked"]
            )
        })

    # ========================================================
    # SORT
    # ========================================================

    ranked = sorted(
        comparison,
        key=lambda x: (
            x["profit"],
            x["profit_factor"] or 0,
            -x["max_drawdown_pct"]
        ),
        reverse=True
    )

    # ========================================================
    # RESULT
    # ========================================================

    return native({

        "status": "ok",

        "version": VERSION,

        "strategy": STRATEGY,

        "data": {

            "candles": len(df)
        },

        "settings": {

            "initial_balance": initial_balance,

            "fee_rate": fee_rate,

            "slippage": slippage
        },

        "comparison": comparison,

        "ranking": ranked,

        "details": results
    })


# ============================================================
# CSV LOADER
# ============================================================

def load_csv(path):

    df = pd.read_csv(path)

    return normalize_data(df)


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)

    print(
        "SELL FILTER DIAGNOSTIC"
    )

    print(
        "VERSION:",
        VERSION
    )

    print(
        "STRATEGY:",
        STRATEGY
    )

    print("=" * 70)

    print()

    print(
        "File này cung cấp hàm:"
    )

    print(
        "run_sell_filter_diagnostic(data)"
    )

    print()

    print(
        "Ví dụ:"
    )

    print(
        "df = pd.read_csv('BTCUSDT_1h.csv')"
    )

    print(
        "result = run_sell_filter_diagnostic(df)"
    )

    print()

    print(
        "Không tự chạy CSV vì chưa biết tên file dữ liệu."
    )
