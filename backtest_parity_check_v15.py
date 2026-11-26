import requests
from typing import Any, Dict, List

from backtest_engine import run_backtest
from backtest_filtered_v15 import run_filtered_diagnostic_v15


VERSION = "1.5.0"

KRAKEN_URL = "https://api.kraken.com/0/public/OHLC"

PAIR_MAP = {
    "BTCUSDT": "XBTUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD",
}


# ============================================================
# LOAD KRAKEN 720 CANDLES
# ============================================================

def load_kraken_candles(symbol: str, candles: int = 720) -> List[Dict[str, Any]]:
    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        raise ValueError(
            f"Symbol không hỗ trợ: {symbol}. "
            f"Chỉ hỗ trợ: {', '.join(PAIR_MAP.keys())}"
        )

    if candles != 720:
        raise ValueError(
            "Parity Check v1.5 hiện kiểm tra chính xác 720 candles."
        )

    pair = PAIR_MAP[symbol]

    response = requests.get(
        KRAKEN_URL,
        params={
            "pair": pair,
            "interval": 60,
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("error"):
        raise RuntimeError(
            f"Kraken API error: {data['error']}"
        )

    result = data.get("result", {})

    pair_key = None

    for key in result.keys():
        if key != "last":
            pair_key = key
            break

    if not pair_key:
        raise RuntimeError(
            "Không tìm thấy dữ liệu OHLC từ Kraken."
        )

    rows = result[pair_key]

    if len(rows) < candles:
        raise RuntimeError(
            f"Kraken chỉ trả về {len(rows)} candles, "
            f"cần {candles} candles."
        )

    rows = rows[-candles:]

    output = []

    for row in rows:
        if len(row) < 8:
            continue

        output.append(
            {
                "time": int(float(row[0])),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "vwap": float(row[5]),
                "volume": float(row[6]),
                "trades": int(float(row[7])),
            }
        )

    if len(output) != candles:
        raise RuntimeError(
            f"Sau khi chuẩn hóa chỉ còn {len(output)} candles, "
            f"cần {candles}."
        )

    return output


# ============================================================
# HELPER
# ============================================================

def to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def find_value(obj, possible_keys):
    """
    Tìm key trong dictionary.
    Hỗ trợ nested dictionary.
    """

    if isinstance(obj, dict):

        for key in possible_keys:
            if key in obj:
                return obj[key]

        for value in obj.values():
            found = find_value(value, possible_keys)

            if found is not None:
                return found

    elif isinstance(obj, list):

        for item in obj:
            found = find_value(item, possible_keys)

            if found is not None:
                return found

    return None


def normalize_result(result):
    """
    Chuẩn hóa output của các backtest khác nhau
    thành một summary chung.
    """

    if result is None:
        return {}

    if not isinstance(result, dict):
        return {}

    return {
        "final_balance": to_float(
            find_value(
                result,
                [
                    "final_balance",
                    "final_balance_hypothetical",
                ],
            )
        ),
        "profit": to_float(
            find_value(
                result,
                [
                    "profit",
                ],
            )
        ),
        "return_pct": to_float(
            find_value(
                result,
                [
                    "return_pct",
                ],
            )
        ),
        "trades": find_value(
            result,
            [
                "trades",
            ],
        ),
        "wins": find_value(
            result,
            [
                "wins",
            ],
        ),
        "losses": find_value(
            result,
            [
                "losses",
            ],
        ),
        "win_rate": to_float(
            find_value(
                result,
                [
                    "win_rate",
                ],
            )
        ),
        "profit_factor": to_float(
            find_value(
                result,
                [
                    "profit_factor",
                    "pf",
                ],
            )
        ),
        "max_drawdown_pct": to_float(
            find_value(
                result,
                [
                    "max_drawdown_pct",
                ],
            )
        ),
        "fees": to_float(
            find_value(
                result,
                [
                    "fees",
                    "total_fees",
                ],
            )
        ),
    }


# ============================================================
# EXTRACT BASELINE FROM FILTERED V15
# ============================================================

def extract_filtered_baseline(result):
    """
    backtest_filtered_v15 thường trả:

    {
        "status": "ok",
        "results": {
            "BASELINE": {...},
            ...
        }
    }

    Hàm này lấy riêng BASELINE.
    """

    if not isinstance(result, dict):
        return {}

    results = result.get("results")

    if isinstance(results, dict):

        baseline = results.get("BASELINE")

        if isinstance(baseline, dict):
            return baseline

    # Trường hợp khác nếu BASELINE nằm sâu hơn
    baseline = find_value(
        result,
        ["BASELINE"]
    )

    if isinstance(baseline, dict):
        return baseline

    return {}


# ============================================================
# COMPARE NUMBERS
# ============================================================

def compare_number(
    name: str,
    a,
    b,
    tolerance: float = 1e-8,
):
    a_num = to_float(a)
    b_num = to_float(b)

    if a_num is None or b_num is None:
        return {
            "name": name,
            "a": a,
            "b": b,
            "difference": None,
            "match": False,
            "reason": "Không đọc được giá trị số",
        }

    difference = abs(a_num - b_num)

    return {
        "name": name,
        "a": a_num,
        "b": b_num,
        "difference": difference,
        "match": difference <= tolerance,
    }


# ============================================================
# RUN PARITY
# ============================================================

def run_parity_check(
    candles: List[Dict[str, Any]],
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001,
) -> Dict[str, Any]:

    if not candles:
        raise ValueError("Candles rỗng.")

    # ========================================================
    # QUAN TRỌNG:
    # Hai backtest nhận CHÍNH XÁC cùng object candles.
    # ========================================================

    engine_result = run_backtest(
        candles,
        initial_balance=initial_balance,
        fee_rate=fee_rate,
        slippage=slippage,
    )

    filtered_result = run_filtered_diagnostic_v15(
        candles,
        initial_balance=initial_balance,
        fee_rate=fee_rate,
        slippage=slippage,
    )

    filtered_baseline = extract_filtered_baseline(
        filtered_result
    )

    engine_summary = normalize_result(
        engine_result
    )

    filtered_summary = normalize_result(
        filtered_baseline
    )

    # ========================================================
    # SO SÁNH
    # ========================================================

    comparisons = []

    fields = [
        "final_balance",
        "profit",
        "return_pct",
        "trades",
        "wins",
        "losses",
        "win_rate",
        "profit_factor",
        "max_drawdown_pct",
        "fees",
    ]

    for field in fields:

        tolerance = 1e-8

        if field in [
            "trades",
            "wins",
            "losses",
        ]:
            tolerance = 0.0

        comparisons.append(
            compare_number(
                field,
                engine_summary.get(field),
                filtered_summary.get(field),
                tolerance=tolerance,
            )
        )

    all_match = all(
        item["match"]
        for item in comparisons
    )

    mismatches = [
        item
        for item in comparisons
        if not item["match"]
    ]

    # ========================================================
    # TRADE COUNT
    # ========================================================

    engine_trades = find_value(
        engine_result,
        ["trades_detail", "trades"]
    )

    filtered_trades = find_value(
        filtered_baseline,
        ["trades_detail", "trades"]
    )

    engine_trade_count = (
        len(engine_trades)
        if isinstance(engine_trades, list)
        else None
    )

    filtered_trade_count = (
        len(filtered_trades)
        if isinstance(filtered_trades, list)
        else None
    )

    # ========================================================
    # RESULT
    # ========================================================

    return {
        "status": "ok",
        "version": VERSION,
        "method": (
            "Same frozen candle list -> "
            "backtest_engine.py vs "
            "backtest_filtered_v15.py BASELINE"
        ),
        "candles": len(candles),
        "parameters": {
            "initial_balance": initial_balance,
            "fee_rate": fee_rate,
            "slippage": slippage,
        },
        "engine": {
            "summary": engine_summary,
            "trade_count_from_detail": engine_trade_count,
        },
        "filtered_v15_baseline": {
            "summary": filtered_summary,
            "trade_count_from_detail": filtered_trade_count,
        },
        "comparison": comparisons,
        "parity": {
            "status": "PASS" if all_match else "FAIL",
            "all_core_metrics_match": all_match,
            "mismatch_count": len(mismatches),
        },
        "mismatches": mismatches,
    }


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("BACKTEST PARITY CHECK v1.5")
    print("=" * 70)

    candles = load_kraken_candles(
        "BTCUSDT",
        720,
    )

    print(f"Loaded candles: {len(candles)}")

    result = run_parity_check(
        candles,
        initial_balance=1000.0,
        fee_rate=0.0004,
        slippage=0.0001,
    )

    print()
    print("=" * 70)
    print("PARITY RESULT")
    print("=" * 70)

    print(
        result["parity"]
    )

    print()
    print("ENGINE:")
    print(
        result["engine"]["summary"]
    )

    print()
    print("FILTERED V15 BASELINE:")
    print(
        result["filtered_v15_baseline"]["summary"]
    )

    print()
    print("COMPARISON:")

    for item in result["comparison"]:
        print(
            f"{item['name']}: "
            f"{item['match']} | "
            f"A={item['a']} | "
            f"B={item['b']} | "
            f"Diff={item['difference']}"
        )

    print()

    if result["parity"]["status"] == "PASS":
        print(">>> PARITY CHECK: PASS")
    else:
        print(">>> PARITY CHECK: FAIL")
        print()
        print("MISMATCHES:")

        for item in result["mismatches"]:
            print(item)
