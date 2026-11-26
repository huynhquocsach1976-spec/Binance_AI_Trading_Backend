VERSION = "1.4.0"
STRATEGY = "Signal v1.6.1"


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def get_trade_score(trade):
    return trade.get("score")


def is_filtered(trade, filter_name):
    """
    Trả về True nếu trade bị loại trong test hiện tại.
    """

    signal = str(trade.get("signal", "")).upper()
    score = get_trade_score(trade)

    if score is None:
        return False

    score = safe_float(score)

    # -------------------------------------------------
    # TEST 1: loại SELL score -8/-9
    # -------------------------------------------------
    if filter_name == "REMOVE_SELL_-8_-9":
        return signal == "SELL" and -9 <= score <= -8

    # -------------------------------------------------
    # TEST 2: loại BUY score 12-14
    # -------------------------------------------------
    if filter_name == "REMOVE_BUY_12_14":
        return signal == "BUY" and 12 <= score <= 14

    # -------------------------------------------------
    # TEST 3: loại cả hai nhóm
    # -------------------------------------------------
    if filter_name == "REMOVE_BOTH":
        remove_sell = signal == "SELL" and -9 <= score <= -8
        remove_buy = signal == "BUY" and 12 <= score <= 14

        return remove_sell or remove_buy

    return False


def calculate_trade_stats(trades):
    total = len(trades)

    if total == 0:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "profit_factor": 0.0,
        }

    wins = 0
    losses = 0

    gross_profit = 0.0
    gross_loss = 0.0

    profits = []

    for trade in trades:

        profit = safe_float(
            trade.get("profit"),
            trade.get("pnl", 0.0)
        )

        profits.append(profit)

        if profit > 0:
            wins += 1
            gross_profit += profit

        elif profit < 0:
            losses += 1
            gross_loss += abs(profit)

    win_rate = (wins / total) * 100

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = None

    average_win = (
        gross_profit / wins
        if wins > 0
        else 0.0
    )

    average_loss = (
        -(gross_loss / losses)
        if losses > 0
        else 0.0
    )

    profit = sum(profits)

    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),
        "profit": round(profit, 4),
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "average_win": round(average_win, 4),
        "average_loss": round(average_loss, 4),
        "profit_factor": (
            round(profit_factor, 4)
            if profit_factor is not None
            else None
        ),
    }


def calculate_side_stats(trades):
    buy_trades = [
        t for t in trades
        if str(t.get("signal", "")).upper() == "BUY"
    ]

    sell_trades = [
        t for t in trades
        if str(t.get("signal", "")).upper() == "SELL"
    ]

    return {
        "BUY": calculate_trade_stats(buy_trades),
        "SELL": calculate_trade_stats(sell_trades),
    }


def calculate_fee_stats(trades):
    total_fees = 0.0
    profit_before_fees = 0.0

    for trade in trades:

        profit = safe_float(
            trade.get("profit"),
            trade.get("pnl", 0.0)
        )

        fees = safe_float(
            trade.get("fees"),
            trade.get("fee", 0.0)
        )

        total_fees += fees
        profit_before_fees += profit + fees

    profit_after_fees = sum(
        safe_float(
            t.get("profit"),
            t.get("pnl", 0.0)
        )
        for t in trades
    )

    return {
        "profit_before_fees": round(profit_before_fees, 4),
        "total_fees": round(total_fees, 4),
        "profit_after_fees": round(profit_after_fees, 4),
        "fee_impact": round(-total_fees, 4),
    }


def calculate_drawdown(trades, initial_balance):
    """
    Tính max drawdown từ chuỗi balance của trade records.
    """

    balance = safe_float(initial_balance, 1000.0)

    peak = balance
    max_drawdown = 0.0
    max_drawdown_pct = 0.0

    for trade in trades:

        if "balance" in trade:
            balance = safe_float(
                trade.get("balance"),
                balance
            )
        else:
            balance += safe_float(
                trade.get("profit"),
                trade.get("pnl", 0.0)
            )

        if balance > peak:
            peak = balance

        drawdown = peak - balance

        if drawdown > max_drawdown:
            max_drawdown = drawdown

        if peak > 0:
            dd_pct = (drawdown / peak) * 100

            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct

    return {
        "max_drawdown": round(max_drawdown, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
    }


def build_hypothetical_test(engine_result, filter_name):
    """
    Chạy hypothetical test trên trade records hiện có.

    QUAN TRỌNG:
    Đây không phải backtest mới.

    Nó chỉ loại các trade thuộc nhóm score được chỉ định
    khỏi kết quả trade hiện tại.
    """

    if not isinstance(engine_result, dict):
        return {
            "status": "error",
            "message": "engine_result phải là dict"
        }

    summary = engine_result.get("summary", {})

    trades = engine_result.get("trades", [])

    if not isinstance(trades, list):
        trades = []

    initial_balance = safe_float(
        summary.get("initial_balance"),
        1000.0
    )

    original_total = len(trades)

    kept_trades = []
    removed_trades = []

    for trade in trades:

        if is_filtered(trade, filter_name):
            removed_trades.append(trade)
        else:
            kept_trades.append(trade)

    stats = calculate_trade_stats(kept_trades)

    side_stats = calculate_side_stats(kept_trades)

    fee_stats = calculate_fee_stats(kept_trades)

    drawdown = calculate_drawdown(
        kept_trades,
        initial_balance
    )

    final_balance = (
        initial_balance +
        stats["profit"]
    )

    return {
        "filter": filter_name,
        "original_trades": original_total,
        "removed_trades": len(removed_trades),
        "remaining_trades": len(kept_trades),

        "summary": {
            **stats,
            "initial_balance": round(initial_balance, 4),
            "final_balance": round(final_balance, 4),
            "return_pct": round(
                (
                    (final_balance - initial_balance)
                    / initial_balance
                ) * 100,
                4
            ),
            **drawdown,
        },

        "side_analysis": side_stats,

        "fee_analysis": fee_stats,

        "removed_trade_analysis": calculate_trade_stats(
            removed_trades
        ),
    }


def run_diagnostic_v14(engine_result):
    """
    Diagnostic v1.4
    """

    if not isinstance(engine_result, dict):
        return {
            "status": "error",
            "version": VERSION,
            "message": "engine_result không hợp lệ"
        }

    trades = engine_result.get("trades", [])

    if not isinstance(trades, list):
        trades = []

    # -------------------------------------------------
    # BASELINE
    # -------------------------------------------------

    baseline = build_hypothetical_test(
        engine_result,
        "BASELINE"
    )

    # -------------------------------------------------
    # TEST 1
    # -------------------------------------------------

    remove_sell = build_hypothetical_test(
        engine_result,
        "REMOVE_SELL_-8_-9"
    )

    # -------------------------------------------------
    # TEST 2
    # -------------------------------------------------

    remove_buy = build_hypothetical_test(
        engine_result,
        "REMOVE_BUY_12_14"
    )

    # -------------------------------------------------
    # TEST 3
    # -------------------------------------------------

    remove_both = build_hypothetical_test(
        engine_result,
        "REMOVE_BOTH"
    )

    tests = [
        baseline,
        remove_sell,
        remove_buy,
        remove_both,
    ]

    return {
        "status": "ok",
        "version": VERSION,
        "strategy": STRATEGY,
        "data": {
            "original_trades": len(trades),
            "tests": len(tests),
        },
        "tests": {
            "BASELINE": baseline,
            "REMOVE_SELL_-8_-9": remove_sell,
            "REMOVE_BUY_12_14": remove_buy,
            "REMOVE_BOTH": remove_both,
        },
    }


def print_test_result(name, result):
    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    summary = result.get("summary", {})

    print(
        f"Trades ban đầu : "
        f"{result.get('original_trades', 0)}"
    )

    print(
        f"Trades loại    : "
        f"{result.get('removed_trades', 0)}"
    )

    print(
        f"Trades còn lại : "
        f"{result.get('remaining_trades', 0)}"
    )

    print(
        f"Profit         : "
        f"{summary.get('profit', 0)}"
    )

    print(
        f"Return         : "
        f"{summary.get('return_pct', 0)}%"
    )

    print(
        f"Win rate       : "
        f"{summary.get('win_rate', 0)}%"
    )

    print(
        f"Profit Factor  : "
        f"{summary.get('profit_factor')}"
    )

    print(
        f"Max Drawdown   : "
        f"{summary.get('max_drawdown_pct', 0)}%"
    )

    print()

    side = result.get("side_analysis", {})

    buy = side.get("BUY", {})
    sell = side.get("SELL", {})

    print(
        f"BUY  : "
        f"{buy.get('trades', 0)} trades | "
        f"PF {buy.get('profit_factor')} | "
        f"Profit {buy.get('profit')}"
    )

    print(
        f"SELL : "
        f"{sell.get('trades', 0)} trades | "
        f"PF {sell.get('profit_factor')} | "
        f"Profit {sell.get('profit')}"
    )

    fee = result.get("fee_analysis", {})

    print()

    print(
        f"Profit trước phí : "
        f"{fee.get('profit_before_fees', 0)}"
    )

    print(
        f"Tổng phí         : "
        f"{fee.get('total_fees', 0)}"
    )

    print(
        f"Profit sau phí    : "
        f"{fee.get('profit_after_fees', 0)}"
    )


def print_diagnostic(result):
    print()
    print("=" * 70)
    print("BACKTEST DIAGNOSTIC v1.4.0")
    print("Hypothetical Filter Test")
    print("=" * 70)

    print(
        f"Strategy: {result.get('strategy')}"
    )

    print(
        f"Original trades: "
        f"{result.get('data', {}).get('original_trades', 0)}"
    )

    tests = result.get("tests", {})

    for name, test in tests.items():
        print_test_result(name, test)

    print()
    print("=" * 70)
    print("KẾT THÚC DIAGNOSTIC v1.4")
    print("=" * 70)


if __name__ == "__main__":
    print(
        "backtest_diagnostic_v14.py "
        "là module diagnostic."
    )

    print(
        "Không chạy trực tiếp nếu chưa truyền "
        "engine_result."
    )
