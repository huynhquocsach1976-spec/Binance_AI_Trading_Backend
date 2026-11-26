from ai_analyzer import analyze_market


VERSION = "1.5.0"


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def get_score(signal_result):
    value = signal_result.get("score")

    if value is None:
        return None

    try:
        return float(value)
    except Exception:
        return None


def get_signal(signal_result):
    return str(
        signal_result.get("signal", "")
    ).upper()


def get_trade_allowed(signal_result):
    return bool(
        signal_result.get(
            "trade_allowed",
            True
        )
    )


# ============================================================
# FILTER LOGIC
# ============================================================

def should_remove_trade(
    signal_result,
    mode
):
    signal = get_signal(signal_result)
    score = get_score(signal_result)

    if score is None:
        return False

    # --------------------------------------------------------
    # Remove SELL score -8 / -9
    # --------------------------------------------------------

    if mode in [
        "REMOVE_SELL_-8_-9",
        "REMOVE_BOTH"
    ]:

        if (
            signal == "SELL"
            and -9 <= score <= -8
        ):
            return True

    # --------------------------------------------------------
    # Remove BUY score 12 / 13 / 14
    # --------------------------------------------------------

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


# ============================================================
# ATR
# ============================================================

def get_atr(signal_result):
    indicators = signal_result.get(
        "indicators",
        {}
    )

    atr = indicators.get("atr")

    if atr is None:
        atr = indicators.get("ATR")

    return safe_float(
        atr,
        0.0
    )


# ============================================================
# SL / TP
# ============================================================

def calculate_sl_tp(
    signal_result,
    entry_price
):
    signal = get_signal(signal_result)

    stop_loss = signal_result.get(
        "stop_loss"
    )

    take_profit = signal_result.get(
        "take_profit"
    )

    if (
        stop_loss is not None
        and take_profit is not None
    ):

        return (
            safe_float(stop_loss),
            safe_float(take_profit)
        )

    atr = get_atr(
        signal_result
    )

    if atr <= 0:

        return (
            None,
            None
        )

    if signal == "BUY":

        return (
            entry_price - 1.5 * atr,
            entry_price + 3.0 * atr
        )

    if signal == "SELL":

        return (
            entry_price + 1.5 * atr,
            entry_price - 3.0 * atr
        )

    return (
        None,
        None
    )


# ============================================================
# EXIT CHECK
# ============================================================

def check_exit(
    position,
    candle
):
    side = position["side"]

    high = safe_float(
        candle["high"]
    )

    low = safe_float(
        candle["low"]
    )

    stop_loss = position[
        "stop_loss"
    ]

    take_profit = position[
        "take_profit"
    ]

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if side == "BUY":

        stop_hit = (
            stop_loss is not None
            and low <= stop_loss
        )

        tp_hit = (
            take_profit is not None
            and high >= take_profit
        )

        # Same candle SL + TP:
        # SL first
        if stop_hit:
            return (
                True,
                stop_loss,
                "STOP_LOSS"
            )

        if tp_hit:
            return (
                True,
                take_profit,
                "TAKE_PROFIT"
            )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    elif side == "SELL":

        stop_hit = (
            stop_loss is not None
            and high >= stop_loss
        )

        tp_hit = (
            take_profit is not None
            and low <= take_profit
        )

        # Same candle SL + TP:
        # SL first
        if stop_hit:
            return (
                True,
                stop_loss,
                "STOP_LOSS"
            )

        if tp_hit:
            return (
                True,
                take_profit,
                "TAKE_PROFIT"
            )

    return (
        False,
        None,
        None
    )


# ============================================================
# EXECUTION PRICE
# ============================================================

def apply_entry_slippage(
    price,
    side,
    slippage
):

    if side == "BUY":
        return price * (
            1.0 + slippage
        )

    return price * (
        1.0 - slippage
    )


def apply_exit_slippage(
    price,
    side,
    slippage
):

    if side == "BUY":
        return price * (
            1.0 - slippage
        )

    return price * (
        1.0 + slippage
    )


# ============================================================
# SINGLE FILTERED BACKTEST
# ============================================================

def run_filtered_backtest(
    candles,
    mode="BASELINE",
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):

    if not candles:
        return {
            "status": "error",
            "message": "Không có candles"
        }

    balance = float(
        initial_balance
    )

    peak_balance = balance

    max_drawdown = 0.0

    trades = []

    position = None

    signal_counts = {
        "BUY": 0,
        "SELL": 0,
        "HOLD": 0
    }

    filtered_counts = {
        "SELL_-8_-9": 0,
        "BUY_12_14": 0
    }

    analyzer_errors = 0

    first_analyzer_error = None

    # ========================================================
    # MAIN LOOP
    # ========================================================

    for i in range(
        50,
        len(candles)
    ):

        candle = candles[i]

        # ----------------------------------------------------
        # 1. Manage existing position
        # ----------------------------------------------------

        if position is not None:

            exit_now, exit_price, exit_reason = (
                check_exit(
                    position,
                    candle
                )
            )

            if exit_now:

                side = position["side"]

                raw_exit_price = exit_price

                actual_exit_price = (
                    apply_exit_slippage(
                        raw_exit_price,
                        side,
                        slippage
                    )
                )

                entry_price = position[
                    "entry_price"
                ]

                quantity = position[
                    "quantity"
                ]

                if side == "BUY":

                    gross_profit = (
                        actual_exit_price
                        - entry_price
                    ) * quantity

                else:

                    gross_profit = (
                        entry_price
                        - actual_exit_price
                    ) * quantity

                entry_fee = position[
                    "entry_fee"
                ]

                exit_fee = (
                    actual_exit_price
                    * quantity
                    * fee_rate
                )

                total_fee = (
                    entry_fee
                    + exit_fee
                )

                net_profit = (
                    gross_profit
                    - total_fee
                )

                balance += net_profit

                if balance > peak_balance:
                    peak_balance = balance

                if peak_balance > 0:

                    drawdown = (
                        peak_balance
                        - balance
                    ) / peak_balance * 100.0

                    if drawdown > max_drawdown:
                        max_drawdown = drawdown

                entry_balance = position[
                    "entry_balance"
                ]

                if entry_balance > 0:

                    return_pct = (
                        net_profit
                        / entry_balance
                        * 100.0
                    )

                else:

                    return_pct = 0.0

                trades.append({
                    "signal": position[
                        "signal"
                    ],

                    "score": position[
                        "score"
                    ],

                    "market_condition": position.get(
                        "market_condition"
                    ),

                    "entry_index": position[
                        "entry_index"
                    ],

                    "exit_index": i,

                    "entry_price": round(
                        entry_price,
                        8
                    ),

                    "exit_price": round(
                        actual_exit_price,
                        8
                    ),

                    "stop_loss": position[
                        "stop_loss"
                    ],

                    "take_profit": position[
                        "take_profit"
                    ],

                    "reason": position.get(
                        "reason",
                        "SIGNAL"
                    ),

                    "exit_reason": exit_reason,

                    "return_pct": round(
                        return_pct,
                        8
                    ),

                    "profit_before_fee": round(
                        gross_profit,
                        8
                    ),

                    "fees": round(
                        total_fee,
                        8
                    ),

                    "profit": round(
                        net_profit,
                        8
                    ),

                    "balance": round(
                        balance,
                        8
                    )
                })

                position = None

                # Không mở lệnh mới cùng candle
                continue

        # ----------------------------------------------------
        # 2. Analyze current candle
        # ----------------------------------------------------

        try:

            analysis = analyze_market(
                candles[:i + 1]
            )

        except Exception as e:

            analyzer_errors += 1

            if first_analyzer_error is None:
                first_analyzer_error = str(e)

            continue

        if not isinstance(
            analysis,
            dict
        ):
            analyzer_errors += 1

            if first_analyzer_error is None:
                first_analyzer_error = (
                    "analyze_market không trả về dict"
                )

            continue

        signal = get_signal(
            analysis
        )

        if signal not in [
            "BUY",
            "SELL"
        ]:

            signal_counts["HOLD"] += 1

            continue

        signal_counts[signal] += 1

        score = get_score(
            analysis
        )

        # ----------------------------------------------------
        # 3. Filter
        # ----------------------------------------------------

        if should_remove_trade(
            analysis,
            mode
        ):

            if (
                signal == "SELL"
                and score is not None
                and -9 <= score <= -8
            ):

                filtered_counts[
                    "SELL_-8_-9"
                ] += 1

            if (
                signal == "BUY"
                and score is not None
                and 12 <= score <= 14
            ):

                filtered_counts[
                    "BUY_12_14"
                ] += 1

            continue

        # ----------------------------------------------------
        # 4. Trade allowed
        # ----------------------------------------------------

        if not get_trade_allowed(
            analysis
        ):
            continue

        # ----------------------------------------------------
        # 5. Need next candle for entry
        # ----------------------------------------------------

        if i + 1 >= len(candles):
            continue

        next_candle = candles[
            i + 1
        ]

        raw_entry_price = safe_float(
            next_candle["open"]
        )

        if raw_entry_price <= 0:
            continue

        # ----------------------------------------------------
        # 6. Entry price + slippage
        # ----------------------------------------------------

        entry_price = (
            apply_entry_slippage(
                raw_entry_price,
                signal,
                slippage
            )
        )

        # ----------------------------------------------------
        # 7. SL / TP
        # ----------------------------------------------------

        stop_loss, take_profit = (
            calculate_sl_tp(
                analysis,
                entry_price
            )
        )

        if (
            stop_loss is None
            or take_profit is None
        ):
            continue

        # ----------------------------------------------------
        # 8. Position sizing
        # Full balance compounding
        # ----------------------------------------------------

        quantity = (
            balance
            / entry_price
        )

        entry_fee = (
            balance
            * fee_rate
        )

        balance -= entry_fee

        if balance < 0:
            balance = 0.0

        # ----------------------------------------------------
        # 9. Position
        # ----------------------------------------------------

        position = {
            "side": signal,

            "signal": signal,

            "score": score,

            "market_condition": analysis.get(
                "market_condition"
            ),

            "entry_index": i + 1,

            "entry_price": entry_price,

            "stop_loss": stop_loss,

            "take_profit": take_profit,

            "quantity": quantity,

            "entry_fee": entry_fee,

            "entry_balance": balance,

            "reason": "SIGNAL"
        }

    # ========================================================
    # END OF DATA
    # ========================================================

    if position is not None:

        last_candle = candles[-1]

        raw_exit_price = safe_float(
            last_candle["close"]
        )

        side = position["side"]

        actual_exit_price = (
            apply_exit_slippage(
                raw_exit_price,
                side,
                slippage
            )
        )

        entry_price = position[
            "entry_price"
        ]

        quantity = position[
            "quantity"
        ]

        if side == "BUY":

            gross_profit = (
                actual_exit_price
                - entry_price
            ) * quantity

        else:

            gross_profit = (
                entry_price
                - actual_exit_price
            ) * quantity

        entry_fee = position[
            "entry_fee"
        ]

        exit_fee = (
            actual_exit_price
            * quantity
            * fee_rate
        )

        total_fee = (
            entry_fee
            + exit_fee
        )

        net_profit = (
            gross_profit
            - total_fee
        )

        balance += net_profit

        if balance > peak_balance:
            peak_balance = balance

        if peak_balance > 0:

            drawdown = (
                peak_balance
                - balance
            ) / peak_balance * 100.0

            if drawdown > max_drawdown:
                max_drawdown = drawdown

        entry_balance = position[
            "entry_balance"
        ]

        if entry_balance > 0:

            return_pct = (
                net_profit
                / entry_balance
                * 100.0
            )

        else:

            return_pct = 0.0

        trades.append({
            "signal": position[
                "signal"
            ],

            "score": position[
                "score"
            ],

            "market_condition": position.get(
                "market_condition"
            ),

            "entry_index": position[
                "entry_index"
            ],

            "exit_index": len(candles) - 1,

            "entry_price": round(
                entry_price,
                8
            ),

            "exit_price": round(
                actual_exit_price,
                8
            ),

            "stop_loss": position[
                "stop_loss"
            ],

            "take_profit": position[
                "take_profit"
            ],

            "reason": position.get(
                "reason",
                "SIGNAL"
            ),

            "exit_reason": "END_OF_DATA",

            "return_pct": round(
                return_pct,
                8
            ),

            "profit_before_fee": round(
                gross_profit,
                8
            ),

            "fees": round(
                total_fee,
                8
            ),

            "profit": round(
                net_profit,
                8
            ),

            "balance": round(
                balance,
                8
            )
        })

        position = None

    # ========================================================
    # STATISTICS
    # ========================================================

    total_trades = len(trades)

    wins = [
        t for t in trades
        if safe_float(t.get("profit")) > 0
    ]

    losses = [
        t for t in trades
        if safe_float(t.get("profit")) < 0
    ]

    gross_profit = sum(
        safe_float(t.get("profit"))
        for t in wins
    )

    gross_loss = abs(
        sum(
            safe_float(t.get("profit"))
            for t in losses
        )
    )

    if gross_loss > 0:
        profit_factor = (
            gross_profit
            / gross_loss
        )
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    if total_trades > 0:

        win_rate = (
            len(wins)
            / total_trades
            * 100.0
        )

    else:

        win_rate = 0.0

    profit = (
        balance
        - initial_balance
    )

    if initial_balance > 0:

        return_pct = (
            profit
            / initial_balance
            * 100.0
        )

    else:

        return_pct = 0.0

    buy_trades = [
        t for t in trades
        if t.get("signal") == "BUY"
    ]

    sell_trades = [
        t for t in trades
        if t.get("signal") == "SELL"
    ]

    buy_wins = [
        t for t in buy_trades
        if safe_float(t.get("profit")) > 0
    ]

    sell_wins = [
        t for t in sell_trades
        if safe_float(t.get("profit")) > 0
    ]

    total_fees = sum(
        safe_float(t.get("fees"))
        for t in trades
    )

    stop_loss_count = sum(
        1
        for t in trades
        if t.get("exit_reason")
        == "STOP_LOSS"
    )

    take_profit_count = sum(
        1
        for t in trades
        if t.get("exit_reason")
        == "TAKE_PROFIT"
    )

    eod_count = sum(
        1
        for t in trades
        if t.get("exit_reason")
        == "END_OF_DATA"
    )

    # ========================================================
    # MAX LOSS STREAK
    # ========================================================

    current_loss_streak = 0
    max_loss_streak = 0

    for trade in trades:

        p = safe_float(
            trade.get("profit")
        )

        if p < 0:

            current_loss_streak += 1

            if (
                current_loss_streak
                > max_loss_streak
            ):
                max_loss_streak = (
                    current_loss_streak
                )

        else:

            current_loss_streak = 0

    # ========================================================
    # RESULT
    # ========================================================

    return {
        "status": "ok",

        "version": VERSION,

        "mode": mode,

        "initial_balance": round(
            initial_balance,
            8
        ),

        "final_balance": round(
            balance,
            8
        ),

        "profit": round(
            profit,
            8
        ),

        "return_pct": round(
            return_pct,
            8
        ),

        "trades": total_trades,

        "wins": len(wins),

        "losses": len(losses),

        "win_rate": round(
            win_rate,
            8
        ),

        "profit_factor": (
            round(
                profit_factor,
                8
            )
            if profit_factor != float("inf")
            else "inf"
        ),

        "max_drawdown_pct": round(
            max_drawdown,
            8
        ),

        "gross_profit": round(
            gross_profit,
            8
        ),

        "gross_loss": round(
            gross_loss,
            8
        ),

        "fees": round(
            total_fees,
            8
        ),

        "BUY": {
            "trades": len(
                buy_trades
            ),

            "wins": len(
                buy_wins
            ),

            "profit": round(
                sum(
                    safe_float(
                        t.get("profit")
                    )
                    for t in buy_trades
                ),
                8
            )
        },

        "SELL": {
            "trades": len(
                sell_trades
            ),

            "wins": len(
                sell_wins
            ),

            "profit": round(
                sum(
                    safe_float(
                        t.get("profit")
                    )
                    for t in sell_trades
                ),
                8
            )
        },

        "exit_analysis": {
            "STOP_LOSS": stop_loss_count,
            "TAKE_PROFIT": take_profit_count,
            "END_OF_DATA": eod_count
        },

        "max_loss_streak": max_loss_streak,

        "filter_counts": filtered_counts,

        "debug": {
            "signal_buy_count": signal_counts[
                "BUY"
            ],

            "signal_sell_count": signal_counts[
                "SELL"
            ],

            "signal_hold_count": signal_counts[
                "HOLD"
            ],

            "analyzer_error_count": analyzer_errors,

            "first_analyzer_error": (
                first_analyzer_error
            )
        },

        "trades_detail": trades
    }


# ============================================================
# RUN ALL V1.5 TESTS
# ============================================================

def run_filtered_diagnostic_v15(
    candles,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):

    modes = [
        "BASELINE",
        "REMOVE_SELL_-8_-9",
        "REMOVE_BUY_12_14",
        "REMOVE_BOTH"
    ]

    results = {}

    for mode in modes:

        results[mode] = run_filtered_backtest(
            candles=candles,
            mode=mode,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage
        )

    return {
        "status": "ok",

        "version": VERSION,

        "method": (
            "True filtered backtest with "
            "next-candle entry, "
            "SL/TP, fees, slippage "
            "and full-balance compounding"
        ),

        "warning": (
            "Signal v1.6.1 được giữ nguyên. "
            "Filter chỉ được áp dụng sau khi "
            "Signal tạo BUY/SELL."
        ),

        "results": results
    }
