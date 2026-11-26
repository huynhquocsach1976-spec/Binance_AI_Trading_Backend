import os
import sys
import json
import math
import traceback

from ai_analyzer import analyze_market
from backtest_engine import run_backtest
from backtest_v12 import PAIR_MAP

# Import filtered backtest v1.5
from backtest_filtered_v15 import run_filtered_diagnostic_v15


VERSION = "1.5.0-validation"


# ============================================================
# LOAD CSV
# ============================================================

def load_local_candles(symbol: str, candles_count: int):
    pair = PAIR_MAP.get(symbol.upper())

    if not pair:
        raise ValueError(
            f"Symbol {symbol} chưa có trong PAIR_MAP."
        )

    csv_path = os.path.join(
        "historical",
        f"{pair}_60.csv"
    )

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Không tìm thấy file:\n{csv_path}"
        )

    import csv

    rows = []

    with open(
        csv_path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError("CSV không có header.")

        headers = {
            str(h).strip().lower()
            for h in reader.fieldnames
        }

        required = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing = required - headers

        if missing:
            raise ValueError(
                f"CSV thiếu cột: {sorted(missing)}"
            )

        for row in reader:

            try:
                def get_value(*names, default=None):
                    for name in names:
                        if name in row and row[name] not in (None, ""):
                            return row[name]
                    return default

                candle = {
                    "time": get_value(
                        "time",
                        "timestamp",
                        "ts",
                        "date"
                    ),

                    "open": float(
                        get_value("open")
                    ),

                    "high": float(
                        get_value("high")
                    ),

                    "low": float(
                        get_value("low")
                    ),

                    "close": float(
                        get_value("close")
                    ),

                    "vwap": float(
                        get_value(
                            "vwap",
                            default=get_value("close")
                        )
                    ),

                    "volume": float(
                        get_value("volume")
                    ),

                    "trades": float(
                        get_value(
                            "trades",
                            "count",
                            default=0
                        )
                    ),
                }

                rows.append(candle)

            except Exception:
                continue

    if len(rows) < candles_count:
        raise ValueError(
            f"CSV chỉ có {len(rows)} candles, "
            f"cần {candles_count} candles."
        )

    return rows[-candles_count:]


# ============================================================
# SAFE NUMBER
# ============================================================

def num(value, default=0.0):

    try:
        if value is None:
            return default

        result = float(value)

        if math.isnan(result):
            return default

        if math.isinf(result):
            return default

        return result

    except Exception:
        return default


# ============================================================
# GET VALUE
# ============================================================

def get_value(obj, *keys, default=None):

    if isinstance(obj, dict):

        for key in keys:
            if key in obj:
                return obj[key]

        return default

    for key in keys:

        try:
            if hasattr(obj, key):
                return getattr(obj, key)
        except Exception:
            pass

    return default


# ============================================================
# NORMALIZE ENGINE RESULT
# ============================================================

def normalize_engine_result(result):

    if not isinstance(result, dict):
        return result

    return {
        "status": result.get("status"),

        "initial_balance": num(
            result.get("initial_balance")
        ),

        "final_balance": num(
            result.get("final_balance")
        ),

        "profit": num(
            result.get("profit")
        ),

        "return_pct": num(
            result.get("return_pct")
        ),

        "trades": int(
            num(result.get("trades"))
        ),

        "wins": int(
            num(result.get("wins"))
        ),

        "losses": int(
            num(result.get("losses"))
        ),

        "win_rate": num(
            result.get("win_rate")
        ),

        "profit_factor": num(
            result.get("profit_factor")
        ),

        "max_drawdown_pct": num(
            result.get("max_drawdown_pct")
        ),

        "gross_profit": num(
            result.get("gross_profit")
        ),

        "gross_loss": num(
            result.get("gross_loss")
        ),

        "fees": num(
            result.get("fees")
        ),

        "buy_trades": int(
            num(
                get_value(
                    result.get("buy_sell"),
                    "BUY",
                    default=0
                )
            )
        ),

        "sell_trades": int(
            num(
                get_value(
                    result.get("buy_sell"),
                    "SELL",
                    default=0
                )
            )
        ),
    }


# ============================================================
# EXTRACT FILTERED BASELINE
# ============================================================

def extract_filtered_baseline(result):

    if not isinstance(result, dict):
        return None

    # Có thể result chứa modes
    modes = result.get("modes")

    if isinstance(modes, dict):

        baseline = modes.get("BASELINE")

        if baseline is not None:
            return baseline

    # Một số version dùng list
    if isinstance(modes, list):

        for item in modes:

            if not isinstance(item, dict):
                continue

            if str(
                item.get("mode", "")
            ).upper() == "BASELINE":

                return item

    # Có thể nằm trực tiếp trong backtest
    if str(
        result.get("mode", "")
    ).upper() == "BASELINE":

        return result

    return None


# ============================================================
# FIND TRADE LIST
# ============================================================

def extract_trades(result):

    if not isinstance(result, dict):
        return []

    for key in (
        "trades_detail",
        "trades",
        "trade_details"
    ):

        value = result.get(key)

        if isinstance(value, list):
            return value

    return []


# ============================================================
# TRADE COMPARISON
# ============================================================

def compare_trade_lists(engine_trades, filtered_trades):

    print()
    print("=" * 80)
    print("TRADE-LEVEL VALIDATION")
    print("=" * 80)

    print(
        f"Engine trades   : {len(engine_trades)}"
    )

    print(
        f"Filtered trades : {len(filtered_trades)}"
    )

    common = min(
        len(engine_trades),
        len(filtered_trades)
    )

    differences = []

    fields = [
        "signal",
        "entry_index",
        "exit_index",
        "entry_price",
        "exit_price",
        "stop_loss",
        "take_profit",
        "reason",
        "exit_reason",
        "profit",
        "fees",
    ]

    for i in range(common):

        a = engine_trades[i]
        b = filtered_trades[i]

        if not isinstance(a, dict):
            continue

        if not isinstance(b, dict):
            continue

        for field in fields:

            av = a.get(field)
            bv = b.get(field)

            if isinstance(av, (int, float)) and isinstance(
                bv, (int, float)
            ):

                if not math.isclose(
                    float(av),
                    float(bv),
                    rel_tol=1e-7,
                    abs_tol=1e-7
                ):
                    differences.append({
                        "trade": i + 1,
                        "field": field,
                        "engine": av,
                        "filtered": bv
                    })

            else:

                if av != bv:

                    differences.append({
                        "trade": i + 1,
                        "field": field,
                        "engine": av,
                        "filtered": bv
                    })

            if len(differences) >= 30:
                break

        if len(differences) >= 30:
            break

    if not differences:

        print()
        print("OK: Không phát hiện sai lệch trade-level.")
        return True

    print()
    print(
        f"PHAT HIEN {len(differences)} sai lech "
        f"(hien thi toi da 30)."
    )

    for diff in differences:

        print()
        print(
            f"Trade #{diff['trade']} | "
            f"{diff['field']}"
        )

        print(
            f"  Engine   : {diff['engine']}"
        )

        print(
            f"  Filtered : {diff['filtered']}"
        )

    return False


# ============================================================
# SUMMARY COMPARISON
# ============================================================

def compare_summary(engine, filtered):

    print()
    print("=" * 80)
    print("SUMMARY VALIDATION")
    print("=" * 80)

    fields = [
        "initial_balance",
        "final_balance",
        "profit",
        "return_pct",
        "trades",
        "wins",
        "losses",
        "win_rate",
        "profit_factor",
        "max_drawdown_pct",
        "gross_profit",
        "gross_loss",
        "fees",
        "buy_trades",
        "sell_trades",
    ]

    all_ok = True

    for field in fields:

        a = engine.get(field)
        b = filtered.get(field)

        if isinstance(a, (int, float)) and isinstance(
            b, (int, float)
        ):

            ok = math.isclose(
                float(a),
                float(b),
                rel_tol=1e-6,
                abs_tol=1e-6
            )

        else:

            ok = a == b

        status = "OK" if ok else "DIFF"

        if not ok:
            all_ok = False

        print(
            f"{field:22} | "
            f"Engine={a} | "
            f"Filtered={b} | "
            f"{status}"
        )

    print()

    if all_ok:
        print("SUMMARY: PASS")
    else:
        print("SUMMARY: FAIL")

    return all_ok


# ============================================================
# MAIN VALIDATION
# ============================================================

def main():

    symbol = "BTCUSDT"
    candles_count = 2880

    initial_balance = 1000.0
    fee_rate = 0.0004
    slippage = 0.0001

    print()
    print("=" * 80)
    print("BACKTEST FILTERED v1.5 - VALIDATION")
    print("=" * 80)

    print()
    print(f"Version          : {VERSION}")
    print(f"Symbol           : {symbol}")
    print(f"Candles          : {candles_count}")
    print(f"Initial balance  : {initial_balance}")
    print(f"Fee rate         : {fee_rate}")
    print(f"Slippage         : {slippage}")

    print()
    print("Loading historical candles...")

    candles = load_local_candles(
        symbol,
        candles_count
    )

    print(
        f"Loaded candles  : {len(candles)}"
    )

    # ========================================================
    # 1. STANDARD ENGINE
    # ========================================================

    print()
    print("=" * 80)
    print("1. RUN STANDARD BACKTEST ENGINE")
    print("=" * 80)

    try:

        engine_result = run_backtest(
            candles=candles,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

    except TypeError:

        # Fallback nếu signature engine khác
        try:

            engine_result = run_backtest(
                candles,
                initial_balance,
                fee_rate,
                slippage,
            )

        except Exception as e:

            print()
            print("ERROR run_backtest:")
            print(str(e))
            traceback.print_exc()
            sys.exit(1)

    except Exception as e:

        print()
        print("ERROR run_backtest:")
        print(str(e))
        traceback.print_exc()
        sys.exit(1)

    engine_normalized = normalize_engine_result(
        engine_result
    )

    print()
    print(
        json.dumps(
            engine_normalized,
            indent=2,
            ensure_ascii=False
        )
    )

    engine_trades = extract_trades(
        engine_result
    )

    # ========================================================
    # 2. FILTERED v1.5
    # ========================================================

    print()
    print("=" * 80)
    print("2. RUN FILTERED BACKTEST v1.5")
    print("=" * 80)

    try:

        filtered_result = run_filtered_diagnostic_v15(
            candles=candles,
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage=slippage,
        )

    except TypeError:

        try:

            filtered_result = run_filtered_diagnostic_v15(
                candles,
                initial_balance,
                fee_rate,
                slippage,
            )

        except Exception as e:

            print()
            print(
                "ERROR run_filtered_diagnostic_v15:"
            )

            print(str(e))

            traceback.print_exc()

            sys.exit(1)

    except Exception as e:

        print()
        print(
            "ERROR run_filtered_diagnostic_v15:"
        )

        print(str(e))

        traceback.print_exc()

        sys.exit(1)

    baseline = extract_filtered_baseline(
        filtered_result
    )

    if baseline is None:

        print()
        print(
            "KHONG TIM THAY mode BASELINE "
            "trong ket qua v1.5."
        )

        print()
        print(
            "Keys:"
        )

        if isinstance(filtered_result, dict):
            print(
                list(filtered_result.keys())
            )

        sys.exit(1)

    filtered_normalized = normalize_engine_result(
        baseline
    )

    print()
    print(
        json.dumps(
            filtered_normalized,
            indent=2,
            ensure_ascii=False
        )
    )

    filtered_trades = extract_trades(
        baseline
    )

    # ========================================================
    # 3. SUMMARY
    # ========================================================

    summary_ok = compare_summary(
        engine_normalized,
        filtered_normalized
    )

    # ========================================================
    # 4. TRADE LEVEL
    # ========================================================

    trade_ok = compare_trade_lists(
        engine_trades,
        filtered_trades
    )

    # ========================================================
    # 5. FINAL
    # ========================================================

    print()
    print("=" * 80)
    print("FINAL VALIDATION RESULT")
    print("=" * 80)

    if summary_ok and trade_ok:

        print()
        print("PASS")
        print()
        print(
            "Filtered Backtest v1.5 BASELINE "
            "khop voi backtest_engine.py."
        )

        print()
        print(
            "Co the tiep tuc danh gia 4 filter modes."
        )

        exit_code = 0

    else:

        print()
        print("FAIL")
        print()
        print(
            "Filtered Backtest v1.5 BASELINE "
            "CHUA khop backtest_engine.py."
        )

        print()
        print(
            "KHONG nen sua Signal v1.6.1 luc nay."
        )

        print(
            "Can sua parity cua v1.5 truoc."
        )

        exit_code = 2

    # ========================================================
    # SAVE REPORT
    # ========================================================

    report = {
        "status": (
            "PASS"
            if summary_ok and trade_ok
            else "FAIL"
        ),

        "version": VERSION,

        "symbol": symbol,

        "candles": candles_count,

        "engine": engine_normalized,

        "filtered_baseline": filtered_normalized,

        "trade_count_engine": len(
            engine_trades
        ),

        "trade_count_filtered": len(
            filtered_trades
        ),

        "summary_match": summary_ok,

        "trade_level_match": trade_ok,
    }

    output_file = (
        "validation_v15_result.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print(
        f"Report saved: {output_file}"
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
