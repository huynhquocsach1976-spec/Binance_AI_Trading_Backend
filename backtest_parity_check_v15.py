import requests
import json
import math

from backtest_engine import run_backtest
from backtest_filtered_v15 import run_filtered_diagnostic_v15


# ============================================================
# CONFIG
# ============================================================

SYMBOL = "BTCUSDT"
KRAKEN_SYMBOL = "XBTUSD"

CANDLES_COUNT = 720

INITIAL_BALANCE = 1000.0
FEE_RATE = 0.0004
SLIPPAGE = 0.0001

KRAKEN_URL = "https://api.kraken.com/0/public/OHLC"


# ============================================================
# LOAD DATA
# ============================================================

def load_kraken_720():
    print("=" * 70)
    print("STEP 1 - LOAD KRAKEN DATA")
    print("=" * 70)

    params = {
        "pair": KRAKEN_SYMBOL,
        "interval": 60
    }

    response = requests.get(
        KRAKEN_URL,
        params=params,
        timeout=30
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

    if pair_key is None:
        raise RuntimeError(
            "Không tìm thấy dữ liệu OHLC từ Kraken."
        )

    rows = result[pair_key]

    if len(rows) < CANDLES_COUNT:
        raise RuntimeError(
            f"Kraken chỉ trả {len(rows)} candles, "
            f"cần {CANDLES_COUNT}."
        )

    rows = rows[-CANDLES_COUNT:]

    candles = []

    for row in rows:
        candles.append({
            "time": int(float(row[0])),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "vwap": float(row[5]),
            "volume": float(row[6]),
            "trades": int(row[7])
        })

    print(f"Symbol       : {SYMBOL}")
    print(f"Kraken pair  : {KRAKEN_SYMBOL}")
    print(f"Candles      : {len(candles)}")

    print()
    print("FIRST CANDLE")
    print(json.dumps(candles[0], indent=2))

    print()
    print("LAST CANDLE")
    print(json.dumps(candles[-1], indent=2))

    return candles


# ============================================================
# HELPERS
# ============================================================

def get_value(obj, *keys, default=None):
    """
    Lấy value từ dict với nhiều tên key có thể khác nhau.
    """

    if not isinstance(obj, dict):
        return default

    for key in keys:
        if key in obj:
            return obj[key]

    return default


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        result = float(value)

        if math.isnan(result):
            return default

        return result

    except Exception:
        return default


def print_section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ============================================================
# RUN ORIGINAL BACKTEST ENGINE
# ============================================================

def run_engine(candles):

    print_section(
        "STEP 2 - ORIGINAL backtest_engine.py"
    )

    result = run_backtest(
        candles,
        initial_balance=INITIAL_BALANCE,
        fee_rate=FEE_RATE,
        slippage=SLIPPAGE
    )

    print("Original engine result:")

    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
        default=str
    ))

    return result


# ============================================================
# RUN FILTERED V1.5 BASELINE
# ============================================================

def run_filtered(candles):

    print_section(
        "STEP 3 - FILTERED BACKTEST v1.5"
    )

    result = run_filtered_diagnostic_v15(
        candles,
        initial_balance=INITIAL_BALANCE,
        fee_rate=FEE_RATE,
        slippage=SLIPPAGE
    )

    print("Filtered v1.5 result:")

    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
        default=str
    ))

    return result


# ============================================================
# EXTRACT ORIGINAL ENGINE
# ============================================================

def extract_original(result):

    if not isinstance(result, dict):
        return {}

    # Một số version có thể trả summary trực tiếp
    if "summary" in result:
        data = result["summary"]

    elif "backtest" in result:
        data = result["backtest"]

    else:
        data = result

    trades = get_value(
        data,
        "trades",
        "total_trades",
        default=[]
    )

    if not isinstance(trades, list):
        trades = []

    return {
        "final_balance": safe_float(
            get_value(
                data,
                "final_balance",
                "ending_balance",
                default=None
            )
        ),

        "profit": safe_float(
            get_value(
                data,
                "profit",
                "net_profit",
                default=None
            )
        ),

        "return_pct": safe_float(
            get_value(
                data,
                "return_pct",
                "return",
                default=None
            )
        ),

        "trades": len(trades),

        "wins": safe_float(
            get_value(
                data,
                "wins",
                "winning_trades",
                default=0
            )
        ),

        "losses": safe_float(
            get_value(
                data,
                "losses",
                "losing_trades",
                default=0
            )
        ),

        "profit_factor": safe_float(
            get_value(
                data,
                "profit_factor",
                "pf",
                default=0
            )
        ),

        "max_drawdown_pct": safe_float(
            get_value(
                data,
                "max_drawdown_pct",
                "max_dd_pct",
                default=0
            )
        ),

        "fees": safe_float(
            get_value(
                data,
                "fees",
                "total_fees",
                default=0
            )
        ),

        "trade_list": trades
    }


# ============================================================
# EXTRACT FILTERED BASELINE
# ============================================================

def extract_filtered(result):

    if not isinstance(result, dict):
        return {}

    # run_filtered_diagnostic_v15()
    # thường trả:
    #
    # {
    #     "BASELINE": {...},
    #     "REMOVE_SELL_-8_-9": {...},
    #     ...
    # }

    if "results" in result:
        results = result["results"]
    else:
        results = result

    baseline = results.get("BASELINE")

    if baseline is None:
        raise RuntimeError(
            "Không tìm thấy BASELINE trong kết quả v1.5."
        )

    trades = get_value(
        baseline,
        "trades_detail",
        "trades",
        default=[]
    )

    if not isinstance(trades, list):
        trades = []

    return {
        "final_balance": safe_float(
            baseline.get("final_balance")
        ),

        "profit": safe_float(
            baseline.get("profit")
        ),

        "return_pct": safe_float(
            baseline.get("return_pct")
        ),

        "trades": int(
            safe_float(
                baseline.get("trades"),
                0
            )
        ),

        "wins": int(
            safe_float(
                baseline.get("wins"),
                0
            )
        ),

        "losses": int(
            safe_float(
                baseline.get("losses"),
                0
            )
        ),

        "profit_factor": safe_float(
            baseline.get("profit_factor"),
            0
        ),

        "max_drawdown_pct": safe_float(
            baseline.get("max_drawdown_pct"),
            0
        ),

        "fees": safe_float(
            baseline.get("fees"),
            0
        ),

        "trade_list": trades
    }


# ============================================================
# COMPARE NUMBERS
# ============================================================

def compare_number(name, a, b, tolerance=0.000001):

    difference = abs(a - b)

    if difference <= tolerance:
        status = "PASS"
    else:
        status = "FAIL"

    print(
        f"{name:<22} "
        f"ENGINE={a:<15.8f} "
        f"V1.5={b:<15.8f} "
        f"DIFF={difference:<15.8f} "
        f"{status}"
    )

    return difference <= tolerance


# ============================================================
# COMPARE TRADES
# ============================================================

def compare_trades(engine_trades, filtered_trades):

    print_section(
        "TRADE-BY-TRADE COMPARISON"
    )

    if not engine_trades:
        print("⚠️ Original engine không có trade list.")
        return False

    if not filtered_trades:
        print("⚠️ Filtered v1.5 không có trade list.")
        return False

    count = min(
        len(engine_trades),
        len(filtered_trades)
    )

    print(
        f"ENGINE trades : {len(engine_trades)}"
    )

    print(
        f"V1.5 trades   : {len(filtered_trades)}"
    )

    print(
        f"Compare first : {count}"
    )

    mismatch_count = 0

    for i in range(count):

        a = engine_trades[i]
        b = filtered_trades[i]

        a_entry_index = get_value(
            a,
            "entry_index",
            default=None
        )

        b_entry_index = get_value(
            b,
            "entry_index",
            default=None
        )

        a_exit_index = get_value(
            a,
            "exit_index",
            default=None
        )

        b_exit_index = get_value(
            b,
            "exit_index",
            default=None
        )

        a_signal = get_value(
            a,
            "signal",
            default=None
        )

        b_signal = get_value(
            b,
            "signal",
            default=None
        )

        same = (
            a_entry_index == b_entry_index
            and
            a_exit_index == b_exit_index
            and
            a_signal == b_signal
        )

        if not same:
            mismatch_count += 1

            print()
            print(f"❌ TRADE #{i + 1}")

            print("ENGINE:")
            print(json.dumps(
                a,
                indent=2,
                ensure_ascii=False,
                default=str
            ))

            print("V1.5:")
            print(json.dumps(
                b,
                indent=2,
                ensure_ascii=False,
                default=str
            ))

            if mismatch_count >= 5:
                print()
                print(
                    "Đã dừng hiển thị sau 5 mismatch đầu tiên."
                )
                break

    print()

    if (
        len(engine_trades) == len(filtered_trades)
        and mismatch_count == 0
    ):
        print("✅ TRADE PARITY: PASS")
        return True

    print("❌ TRADE PARITY: FAIL")

    return False


# ============================================================
# MAIN COMPARISON
# ============================================================

def main():

    print()
    print("#" * 70)
    print("# BACKTEST v1.5 PARITY CHECK")
    print("# Signal v1.6.1 KHÔNG THAY ĐỔI")
    print("#" * 70)

    print()
    print("Parameters:")
    print(f"Symbol          : {SYMBOL}")
    print(f"Candles         : {CANDLES_COUNT}")
    print(f"Initial balance : {INITIAL_BALANCE}")
    print(f"Fee rate        : {FEE_RATE}")
    print(f"Slippage        : {SLIPPAGE}")

    # --------------------------------------------------------
    # QUAN TRỌNG:
    # CHỈ LOAD KRAKEN MỘT LẦN
    # CẢ HAI ENGINE DÙNG CÙNG candles
    # --------------------------------------------------------

    candles = load_kraken_720()

    # --------------------------------------------------------
    # ORIGINAL
    # --------------------------------------------------------

    original_raw = run_engine(candles)

    # --------------------------------------------------------
    # FILTERED
    # --------------------------------------------------------

    filtered_raw = run_filtered(candles)

    # --------------------------------------------------------
    # EXTRACT
    # --------------------------------------------------------

    original = extract_original(
        original_raw
    )

    filtered = extract_filtered(
        filtered_raw
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print_section(
        "STEP 4 - PARITY SUMMARY"
    )

    print()

    print(
        f"{'Metric':<22}"
        f"{'ENGINE':<18}"
        f"{'V1.5 BASELINE':<18}"
        f"RESULT"
    )

    print("-" * 75)

    checks = []

    checks.append(
        compare_number(
            "Final Balance",
            original["final_balance"],
            filtered["final_balance"]
        )
    )

    checks.append(
        compare_number(
            "Profit",
            original["profit"],
            filtered["profit"]
        )
    )

    checks.append(
        compare_number(
            "Return %",
            original["return_pct"],
            filtered["return_pct"]
        )
    )

    checks.append(
        compare_number(
            "Trades",
            original["trades"],
            filtered["trades"],
            tolerance=0
        )
    )

    checks.append(
        compare_number(
            "Wins",
            original["wins"],
            filtered["wins"],
            tolerance=0
        )
    )

    checks.append(
        compare_number(
            "Losses",
            original["losses"],
            filtered["losses"],
            tolerance=0
        )
    )

    checks.append(
        compare_number(
            "Profit Factor",
            original["profit_factor"],
            filtered["profit_factor"]
        )
    )

    checks.append(
        compare_number(
            "Max Drawdown %",
            original["max_drawdown_pct"],
            filtered["max_drawdown_pct"]
        )
    )

    checks.append(
        compare_number(
            "Fees",
            original["fees"],
            filtered["fees"]
        )
    )

    # --------------------------------------------------------
    # TRADE COMPARISON
    # --------------------------------------------------------

    trade_parity = compare_trades(
        original["trade_list"],
        filtered["trade_list"]
    )

    checks.append(trade_parity)

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print_section(
        "FINAL RESULT"
    )

    passed = sum(
        1 for x in checks
        if x
    )

    total = len(checks)

    print(
        f"PASS: {passed}/{total}"
    )

    if passed == total:

        print()
        print(
            "✅ PARITY CHECK PASSED"
        )

        print()
        print(
            "backtest_filtered_v15.py BASELINE "
            "khớp với backtest_engine.py."
        )

        print(
            "Có thể tiếp tục kiểm tra các filter."
        )

    else:

        print()
        print(
            "❌ PARITY CHECK FAILED"
        )

        print()
        print(
            "KHÔNG được sửa Signal v1.6.1."
        )

        print(
            "KHÔNG được chuyển sang Paper Trading."
        )

        print()
        print(
            "Cần sửa sai lệch giữa "
            "backtest_filtered_v15.py "
            "và backtest_engine.py trước."
        )

    print()


if __name__ == "__main__":
    main()
