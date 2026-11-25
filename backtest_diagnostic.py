import math


VERSION = "1.2.0"


# =========================================================
# SAFE CONVERSION
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


# =========================================================
# NATIVE
# =========================================================

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

    if isinstance(value, float):

        if not math.isfinite(value):

            return None

    return value


# =========================================================
# EMPTY STATISTICS
# =========================================================

def empty_stats():

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
        "profit_factor": 0.0
    }


# =========================================================
# CALCULATE STATISTICS
# =========================================================

def calculate_stats(trades):

    result = empty_stats()

    if not trades:

        return result

    wins = 0
    losses = 0

    gross_profit = 0.0
    gross_loss = 0.0

    for trade in trades:

        profit = safe_float(
            trade.get("profit"),
            0.0
        )

        if profit > 0:

            wins += 1

            gross_profit += profit

        else:

            losses += 1

            gross_loss += abs(profit)

    total = len(trades)

    profit = sum(
        safe_float(
            trade.get("profit"),
            0.0
        )
        for trade in trades
    )

    win_rate = (
        wins / total * 100
        if total > 0
        else 0.0
    )

    average_win = (
        gross_profit / wins
        if wins > 0
        else 0.0
    )

    average_loss = (
        -gross_loss / losses
        if losses > 0
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

    result = {

        "trades": total,

        "wins": wins,

        "losses": losses,

        "win_rate": round(
            win_rate,
            2
        ),

        "profit": round(
            profit,
            4
        ),

        "gross_profit": round(
            gross_profit,
            4
        ),

        "gross_loss": round(
            gross_loss,
            4
        ),

        "average_win": round(
            average_win,
            4
        ),

        "average_loss": round(
            average_loss,
            4
        ),

        "profit_factor": (
            round(
                profit_factor,
                4
            )
            if profit_factor is not None
            else None
        )
    }

    return result


# =========================================================
# NORMALIZE MARKET CONDITION
# =========================================================

def get_market_condition(trade):

    value = trade.get(
        "market_condition"
    )

    if value is None:

        value = trade.get(
            "market_regime"
        )

    if value is None:

        value = trade.get(
            "regime"
        )

    if value is None:

        value = trade.get(
            "condition"
        )

    if value is None:

        return "UNKNOWN"

    value = str(
        value
    ).upper().strip()

    if not value:

        return "UNKNOWN"

    return value


# =========================================================
# NORMALIZE SCORE
# =========================================================

def get_score(trade):

    value = trade.get(
        "score"
    )

    if value is None:

        return None

    try:

        return int(
            float(value)
        )

    except Exception:

        return None


# =========================================================
# SIDE ANALYSIS
# =========================================================

def analyze_side(trades):

    groups = {
        "BUY": [],
        "SELL": []
    }

    for trade in trades:

        signal = str(
            trade.get(
                "signal",
                ""
            )
        ).upper()

        if signal in groups:

            groups[signal].append(
                trade
            )

    return {

        "BUY": calculate_stats(
            groups["BUY"]
        ),

        "SELL": calculate_stats(
            groups["SELL"]
        )
    }


# =========================================================
# EXIT ANALYSIS
# =========================================================

def analyze_exits(trades):

    groups = {
        "STOP_LOSS": [],
        "TAKE_PROFIT": [],
        "END_OF_DATA": []
    }

    for trade in trades:

        reason = trade.get(
            "exit_reason"
        )

        if reason is None:

            reason = trade.get(
                "reason"
            )

        if reason is None:

            reason = "UNKNOWN"

        reason = str(
            reason
        ).upper()

        if reason not in groups:

            groups[reason] = []

        groups[reason].append(
            trade
        )

    return {
        reason: calculate_stats(
            group
        )
        for reason, group in groups.items()
    }


# =========================================================
# REGIME ANALYSIS
# =========================================================

def analyze_regimes(trades):

    groups = {}

    for trade in trades:

        regime = get_market_condition(
            trade
        )

        if regime not in groups:

            groups[regime] = []

        groups[regime].append(
            trade
        )

    result = {}

    for regime, group in groups.items():

        result[regime] = calculate_stats(
            group
        )

    return result


# =========================================================
# SCORE ANALYSIS
# =========================================================

def analyze_scores(trades):

    # -----------------------------------------------------
    # Tất cả score
    # -----------------------------------------------------

    score_groups = {}

    unknown_score_trades = []

    for trade in trades:

        score = get_score(
            trade
        )

        if score is None:

            unknown_score_trades.append(
                trade
            )

            continue

        if score not in score_groups:

            score_groups[score] = []

        score_groups[score].append(
            trade
        )

    # -----------------------------------------------------
    # Overall score analysis
    # -----------------------------------------------------

    overall = {}

    for score in sorted(
        score_groups.keys()
    ):

        overall[str(score)] = calculate_stats(
            score_groups[score]
        )

    # -----------------------------------------------------
    # BUY score analysis
    # -----------------------------------------------------

    buy_score_groups = {}

    for trade in trades:

        signal = str(
            trade.get(
                "signal",
                ""
            )
        ).upper()

        if signal != "BUY":

            continue

        score = get_score(
            trade
        )

        if score is None:

            continue

        if score not in buy_score_groups:

            buy_score_groups[score] = []

        buy_score_groups[score].append(
            trade
        )

    buy_analysis = {}

    for score in sorted(
        buy_score_groups.keys()
    ):

        buy_analysis[str(score)] = calculate_stats(
            buy_score_groups[score]
        )

    # -----------------------------------------------------
    # SELL score analysis
    # -----------------------------------------------------

    sell_score_groups = {}

    for trade in trades:

        signal = str(
            trade.get(
                "signal",
                ""
            )
        ).upper()

        if signal != "SELL":

            continue

        score = get_score(
            trade
        )

        if score is None:

            continue

        if score not in sell_score_groups:

            sell_score_groups[score] = []

        sell_score_groups[score].append(
            trade
        )

    sell_analysis = {}

    for score in sorted(
        sell_score_groups.keys(),
        reverse=True
    ):

        sell_analysis[str(score)] = calculate_stats(
            sell_score_groups[score]
        )

    # -----------------------------------------------------
    # Score + Regime
    # -----------------------------------------------------

    score_regime_groups = {}

    for trade in trades:

        score = get_score(
            trade
        )

        if score is None:

            continue

        regime = get_market_condition(
            trade
        )

        key = f"{regime}|{score}"

        if key not in score_regime_groups:

            score_regime_groups[key] = []

        score_regime_groups[key].append(
            trade
        )

    score_regime_analysis = {}

    for key in sorted(
        score_regime_groups.keys()
    ):

        score_regime_analysis[key] = calculate_stats(
            score_regime_groups[key]
        )

    # -----------------------------------------------------
    # Score data quality
    # -----------------------------------------------------

    known_scores = sum(
        len(group)
        for group in score_groups.values()
    )

    unknown_scores = len(
        unknown_score_trades
    )

    return {

        "overall": overall,

        "BUY": buy_analysis,

        "SELL": sell_analysis,

        "by_regime_and_score": score_regime_analysis,

        "data_quality": {

            "trades_with_score": known_scores,

            "trades_without_score": unknown_scores,

            "score_coverage_pct": round(
                (
                    known_scores /
                    len(trades) *
                    100
                )
                if len(trades) > 0
                else 0.0,
                2
            )
        }
    }


# =========================================================
# FEE ANALYSIS
# =========================================================

def analyze_fees(
    summary,
    trades
):

    profit_before_fees = safe_float(
        summary.get(
            "profit_before_fees"
        ),
        0.0
    )

    total_fees = safe_float(
        summary.get(
            "total_fees"
        ),
        0.0
    )

    profit_after_fees = safe_float(
        summary.get(
            "profit"
        ),
        0.0
    )

    return {

        "profit_before_fees": round(
            profit_before_fees,
            4
        ),

        "total_fees": round(
            total_fees,
            4
        ),

        "profit_after_fees": round(
            profit_after_fees,
            4
        ),

        "fee_impact": round(
            -total_fees,
            4
        )
    }


# =========================================================
# FIND BEST / WORST REGIME
# =========================================================

def find_best_worst_regime(
    regime_analysis
):

    valid = []

    for regime, stats in regime_analysis.items():

        if stats.get(
            "trades",
            0
        ) <= 0:

            continue

        pf = stats.get(
            "profit_factor"
        )

        profit = safe_float(
            stats.get(
                "profit"
            ),
            0.0
        )

        valid.append(
            (
                regime,
                pf,
                profit
            )
        )

    if not valid:

        return None, None

    def score_item(item):

        regime, pf, profit = item

        if pf is None:

            pf_value = 999999

        else:

            pf_value = safe_float(
                pf,
                0.0
            )

        return (
            pf_value,
            profit
        )

    best = max(
        valid,
        key=score_item
    )

    worst = min(
        valid,
        key=score_item
    )

    return best[0], worst[0]


# =========================================================
# FIND BEST / WORST SCORE
# =========================================================

def find_score_extremes(
    score_analysis,
    minimum_trades=3
):

    valid = []

    for score_text, stats in score_analysis.items():

        trades = safe_int(
            stats.get(
                "trades"
            ),
            0
        )

        if trades < minimum_trades:

            continue

        pf = stats.get(
            "profit_factor"
        )

        profit = safe_float(
            stats.get(
                "profit"
            ),
            0.0
        )

        if pf is None:

            pf_value = 999999.0

        else:

            pf_value = safe_float(
                pf,
                0.0
            )

        valid.append(
            (
                score_text,
                pf_value,
                profit,
                trades
            )
        )

    if not valid:

        return None, None

    best = max(
        valid,
        key=lambda x: (
            x[1],
            x[2]
        )
    )

    worst = min(
        valid,
        key=lambda x: (
            x[1],
            x[2]
        )
    )

    return best, worst


# =========================================================
# CONCLUSION
# =========================================================

def build_conclusion(
    summary,
    side_analysis,
    exit_analysis,
    regime_analysis,
    score_analysis,
    fee_analysis
):

    conclusions = []

    # -----------------------------------------------------
    # PF
    # -----------------------------------------------------

    pf = summary.get(
        "profit_factor"
    )

    if pf is not None:

        if safe_float(
            pf,
            0.0
        ) < 1:

            conclusions.append(
                "PF < 1: chiến lược đang có lợi thế âm trên giai đoạn này."
            )

        else:

            conclusions.append(
                "PF >= 1: chiến lược có lợi thế dương trước khi xét các yếu tố khác."
            )

    # -----------------------------------------------------
    # Return
    # -----------------------------------------------------

    return_pct = safe_float(
        summary.get(
            "return_pct"
        ),
        0.0
    )

    if return_pct < 0:

        conclusions.append(
            "Return âm: chưa nên đưa Signal hiện tại sang Paper Trading."
        )

    else:

        conclusions.append(
            "Return dương trên giai đoạn backtest này."
        )

    # -----------------------------------------------------
    # Drawdown
    # -----------------------------------------------------

    max_dd = safe_float(
        summary.get(
            "max_drawdown_pct"
        ),
        0.0
    )

    if max_dd >= 10:

        conclusions.append(
            "Drawdown >= 10%: cần chú ý kiểm soát rủi ro."
        )

    # -----------------------------------------------------
    # BUY vs SELL
    # -----------------------------------------------------

    buy = side_analysis.get(
        "BUY",
        empty_stats()
    )

    sell = side_analysis.get(
        "SELL",
        empty_stats()
    )

    buy_profit = safe_float(
        buy.get(
            "profit"
        ),
        0.0
    )

    sell_profit = safe_float(
        sell.get(
            "profit"
        ),
        0.0
    )

    if buy_profit > sell_profit:

        conclusions.append(
            "BUY đang có hiệu quả tốt hơn SELL."
        )

    elif sell_profit > buy_profit:

        conclusions.append(
            "SELL đang có hiệu quả tốt hơn BUY."
        )

    # -----------------------------------------------------
    # Exit
    # -----------------------------------------------------

    stop_stats = exit_analysis.get(
        "STOP_LOSS",
        empty_stats()
    )

    tp_stats = exit_analysis.get(
        "TAKE_PROFIT",
        empty_stats()
    )

    stop_trades = safe_int(
        stop_stats.get(
            "trades"
        ),
        0
    )

    tp_trades = safe_int(
        tp_stats.get(
            "trades"
        ),
        0
    )

    if stop_trades > tp_trades:

        conclusions.append(
            "Số lệnh STOP_LOSS nhiều hơn TAKE_PROFIT."
        )

    elif tp_trades > stop_trades:

        conclusions.append(
            "Số lệnh TAKE_PROFIT nhiều hơn STOP_LOSS."
        )

    # -----------------------------------------------------
    # Regime
    # -----------------------------------------------------

    best_regime, worst_regime = find_best_worst_regime(
        regime_analysis
    )

    if best_regime is not None:

        conclusions.append(
            f"Regime tốt nhất: {best_regime}."
        )

    if worst_regime is not None:

        conclusions.append(
            f"Regime yếu nhất: {worst_regime}."
        )

    # -----------------------------------------------------
    # Fee
    # -----------------------------------------------------

    before_fee = safe_float(
        fee_analysis.get(
            "profit_before_fees"
        ),
        0.0
    )

    fees = safe_float(
        fee_analysis.get(
            "total_fees"
        ),
        0.0
    )

    after_fee = safe_float(
        fee_analysis.get(
            "profit_after_fees"
        ),
        0.0
    )

    if fees > 0 and before_fee > 0:

        if fees > before_fee:

            conclusions.append(
                "Chi phí giao dịch lớn hơn lợi nhuận trước phí: fee đang ảnh hưởng rất mạnh."
            )

        elif after_fee < before_fee:

            conclusions.append(
                "Phí giao dịch làm giảm đáng kể lợi nhuận."
            )

    # -----------------------------------------------------
    # Score analysis
    # -----------------------------------------------------

    sell_scores = score_analysis.get(
        "SELL",
        {}
    )

    buy_scores = score_analysis.get(
        "BUY",
        {}
    )

    best_sell, worst_sell = find_score_extremes(
        sell_scores,
        minimum_trades=3
    )

    best_buy, worst_buy = find_score_extremes(
        buy_scores,
        minimum_trades=3
    )

    if best_sell is not None:

        conclusions.append(
            "Diagnostic score: đã tìm được nhóm SELL có đủ mẫu để đánh giá."
        )

    if best_buy is not None:

        conclusions.append(
            "Diagnostic score: đã tìm được nhóm BUY có đủ mẫu để đánh giá."
        )

    # -----------------------------------------------------
    # Score coverage
    # -----------------------------------------------------

    quality = score_analysis.get(
        "data_quality",
        {}
    )

    score_coverage = safe_float(
        quality.get(
            "score_coverage_pct"
        ),
        0.0
    )

    if score_coverage < 100:

        conclusions.append(
            f"Score coverage = {score_coverage:.2f}%: một số trade chưa có score."
        )

    else:

        conclusions.append(
            "Score coverage = 100%: toàn bộ trade đều có score."
        )

    return conclusions


# =========================================================
# MAIN DIAGNOSTIC
# =========================================================

def run_diagnostic(
    engine_result
):

    if not isinstance(
        engine_result,
        dict
    ):

        return {

            "status": "error",

            "version": VERSION,

            "message": (
                "engine_result phải là dict"
            )
        }

    summary = engine_result.get(
        "summary",
        {}
    )

    debug = engine_result.get(
        "debug",
        {}
    )

    trades = engine_result.get(
        "trades",
        []
    )

    if not isinstance(
        trades,
        list
    ):

        trades = []

    # =====================================================
    # ANALYSIS
    # =====================================================

    side_analysis = analyze_side(
        trades
    )

    exit_analysis = analyze_exits(
        trades
    )

    regime_analysis = analyze_regimes(
        trades
    )

    score_analysis = analyze_scores(
        trades
    )

    fee_analysis = analyze_fees(
        summary,
        trades
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    diagnostic_summary = {

        "initial_balance": summary.get(
            "initial_balance",
            0
        ),

        "final_balance": summary.get(
            "final_balance",
            0
        ),

        "profit": summary.get(
            "profit",
            0
        ),

        "return_pct": summary.get(
            "return_pct",
            0
        ),

        "total_trades": summary.get(
            "total_trades",
            len(trades)
        ),

        "win_rate": summary.get(
            "win_rate",
            0
        ),

        "profit_factor": summary.get(
            "profit_factor"
        ),

        "max_drawdown_pct": summary.get(
            "max_drawdown_pct",
            0
        )
    }

    # =====================================================
    # CONCLUSION
    # =====================================================

    conclusion = build_conclusion(
        diagnostic_summary,
        side_analysis,
        exit_analysis,
        regime_analysis,
        score_analysis,
        fee_analysis
    )

    # =====================================================
    # RESULT
    # =====================================================

    result = {

        "status": "ok",

        "version": VERSION,

        "data": {

            "total_trades": len(trades),

            "source_summary": bool(
                summary
            ),

            "source_trade_records": bool(
                trades
            )
        },

        "summary": diagnostic_summary,

        "side_analysis": side_analysis,

        "exit_analysis": exit_analysis,

        "regime_analysis": regime_analysis,

        "score_analysis": score_analysis,

        "fee_analysis": fee_analysis,

        "engine_debug": debug,

        "conclusion": conclusion
    }

    return native(
        result
    )


# =========================================================
# LOCAL TEST
# =========================================================

if __name__ == "__main__":

    print(
        "backtest_diagnostic.py"
    )

    print(
        "VERSION:",
        VERSION
    )

    print(
        "Diagnostic v1.2 = OK"
    )
