from collections import defaultdict


VERSION = "1.3.0"
STRATEGY = "Signal v1.6.1"


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def round_value(value, digits=4):
    if value is None:
        return None

    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def get_trades(engine_result):
    if not isinstance(engine_result, dict):
        return []

    trades = engine_result.get("trades", [])

    if not isinstance(trades, list):
        return []

    return trades


def get_summary(engine_result):
    if not isinstance(engine_result, dict):
        return {}

    summary = engine_result.get("summary", {})

    if not isinstance(summary, dict):
        return {}

    return summary


def get_debug(engine_result):
    if not isinstance(engine_result, dict):
        return {}

    debug = engine_result.get("debug", {})

    if not isinstance(debug, dict):
        return {}

    return debug


def get_signal(trade):
    return str(trade.get("signal", "")).upper()


def get_score(trade):
    value = trade.get("score")

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_regime(trade):
    regime = (
        trade.get("market_condition")
        or trade.get("market_regime")
        or trade.get("regime")
        or trade.get("condition")
        or "UNKNOWN"
    )

    return str(regime).upper()


def get_profit(trade):
    return safe_float(trade.get("profit"))


def get_exit_reason(trade):
    reason = (
        trade.get("exit_reason")
        or trade.get("reason")
        or "UNKNOWN"
    )

    return str(reason).upper()


# ============================================================
# TRADE STATISTICS
# ============================================================

def calculate_trade_stats(trades):
    trades = list(trades)

    total = len(trades)

    if total == 0:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "profit": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "average_win": 0,
            "average_loss": 0,
            "profit_factor": None,
        }

    wins = []
    losses = []

    for trade in trades:
        profit = get_profit(trade)

        if profit > 0:
            wins.append(profit)
        elif profit < 0:
            losses.append(profit)

    win_count = len(wins)
    loss_count = len(losses)

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    profit = gross_profit - gross_loss

    average_win = (
        gross_profit / win_count
        if win_count > 0
        else 0
    )

    average_loss = (
        -gross_loss / loss_count
        if loss_count > 0
        else 0
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else None
    )

    return {
        "trades": total,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": round_value(
            win_count / total * 100,
            2
        ),
        "profit": round_value(profit),
        "gross_profit": round_value(gross_profit),
        "gross_loss": round_value(gross_loss),
        "average_win": round_value(average_win),
        "average_loss": round_value(average_loss),
        "profit_factor": (
            round_value(profit_factor)
            if profit_factor is not None
            else None
        ),
    }


# ============================================================
# SIDE ANALYSIS
# ============================================================

def analyze_side(trades):
    result = {}

    for side in ["BUY", "SELL"]:
        side_trades = [
            trade
            for trade in trades
            if get_signal(trade) == side
        ]

        result[side] = calculate_trade_stats(side_trades)

    return result


# ============================================================
# EXIT ANALYSIS
# ============================================================

def analyze_exit(trades):
    groups = defaultdict(list)

    for trade in trades:
        reason = get_exit_reason(trade)
        groups[reason].append(trade)

    result = {}

    preferred_order = [
        "STOP_LOSS",
        "TAKE_PROFIT",
        "END_OF_DATA",
    ]

    for reason in preferred_order:
        if reason in groups:
            result[reason] = calculate_trade_stats(
                groups[reason]
            )

    for reason in sorted(groups.keys()):
        if reason not in result:
            result[reason] = calculate_trade_stats(
                groups[reason]
            )

    return result


# ============================================================
# REGIME ANALYSIS
# ============================================================

def analyze_regime(trades):
    groups = defaultdict(list)

    for trade in trades:
        regime = get_regime(trade)
        groups[regime].append(trade)

    result = {}

    for regime in sorted(groups.keys()):
        result[regime] = calculate_trade_stats(
            groups[regime]
        )

    return result


# ============================================================
# SCORE ANALYSIS
# ============================================================

def analyze_score(trades):
    score_groups = defaultdict(list)

    trades_with_score = 0
    trades_without_score = 0

    for trade in trades:
        score = get_score(trade)

        if score is None:
            trades_without_score += 1
            continue

        trades_with_score += 1
        score_groups[score].append(trade)

    overall = {}

    for score in sorted(
        score_groups.keys(),
        key=lambda x: x,
        reverse=True
    ):
        overall[str(score)] = calculate_trade_stats(
            score_groups[score]
        )

    buy = {}

    buy_scores = [
        score
        for score in score_groups.keys()
        if score > 0
    ]

    for score in sorted(buy_scores):
        buy[str(score)] = calculate_trade_stats(
            score_groups[score]
        )

    sell = {}

    sell_scores = [
        score
        for score in score_groups.keys()
        if score < 0
    ]

    for score in sorted(sell_scores, reverse=True):
        sell[str(score)] = calculate_trade_stats(
            score_groups[score]
        )

    by_regime_and_score = {}

    regime_score_groups = defaultdict(list)

    for trade in trades:
        score = get_score(trade)

        if score is None:
            continue

        regime = get_regime(trade)

        key = f"{regime}|{score}"

        regime_score_groups[key].append(trade)

    for key in sorted(regime_score_groups.keys()):
        by_regime_and_score[key] = calculate_trade_stats(
            regime_score_groups[key]
        )

    return {
        "overall": overall,
        "BUY": buy,
        "SELL": sell,
        "by_regime_and_score": by_regime_and_score,
        "data_quality": {
            "trades_with_score": trades_with_score,
            "trades_without_score": trades_without_score,
            "score_coverage_pct": round_value(
                (
                    trades_with_score / len(trades) * 100
                    if trades
                    else 0
                ),
                2
            ),
        },
    }


# ============================================================
# SCORE GROUP ANALYSIS v1.3
# ============================================================

def get_score_group(score):
    """
    Gom score thành nhóm để giảm ảnh hưởng của
    những nhóm có quá ít mẫu.

    BUY:
        +8  -> +9
        +10 -> +11
        +12 -> +14
        +15 trở lên

    SELL:
        -8  -> -9
        -10 -> -11
        -12 -> -14
        -15 trở xuống
    """

    if score is None:
        return "UNKNOWN"

    # BUY
    if score >= 8:
        if score <= 9:
            return "BUY_8_9"

        if score <= 11:
            return "BUY_10_11"

        if score <= 14:
            return "BUY_12_14"

        return "BUY_15_PLUS"

    # SELL
    if score <= -8:
        if score >= -9:
            return "SELL_-8_-9"

        if score >= -11:
            return "SELL_-10_-11"

        if score >= -14:
            return "SELL_-12_-14"

        return "SELL_-15_MINUS"

    return "OTHER"


def analyze_score_groups(trades):
    """
    Phân tích score theo nhóm lớn.

    Đây là phần quan trọng nhất của Diagnostic v1.3.
    Không thay đổi bất kỳ logic giao dịch nào.
    """

    groups = defaultdict(list)

    for trade in trades:
        score = get_score(trade)

        if score is None:
            continue

        group = get_score_group(score)

        groups[group].append(trade)

    preferred_order = [
        "BUY_8_9",
        "BUY_10_11",
        "BUY_12_14",
        "BUY_15_PLUS",
        "SELL_-8_-9",
        "SELL_-10_-11",
        "SELL_-12_-14",
        "SELL_-15_MINUS",
    ]

    result = {}

    for group in preferred_order:
        if group not in groups:
            continue

        stats = calculate_trade_stats(groups[group])

        scores = [
            get_score(trade)
            for trade in groups[group]
            if get_score(trade) is not None
        ]

        profits = [
            get_profit(trade)
            for trade in groups[group]
        ]

        stats["score_min"] = (
            min(scores)
            if scores
            else None
        )

        stats["score_max"] = (
            max(scores)
            if scores
            else None
        )

        stats["average_score"] = (
            round_value(
                sum(scores) / len(scores),
                2
            )
            if scores
            else None
        )

        stats["total_profit"] = round_value(
            sum(profits)
        )

        result[group] = stats

    # Bổ sung nhóm UNKNOWN / OTHER nếu có
    for group in sorted(groups.keys()):
        if group not in result:
            stats = calculate_trade_stats(groups[group])

            scores = [
                get_score(trade)
                for trade in groups[group]
                if get_score(trade) is not None
            ]

            stats["score_min"] = (
                min(scores)
                if scores
                else None
            )

            stats["score_max"] = (
                max(scores)
                if scores
                else None
            )

            stats["average_score"] = (
                round_value(
                    sum(scores) / len(scores),
                    2
                )
                if scores
                else None
            )

            stats["total_profit"] = round_value(
                sum(
                    get_profit(trade)
                    for trade in groups[group]
                )
            )

            result[group] = stats

    return result


# ============================================================
# SCORE GROUP CONCLUSIONS
# ============================================================

def build_score_group_conclusions(score_groups):
    conclusions = []

    # --------------------------------------------------------
    # Minimum sample size
    # --------------------------------------------------------

    minimum_sample = 5

    valid_groups = {
        name: stats
        for name, stats in score_groups.items()
        if stats.get("trades", 0) >= minimum_sample
    }

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    buy_groups = {
        name: stats
        for name, stats in valid_groups.items()
        if name.startswith("BUY_")
    }

    if buy_groups:
        best_buy = max(
            buy_groups.items(),
            key=lambda item: (
                item[1].get("profit_factor")
                if item[1].get("profit_factor") is not None
                else -999
            )
        )

        worst_buy = min(
            buy_groups.items(),
            key=lambda item: (
                item[1].get("profit_factor")
                if item[1].get("profit_factor") is not None
                else 999
            )
        )

        conclusions.append(
            "BUY group tốt nhất theo PF: "
            f"{best_buy[0]} "
            f"(PF={best_buy[1].get('profit_factor')})."
        )

        conclusions.append(
            "BUY group yếu nhất theo PF: "
            f"{worst_buy[0]} "
            f"(PF={worst_buy[1].get('profit_factor')})."
        )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    sell_groups = {
        name: stats
        for name, stats in valid_groups.items()
        if name.startswith("SELL_")
    }

    if sell_groups:
        best_sell = max(
            sell_groups.items(),
            key=lambda item: (
                item[1].get("profit_factor")
                if item[1].get("profit_factor") is not None
                else -999
            )
        )

        worst_sell = min(
            sell_groups.items(),
            key=lambda item: (
                item[1].get("profit_factor")
                if item[1].get("profit_factor") is not None
                else 999
            )
        )

        conclusions.append(
            "SELL group tốt nhất theo PF: "
            f"{best_sell[0]} "
            f"(PF={best_sell[1].get('profit_factor')})."
        )

        conclusions.append(
            "SELL group yếu nhất theo PF: "
            f"{worst_sell[0]} "
            f"(PF={worst_sell[1].get('profit_factor')})."
        )

    # --------------------------------------------------------
    # SELL -8/-9 warning
    # --------------------------------------------------------

    sell_8_9 = score_groups.get("SELL_-8_-9")

    if sell_8_9:
        trades = sell_8_9.get("trades", 0)
        pf = sell_8_9.get("profit_factor")
        profit = sell_8_9.get("profit")

        if trades >= minimum_sample and pf is not None:
            if pf < 1:
                conclusions.append(
                    "CẢNH BÁO: nhóm SELL -8/-9 "
                    "có PF < 1 và cần được kiểm tra kỹ."
                )

                conclusions.append(
                    "SELL -8/-9 hiện có profit "
                    f"{profit}, với {trades} trades."
                )

    # --------------------------------------------------------
    # Fee impact
    # --------------------------------------------------------

    return conclusions


# ============================================================
# FEE ANALYSIS
# ============================================================

def analyze_fees(engine_result):
    summary = get_summary(engine_result)

    profit_before_fees = safe_float(
        summary.get("profit_before_fees")
    )

    total_fees = safe_float(
        summary.get("total_fees")
    )

    profit_after_fees = safe_float(
        summary.get("profit")
    )

    return {
        "profit_before_fees": round_value(
            profit_before_fees
        ),
        "total_fees": round_value(
            total_fees
        ),
        "profit_after_fees": round_value(
            profit_after_fees
        ),
        "fee_impact": round_value(
            -abs(total_fees)
        ),
    }


# ============================================================
# ENGINE DEBUG
# ============================================================

def analyze_debug(engine_result):
    debug = get_debug(engine_result)

    return {
        "signal_buy_count": safe_int(
            debug.get("signal_buy_count")
        ),
        "signal_sell_count": safe_int(
            debug.get("signal_sell_count")
        ),
        "signal_hold_count": safe_int(
            debug.get("signal_hold_count")
        ),
        "trade_allowed_false_count": safe_int(
            debug.get("trade_allowed_false_count")
        ),
        "analyzer_error_count": safe_int(
            debug.get("analyzer_error_count")
        ),
        "first_analyzer_error": debug.get(
            "first_analyzer_error"
        ),
    }


# ============================================================
# SUMMARY
# ============================================================

def analyze_summary(engine_result):
    summary = get_summary(engine_result)

    return {
        "initial_balance": safe_float(
            summary.get("initial_balance")
        ),
        "final_balance": safe_float(
            summary.get("final_balance")
        ),
        "profit": round_value(
            summary.get("profit")
        ),
        "return_pct": round_value(
            summary.get("return_pct")
        ),
        "total_trades": safe_int(
            summary.get("total_trades")
        ),
        "win_rate": round_value(
            summary.get("win_rate")
        ),
        "profit_factor": round_value(
            summary.get("profit_factor")
        ),
        "max_drawdown_pct": round_value(
            summary.get("max_drawdown_pct")
        ),
    }


# ============================================================
# GENERAL CONCLUSIONS
# ============================================================

def build_general_conclusions(
    summary,
    side_analysis,
    exit_analysis,
    regime_analysis,
    fee_analysis,
    score_analysis,
    score_group_analysis,
    debug,
):
    conclusions = []

    # --------------------------------------------------------
    # Profit Factor
    # --------------------------------------------------------

    pf = summary.get("profit_factor")

    if pf is not None:
        if pf < 1:
            conclusions.append(
                "PF < 1: chiến lược đang có lợi thế âm "
                "trên giai đoạn này."
            )
        elif pf > 1:
            conclusions.append(
                "PF > 1: chiến lược có lợi thế dương "
                "trên giai đoạn này."
            )

    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return_pct = safe_float(
        summary.get("return_pct")
    )

    if return_pct < 0:
        conclusions.append(
            "Return âm: chưa nên đưa Signal hiện tại "
            "sang Paper Trading."
        )

    # --------------------------------------------------------
    # Drawdown
    # --------------------------------------------------------

    max_dd = safe_float(
        summary.get("max_drawdown_pct")
    )

    if max_dd >= 10:
        conclusions.append(
            "Drawdown >= 10%: cần chú ý kiểm soát rủi ro."
        )

    # --------------------------------------------------------
    # BUY vs SELL
    # --------------------------------------------------------

    buy_pf = side_analysis.get("BUY", {}).get(
        "profit_factor"
    )

    sell_pf = side_analysis.get("SELL", {}).get(
        "profit_factor"
    )

    if (
        buy_pf is not None
        and sell_pf is not None
    ):
        if buy_pf > sell_pf:
            conclusions.append(
                "BUY đang có hiệu quả tốt hơn SELL."
            )
        elif sell_pf > buy_pf:
            conclusions.append(
                "SELL đang có hiệu quả tốt hơn BUY."
            )

    # --------------------------------------------------------
    # Exit
    # --------------------------------------------------------

    sl = exit_analysis.get("STOP_LOSS", {})
    tp = exit_analysis.get("TAKE_PROFIT", {})

    sl_trades = sl.get("trades", 0)
    tp_trades = tp.get("trades", 0)

    if sl_trades > tp_trades:
        conclusions.append(
            "Số lệnh STOP_LOSS nhiều hơn TAKE_PROFIT."
        )

    # --------------------------------------------------------
    # Regime
    # --------------------------------------------------------

    valid_regimes = {
        regime: stats
        for regime, stats in regime_analysis.items()
        if stats.get("trades", 0) >= 3
        and stats.get("profit_factor") is not None
    }

    if valid_regimes:
        best_regime = max(
            valid_regimes.items(),
            key=lambda item: item[1]["profit_factor"]
        )

        worst_regime = min(
            valid_regimes.items(),
            key=lambda item: item[1]["profit_factor"]
        )

        conclusions.append(
            "Regime tốt nhất: "
            f"{best_regime[0]}."
        )

        conclusions.append(
            "Regime yếu nhất: "
            f"{worst_regime[0]}."
        )

    # --------------------------------------------------------
    # Fees
    # --------------------------------------------------------

    profit_before = safe_float(
        fee_analysis.get("profit_before_fees")
    )

    fees = safe_float(
        fee_analysis.get("total_fees")
    )

    if fees > abs(profit_before):
        conclusions.append(
            "Chi phí giao dịch lớn hơn lợi nhuận "
            "trước phí: fee đang ảnh hưởng rất mạnh."
        )

    # --------------------------------------------------------
    # Score coverage
    # --------------------------------------------------------

    score_quality = score_analysis.get(
        "data_quality",
        {}
    )

    coverage = safe_float(
        score_quality.get("score_coverage_pct")
    )

    if coverage >= 100:
        conclusions.append(
            "Score coverage = 100%: toàn bộ trade "
            "đều có score."
        )
    elif coverage > 0:
        conclusions.append(
            f"Score coverage = {coverage}%."
        )
    else:
        conclusions.append(
            "Không có dữ liệu score để phân tích."
        )

    # --------------------------------------------------------
    # Score group
    # --------------------------------------------------------

    valid_group_count = sum(
        1
        for stats in score_group_analysis.values()
        if stats.get("trades", 0) >= 5
    )

    if valid_group_count > 0:
        conclusions.append(
            "Diagnostic v1.3: đã phân tích score "
            "theo nhóm có tối thiểu 5 trades."
        )

    # --------------------------------------------------------
    # Debug
    # --------------------------------------------------------

    analyzer_errors = debug.get(
        "analyzer_error_count",
        0
    )

    if analyzer_errors == 0:
        conclusions.append(
            "Analyzer error = 0: dữ liệu backtest "
            "không ghi nhận lỗi analyzer."
        )
    else:
        conclusions.append(
            f"CẢNH BÁO: có {analyzer_errors} "
            "analyzer errors."
        )

    return conclusions


# ============================================================
# MAIN DIAGNOSTIC
# ============================================================

def run_diagnostic(engine_result):
    trades = get_trades(engine_result)

    summary = analyze_summary(
        engine_result
    )

    side_analysis = analyze_side(
        trades
    )

    exit_analysis = analyze_exit(
        trades
    )

    regime_analysis = analyze_regime(
        trades
    )

    score_analysis = analyze_score(
        trades
    )

    score_group_analysis = analyze_score_groups(
        trades
    )

    fee_analysis = analyze_fees(
        engine_result
    )

    debug = analyze_debug(
        engine_result
    )

    score_group_conclusions = (
        build_score_group_conclusions(
            score_group_analysis
        )
    )

    general_conclusions = (
        build_general_conclusions(
            summary,
            side_analysis,
            exit_analysis,
            regime_analysis,
            fee_analysis,
            score_analysis,
            score_group_analysis,
            debug,
        )
    )

    conclusions = (
        general_conclusions
        + score_group_conclusions
    )

    return {
        "status": "ok",
        "version": VERSION,
        "strategy": STRATEGY,

        "data": {
            "total_trades": len(trades),
            "source_summary": bool(
                get_summary(engine_result)
            ),
            "source_trade_records": bool(
                trades
            ),
        },

        "summary": summary,

        "side_analysis": side_analysis,

        "exit_analysis": exit_analysis,

        "regime_analysis": regime_analysis,

        "score_analysis": score_analysis,

        "score_group_analysis": (
            score_group_analysis
        ),

        "fee_analysis": fee_analysis,

        "engine_debug": debug,

        "conclusion": conclusions,
    }


# ============================================================
# OPTIONAL TERMINAL DISPLAY
# ============================================================

def print_diagnostic(result):
    """
    Hiển thị nhanh Diagnostic v1.3 trên terminal.
    Không bắt buộc khi sử dụng qua FastAPI.
    """

    if not isinstance(result, dict):
        return

    print("=" * 70)
    print(
        f"Backtest Diagnostic {VERSION} | {STRATEGY}"
    )
    print("=" * 70)

    summary = result.get("summary", {})

    print(
        f"Trades       : {summary.get('total_trades')}"
    )

    print(
        f"Win rate     : {summary.get('win_rate')}%"
    )

    print(
        f"Profit       : {summary.get('profit')}"
    )

    print(
        f"Return       : {summary.get('return_pct')}%"
    )

    print(
        f"Profit Factor: {summary.get('profit_factor')}"
    )

    print(
        f"Max DD       : {summary.get('max_drawdown_pct')}%"
    )

    print()
    print("-" * 70)
    print("SCORE GROUP ANALYSIS")
    print("-" * 70)

    groups = result.get(
        "score_group_analysis",
        {}
    )

    for name, stats in groups.items():
        print(
            f"{name:15} "
            f"trades={stats.get('trades'):>3} "
            f"win={stats.get('win_rate'):>6}% "
            f"PF={stats.get('profit_factor')} "
            f"profit={stats.get('profit')}"
        )

    print()
    print("-" * 70)
    print("CONCLUSIONS")
    print("-" * 70)

    for conclusion in result.get(
        "conclusion",
        []
    ):
        print(f"- {conclusion}")

    print("=" * 70)
