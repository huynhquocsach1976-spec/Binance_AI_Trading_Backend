import pandas as pd
from ai_analyzer import analyze_market


VERSION = "1.1.0"


def run_backtest(
    candles,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):
    """
    Backtest Signal v1.6.1 - Version 1.1

    Quy tắc:

    1. Phân tích tại nến T
    2. Nếu có BUY/SELL:
       vào lệnh tại OPEN nến T+1
    3. Chỉ giao dịch khi trade_allowed = True
    4. Có Stop Loss / Take Profit
    5. Nếu cùng một nến chạm SL và TP:
       ưu tiên SL
    6. Chỉ giữ một lệnh tại một thời điểm
    """

    # =====================================================
    # KIỂM TRA DỮ LIỆU
    # =====================================================

    if not candles:

        return {
            "status": "error",
            "message": "Không có dữ liệu nến"
        }

    if len(candles) < 60:

        return {
            "status": "error",
            "message": (
                f"Cần ít nhất 60 nến, "
                f"hiện tại có {len(candles)} nến"
            )
        }

    df = pd.DataFrame(candles)

    required_columns = [
        "time",
        "open",
        "high",
        "low",
        "close"
    ]

    for column in required_columns:

        if column not in df.columns:

            return {
                "status": "error",
                "message": f"Thiếu trường dữ liệu: {column}"
            }

    # =====================================================
    # CHUYỂN KIỂU DỮ LIỆU
    # =====================================================

    for column in [
        "open",
        "high",
        "low",
        "close"
    ]:

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

    # =====================================================
    # VỐN
    # =====================================================

    balance = float(initial_balance)

    peak_equity = float(initial_balance)

    max_drawdown = 0.0

    # =====================================================
    # THỐNG KÊ
    # =====================================================

    trades = []

    wins = 0
    losses = 0

    buy_trades = 0
    buy_wins = 0
    buy_losses = 0

    sell_trades = 0
    sell_wins = 0
    sell_losses = 0

    gross_profit = 0.0
    gross_loss = 0.0

    total_fees = 0.0

    total_profit_before_fees = 0.0

    total_profit_after_fees = 0.0

    # =====================================================
    # CHUỖI THẮNG / THUA
    # =====================================================

    current_win_streak = 0
    current_loss_streak = 0

    max_win_streak = 0
    max_loss_streak = 0

    # =====================================================
    # EQUITY CURVE
    # =====================================================

    equity_curve = []

    # =====================================================
    # BẮT ĐẦU TỪ NẾN THỨ 50
    # =====================================================

    i = 50

    while i < len(df) - 1:

        # -------------------------------------------------
        # Chỉ sử dụng dữ liệu từ đầu đến nến hiện tại
        # -------------------------------------------------

        history = df.iloc[:i + 1].copy()

        history_candles = history.to_dict(
            orient="records"
        )

        try:

            signal_result = analyze_market(
                history_candles
            )

        except Exception:

            i += 1
            continue

        signal = signal_result.get(
            "signal"
        )

        trade_allowed = signal_result.get(
            "trade_allowed",
            False
        )

        # -------------------------------------------------
        # Không có tín hiệu
        # -------------------------------------------------

        if signal not in ["BUY", "SELL"]:

            i += 1
            continue

        # -------------------------------------------------
        # Không được phép giao dịch
        # -------------------------------------------------

        if not trade_allowed:

            i += 1
            continue

        stop_loss = signal_result.get(
            "stop_loss"
        )

        take_profit = signal_result.get(
            "take_profit"
        )

        if (
            stop_loss is None
            or take_profit is None
        ):

            i += 1
            continue

        stop_loss = float(stop_loss)

        take_profit = float(take_profit)

        # =================================================
        # ENTRY = OPEN NẾN KẾ TIẾP
        # =================================================

        entry_index = i + 1

        entry_candle = df.iloc[
            entry_index
        ]

        raw_entry = float(
            entry_candle["open"]
        )

        # -------------------------------------------------
        # Slippage
        # -------------------------------------------------

        if signal == "BUY":

            entry_price = (
                raw_entry
                * (1 + slippage)
            )

        else:

            entry_price = (
                raw_entry
                * (1 - slippage)
            )

        entry_time = int(
            entry_candle["time"]
        )

        # =================================================
        # TÌM EXIT
        # =================================================

        exit_price = None

        exit_time = None

        exit_reason = None

        exit_index = None

        j = entry_index

        while j < len(df):

            candle = df.iloc[j]

            high = float(
                candle["high"]
            )

            low = float(
                candle["low"]
            )

            # =============================================
            # BUY
            # =============================================

            if signal == "BUY":

                hit_sl = (
                    low <= stop_loss
                )

                hit_tp = (
                    high >= take_profit
                )

                # SL ưu tiên
                if hit_sl:

                    exit_price = stop_loss

                    exit_reason = "STOP_LOSS"

                    exit_index = j

                    exit_time = int(
                        candle["time"]
                    )

                    break

                if hit_tp:

                    exit_price = take_profit

                    exit_reason = "TAKE_PROFIT"

                    exit_index = j

                    exit_time = int(
                        candle["time"]
                    )

                    break

            # =============================================
            # SELL
            # =============================================

            else:

                hit_sl = (
                    high >= stop_loss
                )

                hit_tp = (
                    low <= take_profit
                )

                # SL ưu tiên
                if hit_sl:

                    exit_price = stop_loss

                    exit_reason = "STOP_LOSS"

                    exit_index = j

                    exit_time = int(
                        candle["time"]
                    )

                    break

                if hit_tp:

                    exit_price = take_profit

                    exit_reason = "TAKE_PROFIT"

                    exit_index = j

                    exit_time = int(
                        candle["time"]
                    )

                    break

            j += 1

        # =================================================
        # CHƯA CHẠM SL / TP
        # =================================================

        if exit_price is None:

            exit_index = len(df) - 1

            last_candle = df.iloc[
                exit_index
            ]

            exit_price = float(
                last_candle["close"]
            )

            exit_time = int(
                last_candle["time"]
            )

            exit_reason = "END_OF_DATA"

        # =================================================
        # TÍNH LỢI NHUẬN TRƯỚC PHÍ
        # =================================================

        if signal == "BUY":

            price_change = (
                exit_price
                - entry_price
            )

        else:

            price_change = (
                entry_price
                - exit_price
            )

        raw_return = (
            price_change
            / entry_price
        )

        profit_before_fee = (
            balance
            * raw_return
        )

        # =================================================
        # PHÍ
        # =================================================

        entry_fee = (
            balance
            * fee_rate
        )

        exit_fee = (
            balance
            * fee_rate
        )

        trade_fee = (
            entry_fee
            + exit_fee
        )

        # =================================================
        # LỢI NHUẬN SAU PHÍ
        # =================================================

        profit_after_fee = (
            profit_before_fee
            - trade_fee
        )

        balance += profit_after_fee

        # =================================================
        # THỐNG KÊ PHÍ
        # =================================================

        total_fees += trade_fee

        total_profit_before_fees += (
            profit_before_fee
        )

        total_profit_after_fees += (
            profit_after_fee
        )

        # =================================================
        # WIN / LOSS
        # =================================================

        if profit_after_fee > 0:

            wins += 1

            gross_profit += (
                profit_after_fee
            )

            current_win_streak += 1

            current_loss_streak = 0

            if current_win_streak > max_win_streak:

                max_win_streak = (
                    current_win_streak
                )

        elif profit_after_fee < 0:

            losses += 1

            gross_loss += abs(
                profit_after_fee
            )

            current_loss_streak += 1

            current_win_streak = 0

            if current_loss_streak > max_loss_streak:

                max_loss_streak = (
                    current_loss_streak
                )

        # =================================================
        # BUY / SELL STATS
        # =================================================

        if signal == "BUY":

            buy_trades += 1

            if profit_after_fee > 0:

                buy_wins += 1

            elif profit_after_fee < 0:

                buy_losses += 1

        else:

            sell_trades += 1

            if profit_after_fee > 0:

                sell_wins += 1

            elif profit_after_fee < 0:

                sell_losses += 1

        # =================================================
        # DRAWDOWN
        # =================================================

        equity = balance

        if equity > peak_equity:

            peak_equity = equity

        drawdown = (
            peak_equity
            - equity
        )

        if drawdown > max_drawdown:

            max_drawdown = drawdown

        equity_curve.append({
            "trade_number": len(trades) + 1,
            "balance": round(
                balance,
                2
            )
        })

        # =================================================
        # GHI LẠI TRADE
        # =================================================

        trades.append({

            "trade_number": (
                len(trades) + 1
            ),

            "signal": signal,

            "entry_time": entry_time,

            "exit_time": exit_time,

            "entry_price": round(
                entry_price,
                2
            ),

            "exit_price": round(
                exit_price,
                2
            ),

            "stop_loss": round(
                stop_loss,
                2
            ),

            "take_profit": round(
                take_profit,
                2
            ),

            "exit_reason": exit_reason,

            "profit_before_fee": round(
                profit_before_fee,
                2
            ),

            "fee": round(
                trade_fee,
                2
            ),

            "profit": round(
                profit_after_fee,
                2
            ),

            "return_percent": round(
                (
                    profit_after_fee
                    / (
                        balance
                        - profit_after_fee
                    )
                ) * 100,
                4
            ),

            "balance_after": round(
                balance,
                2
            )
        })

        # =================================================
        # BỎ QUA CÁC NẾN ĐÃ NẰM TRONG LỆNH
        # =================================================

        if exit_index > i:

            i = exit_index + 1

        else:

            i += 1

    # =====================================================
    # TỔNG SỐ LỆNH
    # =====================================================

    total_trades = len(trades)

    # =====================================================
    # WIN RATE
    # =====================================================

    if total_trades > 0:

        win_rate = (
            wins
            / total_trades
        ) * 100

    else:

        win_rate = 0.0

    # =====================================================
    # BUY WIN RATE
    # =====================================================

    if buy_trades > 0:

        buy_win_rate = (
            buy_wins
            / buy_trades
        ) * 100

    else:

        buy_win_rate = 0.0

    # =====================================================
    # SELL WIN RATE
    # =====================================================

    if sell_trades > 0:

        sell_win_rate = (
            sell_wins
            / sell_trades
        ) * 100

    else:

        sell_win_rate = 0.0

    # =====================================================
    # AVERAGE WIN
    # =====================================================

    winning_profits = [
        trade["profit"]
        for trade in trades
        if trade["profit"] > 0
    ]

    losing_profits = [
        trade["profit"]
        for trade in trades
        if trade["profit"] < 0
    ]

    if winning_profits:

        average_win = (
            sum(winning_profits)
            / len(winning_profits)
        )

    else:

        average_win = 0.0

    if losing_profits:

        average_loss = (
            sum(losing_profits)
            / len(losing_profits)
        )

    else:

        average_loss = 0.0

    # =====================================================
    # PROFIT FACTOR
    # =====================================================

    if gross_loss > 0:

        profit_factor = (
            gross_profit
            / gross_loss
        )

    elif gross_profit > 0:

        profit_factor = None

    else:

        profit_factor = 0.0

    # =====================================================
    # TOTAL RETURN
    # =====================================================

    total_return_percent = (
        (
            balance
            - initial_balance
        )
        / initial_balance
    ) * 100

    # =====================================================
    # MAX DRAWDOWN %
    # =====================================================

    if peak_equity > 0:

        max_drawdown_percent = (
            max_drawdown
            / peak_equity
        ) * 100

    else:

        max_drawdown_percent = 0.0

    # =====================================================
    # KẾT QUẢ CUỐI
    # =====================================================

    return {

        "status": "ok",

        "version": VERSION,

        "strategy": "Signal v1.6.1",

        "data": {
            "candles": len(df),
            "timeframe": "1h"
        },

        "account": {

            "initial_balance": round(
                initial_balance,
                2
            ),

            "final_balance": round(
                balance,
                2
            ),

            "total_profit": round(
                total_profit_after_fees,
                2
            ),

            "total_return_percent": round(
                total_return_percent,
                2
            )
        },

        "trades": {

            "total": total_trades,

            "wins": wins,

            "losses": losses,

            "win_rate": round(
                win_rate,
                2
            )
        },

        "buy": {

            "trades": buy_trades,

            "wins": buy_wins,

            "losses": buy_losses,

            "win_rate": round(
                buy_win_rate,
                2
            )
        },

        "sell": {

            "trades": sell_trades,

            "wins": sell_wins,

            "losses": sell_losses,

            "win_rate": round(
                sell_win_rate,
                2
            )
        },

        "performance": {

            "average_win": round(
                average_win,
                2
            ),

            "average_loss": round(
                average_loss,
                2
            ),

            "profit_factor": (
                round(
                    profit_factor,
                    2
                )
                if profit_factor is not None
                else None
            ),

            "gross_profit": round(
                gross_profit,
                2
            ),

            "gross_loss": round(
                gross_loss,
                2
            ),

            "profit_before_fees": round(
                total_profit_before_fees,
                2
            ),

            "total_fees": round(
                total_fees,
                2
            )
        },

        "risk": {

            "max_drawdown": round(
                max_drawdown,
                2
            ),

            "max_drawdown_percent": round(
                max_drawdown_percent,
                2
            ),

            "max_win_streak": max_win_streak,

            "max_loss_streak": max_loss_streak
        },

        "settings": {

            "fee_rate_per_side": fee_rate,

            "slippage": slippage
        },

        "equity_curve": equity_curve,

        "trade_history": trades
    }
