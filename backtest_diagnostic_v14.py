VERSION = "1.4.0"


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def get_trade_profit(trade):
    """
    Lấy profit của một trade.
    """
    return safe_float(
        trade.get(
            "profit",
            trade.get("pnl", 0.0)
        )
    )


def get_trade_fee(trade):
    """
    Lấy fee của một trade.
    """
    return safe_float(
        trade.get(
            "fees",
            trade.get("fee", 0.0)
        )
    )


def get_trade_score(trade):
    """
    Lấy score của trade.
    """
    value = trade.get("score")

    if value is None:
        return None

    try:
        return float(value)
    except Exception:
        return None


def trade_side(trade):
    signal = str(
        trade.get("signal", "")
    ).upper()

    if signal in ["BUY", "SELL"]:
        return signal

    return None


def calculate_profit_factor(trades):
    gross_profit = 0.0
    gross_loss = 0.0

    for trade in trades:
        profit = get_trade_profit(trade)

        if profit > 0:
            gross_profit += profit

        elif profit < 0:
            gross_loss += abs(profit)

    if gross_loss == 0:
        if gross_profit > 0:
            return float("inf")
        return 0.0

    return gross_profit / gross_loss


def calculate_max_drawdown(trades, initial_balance):
    """
    Tính drawdown trên chuỗi profit của các trade được giữ lại.

    Đây là diagnostic giả định, KHÔNG phải backtest compounding
    đầy đủ như backtest_engine.
    """

    balance = float(initial_balance)
    peak = balance
    max_drawdown = 0.0

    for trade in trades:
        balance += get_trade_profit(trade)

        if balance > peak:
            peak = balance

        if peak > 0:
            drawdown = (peak - balance) / peak * 100.0

            if drawdown > max_drawdown:
                max_drawdown = drawdown

    return max_drawdown


def analyze_trade_set(
    trades,
    initial_balance=1000.0
):
    total = len(trades)

    wins = 0
    losses = 0

    profit = 0.0
    fees = 0.0

    buy_count = 0
    sell_count = 0

    buy_profit = 0.0
    sell_profit = 0.0

    for trade in trades:

        p = get_trade_profit(trade)

        profit += p
        fees += get_trade_fee(trade)

        side = trade_side(trade)

        if p > 0:
            wins += 1

        elif p < 0:
            losses += 1

        if side == "BUY":
            buy_count += 1
            buy_profit += p

        elif side == "SELL":
            sell_count += 1
            sell_profit += p

    if total > 0:
        win_rate = wins / total * 100.0
    else:
        win_rate = 0.0

    final_balance = initial_balance + profit

    if initial_balance > 0:
        return_pct = (
            (final_balance - initial_balance)
            / initial_balance
            * 100.0
        )
    else:
        return_pct = 0.0

    pf = calculate_profit_factor(trades)

    max_dd = calculate_max_drawdown(
        trades,
        initial_balance
    )

    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),

        "profit": round(profit, 6),
        "fees": round(fees, 6),

        "final_balance_hypothetical": round(
            final_balance,
            6
        ),

        "return_pct_hypothetical": round(
            return_pct,
            6
        ),

        "profit_factor": (
            round(pf, 6)
            if pf != float("inf")
            else "inf"
        ),

        "max_drawdown_hypothetical_pct": round(
            max_dd,
            6
        ),

        "BUY": {
            "trades": buy_count,
            "profit": round(buy_profit, 6)
        },

        "SELL": {
            "trades": sell_count,
            "profit": round(sell_profit, 6)
        }
    }


def is_sell_minus_8_9(trade):
    score = get_trade_score(trade)

    if score is None:
        return False

    return (
        trade_side(trade) == "SELL"
        and -9 <= score <= -8
    )


def is_buy_12_14(trade):
    score = get_trade_score(trade)

    if score is None:
        return False

    return (
        trade_side(trade) == "BUY"
        and 12 <= score <= 14
    )


def filter_trades(trades, mode):
    result = []

    for trade in trades:

        remove = False

        if mode == "REMOVE_SELL_-8_-9":
            remove = is_sell_minus_8_9(trade)

        elif mode == "REMOVE_BUY_12_14":
            remove = is_buy_12_14(trade)

        elif mode == "REMOVE_BOTH":
            remove = (
                is_sell_minus_8_9(trade)
                or is_buy_12_14(trade)
            )

        if not remove:
            result.append(trade)

    return result


def run_diagnostic_v14(
    engine_result,
    initial_balance=1000.0
):
    """
    Chạy Diagnostic v1.4 trên kết quả Backtest Engine.

    Lưu ý:
    Đây là hypothetical filter analysis.
    Không phải re-backtest compounding đầy đủ.
    """

    trades = engine_result.get("trades", [])

    if not isinstance(trades, list):
        return {
            "status": "error",
            "version": VERSION,
            "message": "engine_result.trades không phải list"
        }

    if len(trades) == 0:
        return {
            "status": "error",
            "version": VERSION,
            "message": "Không có trades để diagnostic"
        }

    baseline = analyze_trade_set(
        trades,
        initial_balance
    )

    sell_8_9_removed = filter_trades(
        trades,
        "REMOVE_SELL_-8_-9"
    )

    buy_12_14_removed = filter_trades(
        trades,
        "REMOVE_BUY_12_14"
    )

    both_removed = filter_trades(
        trades,
        "REMOVE_BOTH"
    )

    result = {
        "status": "ok",
        "version": VERSION,

        "method": (
            "Hypothetical trade-filter diagnostic "
            "using existing Backtest v1.2 trades"
        ),

        "warning": (
            "Đây là diagnostic giả định trên danh sách "
            "trade hiện có; chưa phải re-backtest "
            "compounding đầy đủ."
        ),

        "baseline": baseline,

        "remove_sell_minus_8_9": analyze_trade_set(
            sell_8_9_removed,
            initial_balance
        ),

        "remove_buy_12_14": analyze_trade_set(
            buy_12_14_removed,
            initial_balance
        ),

        "remove_both": analyze_trade_set(
            both_removed,
            initial_balance
        ),

        "removed_trade_count": {
            "SELL_-8_-9": (
                len(trades) - len(sell_8_9_removed)
            ),
            "BUY_12_14": (
                len(trades) - len(buy_12_14_removed)
            ),
            "BOTH": (
                len(trades) - len(both_removed)
            )
        }
    }

    return result
