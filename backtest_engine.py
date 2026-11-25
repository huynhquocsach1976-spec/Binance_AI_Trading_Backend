import pandas as pd
from ai_analyzer import analyze_market


VERSION = "1.0.0"


def run_backtest(
    candles,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001
):
    """
    Backtest Signal v1.6.1

    Quy tắc:
    - Phân tích tại nến hiện tại
    - Nếu có BUY/SELL thì vào lệnh ở OPEN nến kế tiếp
    - Chỉ vào lệnh khi trade_allowed = True
    - SL/TP lấy từ tín hiệu
    - Nếu cùng một nến chạm cả SL và TP -> ưu tiên SL
    - Chỉ giữ 1 lệnh tại một thời điểm
    """

    if not candles:
        return {
            "status": "error",
            "message": "Không có dữ liệu nến"
        }

    if len(candles) < 60:
        return {
            "status": "error",
            "message": f"Cần ít nhất 60 nến, hiện có {len(candles)} nến"
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

    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=["open", "high", "low", "close"]
    ).reset_index(drop=True)

    balance = float(initial_balance)
    equity = float(initial_balance)

    trades = []

    wins = 0
    losses = 0

    total_profit = 0.0
    gross_profit = 0.0
    gross_loss = 0.0

    peak_equity = balance
    max_drawdown = 0.0

    i = 50

    while i < len(df) - 1:

        history = df.iloc[:i + 1].copy()

        history_candles = history.to_dict(
            orient="records"
        )

        try:
            signal_result = analyze_market(
                history_candles
            )
        except Exception as e:
            i += 1
            continue

        signal = signal_result.get("signal")
        trade_allowed = signal_result.get(
            "trade_allowed",
            False
        )

        if signal not in ["BUY", "SELL"]:
            i += 1
            continue

        if not trade_allowed:
            i += 1
            continue

        stop_loss = signal_result.get("stop_loss")
        take_profit = signal_result.get("take_profit")

        if stop_loss is None or take_profit is None:
            i += 1
            continue

        # ==========================================
        # VÀO LỆNH Ở OPEN CỦA NẾN KẾ TIẾP
        # ==========================================

        entry_index = i + 1

        entry_candle = df.iloc[entry_index]

        raw_entry = float(entry_candle["open"])

        # Slippage
        if signal == "BUY":
            entry_price = raw_entry * (
                1 + slippage
            )
        else:
            entry_price = raw_entry * (
                1 - slippage
            )

        stop_loss = float(stop_loss)
        take_profit = float(take_profit)

        entry_time = int(entry_candle["time"])

        exit_price = None
        exit_time = None
        exit_reason = None
        exit_index = None

        # ==========================================
        # TÌM SL / TP
        # ==========================================

        j = entry_index

        while j < len(df):

            candle = df.iloc[j]

            high = float(candle["high"])
            low = float(candle["low"])

            # -----------------------------
            # BUY
            # -----------------------------

            if signal == "BUY":

                hit_sl = low <= stop_loss
                hit_tp = high >= take_profit

                # Nếu cùng lúc chạm cả SL và TP
                # => ưu tiên SL
                if hit_sl:
                    exit_price = stop_loss
                    exit_reason = "STOP_LOSS"
                    exit_index = j
                    exit_time = int(candle["time"])
                    break

                if hit_tp:
                    exit_price = take_profit
                    exit_reason = "TAKE_PROFIT"
                    exit_index = j
                    exit_time = int(candle["time"])
                    break

            # -----------------------------
            # SELL
            # -----------------------------

            else:

                hit_sl = high >= stop_loss
                hit_tp = low <= take_profit

                # Nếu cùng lúc chạm cả SL và TP
                # => ưu tiên SL
                if hit_sl:
                    exit_price = stop_loss
                    exit_reason = "STOP_LOSS"
                    exit_index = j
                    exit_time = int(candle["time"])
                    break

                if hit_tp:
                    exit_price = take_profit
                    exit_reason = "TAKE_PROFIT"
                    exit_index = j
                    exit_time = int(candle["time"])
                    break

            j += 1

        # ==========================================
        # NẾU CHƯA CHẠM SL / TP
        # ==========================================

        if exit_price is None:

            last_index = len(df) - 1

            last_candle = df.iloc[last_index]

            exit_price = float(
                last_candle["close"]
            )

            exit_time = int(
                last_candle["time"]
            )

            exit_index = last_index

            exit_reason = "END_OF_DATA"

        # ==========================================
        # TÍNH LỢI NHUẬN
        # ==========================================

        if signal == "BUY":

            price_change = (
                exit_price - entry_price
            )

        else:

            price_change = (
                entry_price - exit_price
            )

        raw_return_pct = (
            price_change / entry_price
        )

        # Fee 2 chiều
        total_fee_rate = fee_rate * 2

        net_return_pct = (
            raw_return_pct
            - total_fee_rate
        )

        profit = (
            balance * net_return_pct
        )

        balance += profit

        total_profit += profit

        if profit > 0:

            wins += 1
            gross_profit += profit

        elif profit < 0:

            losses += 1
            gross_loss += abs(profit)

        # ==========================================
        # EQUITY / DRAWDOWN
        # ==========================================

        equity = balance

        if equity > peak_equity:

            peak_equity = equity

        drawdown = (
            peak_equity - equity
        )

        if drawdown > max_drawdown:

            max_drawdown = drawdown

        trade = {
            "trade_number": len(trades) + 1,
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

            "profit": round(
                profit,
                2
            ),

            "return_percent": round(
                net_return_pct * 100,
                4
            ),

            "balance_after": round(
                balance,
                2
            )
        }

        trades.append(trade)

        # ==========================================
        # QUAN TRỌNG:
        # bỏ qua toàn bộ nến đã nằm trong lệnh
        # ==========================================

        if exit_index > i:

            i = exit_index + 1

        else:

            i += 1

    # ==========================================
    # THỐNG KÊ
    # ==========================================

    total_trades = len(trades)

    if total_trades > 0:

        win_rate = (
            wins / total_trades
        ) * 100

    else:

        win_rate = 0.0

    if gross_loss > 0:

        profit_factor = (
            gross_profit / gross_loss
        )

    else:

        if gross_profit > 0:
            profit_factor = None
        else:
            profit_factor = 0.0

    total_return_percent = (
        (
            balance - initial_balance
        )
        / initial_balance
    ) * 100

    max_drawdown_percent = (
        (
            max_drawdown
            / peak_equity
        ) * 100
        if peak_equity > 0
        else 0
    )

    return {
        "status": "ok",
        "version": VERSION,

        "strategy": "Signal v1.6.1",

        "initial_balance": round(
            initial_balance,
            2
        ),

        "final_balance": round(
            balance,
            2
        ),

        "total_profit": round(
            total_profit,
            2
        ),

        "total_return_percent": round(
            total_return_percent,
            2
        ),

        "total_trades": total_trades,

        "wins": wins,

        "losses": losses,

        "win_rate": round(
            win_rate,
            2
        ),

        "profit_factor": (
            round(profit_factor, 2)
            if profit_factor is not None
            else None
        ),

        "max_drawdown": round(
            max_drawdown,
            2
        ),

        "max_drawdown_percent": round(
            max_drawdown_percent,
            2
        ),

        "fee_rate_per_side": fee_rate,

        "slippage": slippage,

        "trades": trades
    }
