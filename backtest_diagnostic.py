import math
from collections import defaultdict


VERSION = "1.0.0"


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        value = float(value)
        if not math.isfinite(value):
            return default
        return value
    except Exception:
        return default


def _get_trade_result(trade):
    """
    Chuẩn hóa kết quả của một trade.
    Hỗ trợ nhiều tên field khác nhau để tương thích
    với backtest_engine hiện tại.
    """

    result = str(
        trade.get("result")
        or trade.get("exit_reason")
        or trade.get("reason")
        or ""
    ).upper()

    if "TAKE" in result or "TP" in result:
        return "TAKE_PROFIT"

    if "STOP" in result or "SL" in result:
        return "STOP_LOSS"

    if "END" in result:
        return "END_OF_DATA"

    # Một số engine có thể dùng pnl để xác định
    pnl = _safe_float(
        trade.get("pnl"),
        _safe_float(trade.get("profit"), 0.0)
    )

    if pnl > 0:
        return "WIN"

    if pnl < 0:
        return "LOSS"

    return "UNKNOWN"


def _get_pnl(trade):
    return _safe_float(
        trade.get("pnl"),
        _safe_float(
            trade.get("profit"),
            _safe_float(trade.get("net_pnl"), 0.0)
        )
    )


def _get_side(trade):
    side = str(
        trade.get("side")
        or trade.get("signal")
        or trade.get("direction")
        or ""
    ).upper()

    if side in ("BUY", "LONG"):
        return "BUY"

    if side in ("SELL", "SHORT"):
        return "SELL"

    return "UNKNOWN"


def _get_regime(trade):
    regime = str(
        trade.get("market_condition")
        or trade.get("regime")
        or trade.get("market_regime")
        or trade.get("condition")
        or ""
    ).upper()

    if not regime:
        return "UNKNOWN"

    return regime


def _calculate_group(trades):
    total = len(trades)

    wins = 0
    losses = 0
    profit = 0.0
    gross_profit = 0.0
    gross_loss = 0.0

    for trade in trades:
        pnl = _get_pnl(trade)

        profit += pnl

        if pnl > 0:
            wins += 1
            gross_profit += pnl

        elif pnl < 0:
            losses += 1
            gross_loss += abs(pnl)

    win_rate = (wins / total * 100) if total else 0.0

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = None

    average_win = gross_profit / wins if wins else 0.0
    average_loss = -(gross_loss / losses) if losses else 0.0

    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
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


def _find_trades(result):
    """
    Tìm danh sách trades trong output của backtest_engine.
    """

    if not isinstance(result, dict):
        return []

    candidates = [
        result.get("trades"),
        result.get("trade_history"),
        result.get("trade_records"),
    ]

    # Trường hợp run_backtest trả:
    # {
    #   "status": "ok",
    #   "result": {
    #       "trades": [...]
    #   }
    # }
    nested = result.get("result")

    if isinstance(nested, dict):
        candidates.extend([
            nested.get("trades"),
            nested.get("trade_history"),
            nested.get("trade_records"),
        ])

    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate

    return []


def _find_summary(result):
    if not isinstance(result, dict):
        return {}

    summary = result.get("summary")

    if isinstance(summary, dict):
        return summary

    nested = result.get("result")

    if isinstance(nested, dict):
        summary = nested.get("summary")

        if isinstance(summary, dict):
            return summary

    return {}


def _find_debug(result):
    if not isinstance(result, dict):
        return {}

    debug = result.get("debug")

    if isinstance(debug, dict):
        return debug

    nested = result.get("result")

    if isinstance(nested, dict):
        debug = nested.get("debug")

        if isinstance(debug, dict):
            return debug

    return {}


def _analyze_exit_reasons(trades):
    data = defaultdict(list)

    for trade in trades:
        reason = _get_trade_result(trade)

        data[reason].append(trade)

    output = {}

    for reason, reason_trades in data.items():
        stats = _calculate_group(reason_trades)

        output[reason] = stats

    return output


def _analyze_side(trades):
    data = defaultdict(list)

    for trade in trades:
        side = _get_side(trade)

        data[side].append(trade)

    output = {}

    for side, side_trades in data.items():
        output[side] = _calculate_group(side_trades)

    return output


def _analyze_regime(trades):
    data = defaultdict(list)

    for trade in trades:
        regime = _get_regime(trade)

        data[regime].append(trade)

    output = {}

    for regime, regime_trades in data.items():
        output[regime] = _calculate_group(regime_trades)

    return output


def _calculate_fee_impact(summary):
    """
    So sánh lợi nhuận trước phí và sau phí.
    """

    profit_before_fees = _safe_float(
        summary.get("profit_before_fees"),
        0.0
    )

    total_fees = _safe_float(
        summary.get("total_fees"),
        0.0
    )

    profit_after_fees = _safe_float(
        summary.get("profit"),
        0.0
    )

    return {
        "profit_before_fees": round(profit_before_fees, 4),
        "total_fees": round(total_fees, 4),
        "profit_after_fees": round(profit_after_fees, 4),
        "fee_impact": round(
            profit_after_fees - profit_before_fees,
            4
        ),
    }


def _generate_conclusion(
    summary,
    side_analysis,
    exit_analysis,
    regime_analysis,
):
    conclusions = []

    profit_factor = _safe_float(
        summary.get("profit_factor"),
        0.0
    )

    return_pct = _safe_float(
        summary.get("return_pct"),
        0.0
    )

    max_dd_pct = _safe_float(
        summary.get("max_drawdown_pct"),
        0.0
    )

    # -----------------------------
    # Profit Factor
    # -----------------------------

    if profit_factor < 1:
        conclusions.append(
            "PF < 1: chiến lược đang có lợi thế âm trên giai đoạn này."
        )

    elif profit_factor >= 1.2:
        conclusions.append(
            "PF >= 1.2: chiến lược có lợi thế tương đối tốt."
        )

    else:
        conclusions.append(
            "PF từ 1.0 đến dưới 1.2: lợi thế còn khá yếu."
        )

    # -----------------------------
    # Return
    # -----------------------------

    if return_pct < 0:
        conclusions.append(
            "Return âm: chưa nên đưa Signal hiện tại sang Paper Trading."
        )
    else:
        conclusions.append(
            "Return dương trên giai đoạn backtest."
        )

    # -----------------------------
    # Drawdown
    # -----------------------------

    if max_dd_pct >= 15:
        conclusions.append(
            "Drawdown >= 15%: rủi ro giảm vốn tương đối cao."
        )

    elif max_dd_pct >= 10:
        conclusions.append(
            "Drawdown >= 10%: cần chú ý kiểm soát rủi ro."
        )

    # -----------------------------
    # BUY vs SELL
    # -----------------------------

    buy = side_analysis.get("BUY", {})
    sell = side_analysis.get("SELL", {})

    buy_pf = buy.get("profit_factor")
    sell_pf = sell.get("profit_factor")

    if buy_pf is not None and sell_pf is not None:

        if buy_pf > sell_pf:
            conclusions.append(
                "BUY đang có hiệu quả tốt hơn SELL."
            )

        elif sell_pf > buy_pf:
            conclusions.append(
                "SELL đang có hiệu quả tốt hơn BUY."
            )

        else:
            conclusions.append(
                "BUY và SELL có hiệu quả gần tương đương."
            )

    # -----------------------------
    # Exit reason
    # -----------------------------

    stop_loss = exit_analysis.get("STOP_LOSS", {})
    take_profit = exit_analysis.get("TAKE_PROFIT", {})

    sl_count = stop_loss.get("trades", 0)
    tp_count = take_profit.get("trades", 0)

    if sl_count > tp_count:
        conclusions.append(
            "Số lệnh STOP_LOSS nhiều hơn TAKE_PROFIT."
        )

    # -----------------------------
    # Regime
    # -----------------------------

    best_regime = None
    best_profit = None

    worst_regime = None
    worst_profit = None

    for regime, stats in regime_analysis.items():

        if regime == "UNKNOWN":
            continue

        profit = _safe_float(stats.get("profit"), 0.0)

        if best_profit is None or profit > best_profit:
            best_profit = profit
            best_regime = regime

        if worst_profit is None or profit < worst_profit:
            worst_profit = profit
            worst_regime = regime

    if best_regime is not None:
        conclusions.append(
            f"Regime tốt nhất: {best_regime}."
        )

    if worst_regime is not None:
        conclusions.append(
            f"Regime yếu nhất: {worst_regime}."
        )

    return conclusions


def run_diagnostic(backtest_result):
    """
    Chạy Backtest Diagnostic v1.0

    Input:
        Kết quả trả về từ run_backtest()

    Output:
        Dictionary JSON-safe.
    """

    summary = _find_summary(backtest_result)
    debug = _find_debug(backtest_result)
    trades = _find_trades(backtest_result)

    side_analysis = _analyze_side(trades)

    exit_analysis = _analyze_exit_reasons(trades)

    regime_analysis = _analyze_regime(trades)

    fee_analysis = _calculate_fee_impact(summary)

    conclusion = _generate_conclusion(
        summary,
        side_analysis,
        exit_analysis,
        regime_analysis,
    )

    return {
        "status": "ok",
        "version": VERSION,

        "data": {
            "total_trades": len(trades),
            "source_summary": bool(summary),
            "source_trade_records": bool(trades),
        },

        "summary": {
            "initial_balance": summary.get(
                "initial_balance"
            ),
            "final_balance": summary.get(
                "final_balance"
            ),
            "profit": summary.get(
                "profit"
            ),
            "return_pct": summary.get(
                "return_pct"
            ),
            "total_trades": summary.get(
                "total_trades",
                len(trades)
            ),
            "win_rate": summary.get(
                "win_rate"
            ),
            "profit_factor": summary.get(
                "profit_factor"
            ),
            "max_drawdown_pct": summary.get(
                "max_drawdown_pct"
            ),
        },

        "side_analysis": side_analysis,

        "exit_analysis": exit_analysis,

        "regime_analysis": regime_analysis,

        "fee_analysis": fee_analysis,

        "engine_debug": debug,

        "conclusion": conclusion,
    }


def print_diagnostic(report):
    """
    In kết quả Diagnostic dễ đọc trên terminal.
    """

    print()
    print("=" * 70)
    print("BACKTEST DIAGNOSTIC v1.0")
    print("=" * 70)

    summary = report.get("summary", {})

    print()
    print("1. TỔNG QUAN")
    print("-" * 70)

    print(
        f"Initial Balance : "
        f"{summary.get('initial_balance')}"
    )

    print(
        f"Final Balance   : "
        f"{summary.get('final_balance')}"
    )

    print(
        f"Profit          : "
        f"{summary.get('profit')}"
    )

    print(
        f"Return %        : "
        f"{summary.get('return_pct')}"
    )

    print(
        f"Trades          : "
        f"{summary.get('total_trades')}"
    )

    print(
        f"Win Rate        : "
        f"{summary.get('win_rate')}"
    )

    print(
        f"Profit Factor   : "
        f"{summary.get('profit_factor')}"
    )

    print(
        f"Max Drawdown %  : "
        f"{summary.get('max_drawdown_pct')}"
    )

    print()
    print("2. BUY / SELL")
    print("-" * 70)

    for side, stats in report.get(
        "side_analysis", {}
    ).items():

        print(f"\n{side}")

        print(
            f"  Trades       : {stats['trades']}"
        )

        print(
            f"  Wins         : {stats['wins']}"
        )

        print(
            f"  Losses       : {stats['losses']}"
        )

        print(
            f"  Win Rate     : {stats['win_rate']}%"
        )

        print(
            f"  Profit       : {stats['profit']}"
        )

        print(
            f"  Profit Factor: {stats['profit_factor']}"
        )

    print()
    print("3. EXIT REASON")
    print("-" * 70)

    for reason, stats in report.get(
        "exit_analysis", {}
    ).items():

        print(f"\n{reason}")

        print(
            f"  Trades   : {stats['trades']}"
        )

        print(
            f"  Wins     : {stats['wins']}"
        )

        print(
            f"  Losses   : {stats['losses']}"
        )

        print(
            f"  Profit   : {stats['profit']}"
        )

    print()
    print("4. MARKET REGIME")
    print("-" * 70)

    for regime, stats in report.get(
        "regime_analysis", {}
    ).items():

        print(f"\n{regime}")

        print(
            f"  Trades   : {stats['trades']}"
        )

        print(
            f"  Win Rate : {stats['win_rate']}%"
        )

        print(
            f"  Profit   : {stats['profit']}"
        )

        print(
            f"  PF       : {stats['profit_factor']}"
        )

    print()
    print("5. FEE IMPACT")
    print("-" * 70)

    fee = report.get("fee_analysis", {})

    print(
        f"Profit before fees : "
        f"{fee.get('profit_before_fees')}"
    )

    print(
        f"Total fees        : "
        f"{fee.get('total_fees')}"
    )

    print(
        f"Profit after fees  : "
        f"{fee.get('profit_after_fees')}"
    )

    print()
    print("6. KẾT LUẬN")
    print("-" * 70)

    for item in report.get("conclusion", []):
        print(f"- {item}")

    print()
    print("=" * 70)
    print("END BACKTEST DIAGNOSTIC")
    print("=" * 70)


if __name__ == "__main__":

    print(
        "Backtest Diagnostic v1.0"
    )

    print(
        "File này là module phân tích."
    )

    print(
        "Hãy gọi run_diagnostic() "
        "sau khi chạy run_backtest()."
    )
