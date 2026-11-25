# ============================================================
# Binance AI Trading Pro
# Backtest v1.2.2
#
# Strategy: Signal v1.6.1
# Data source: Kraken
#
# Compatible with:
#   candles=
#   candle_count=
#
# KHÔNG sửa ai_analyzer.py
# KHÔNG sửa backtest_engine.py
# ============================================================

import requests
import time

from backtest_engine import run_backtest


VERSION = "1.2.2"

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

PAIR_MAP = {
    "BTCUSDT": "XBTUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD",
}

TIMEFRAME = "1h"
INTERVAL = 60
INTERVAL_SECONDS = 3600


# ============================================================
# NORMALIZE KRAKEN CANDLE
# ============================================================

def normalize_candle(row):

    return {
        "time": int(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "vwap": float(row[5]),
        "volume": float(row[6]),
        "trades": int(row[7]),
    }


# ============================================================
# REQUEST KRAKEN
# ============================================================

def request_kraken(pair, since=None):

    params = {
        "pair": pair,
        "interval": INTERVAL,
    }

    if since is not None:
        params["since"] = int(since)

    response = requests.get(
        KRAKEN_OHLC_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("error"):
        raise RuntimeError(
            f"Kraken API error: {data['error']}"
        )

    result = data.get("result", {})

    candles = []

    for key, rows in result.items():

        if key == "last":
            continue

        if not isinstance(rows, list):
            continue

        for row in rows:

            if len(row) < 8:
                continue

            try:
                candles.append(
                    normalize_candle(row)
                )
            except Exception:
                continue

    return candles


# ============================================================
# GET HISTORICAL CANDLES
# ============================================================

def get_kraken_candles(symbol, limit=720):

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        raise ValueError(
            f"Symbol không được hỗ trợ: {symbol}"
        )

    if limit <= 0:
        raise ValueError(
            "limit phải lớn hơn 0"
        )

    pair = PAIR_MAP[symbol]

    candles_by_time = {}

    # --------------------------------------------------------
    # REQUEST 1
    # --------------------------------------------------------

    batch = request_kraken(pair)

    if not batch:
        raise RuntimeError(
            f"Kraken không trả dữ liệu cho {symbol}"
        )

    for candle in batch:
        candles_by_time[candle["time"]] = candle

    # --------------------------------------------------------
    # PAGINATION
    # --------------------------------------------------------

    oldest_time = min(candles_by_time.keys())

    max_requests = 30

    request_number = 1

    while (
        len(candles_by_time) < limit
        and request_number < max_requests
    ):

        # Lùi về trước dữ liệu hiện tại
        since = oldest_time - (
            INTERVAL_SECONDS * 720
        )

        batch = request_kraken(
            pair,
            since=since,
        )

        if not batch:
            break

        old_count = len(candles_by_time)
        old_oldest = oldest_time

        for candle in batch:
            candles_by_time[
                candle["time"]
            ] = candle

        oldest_time = min(
            candles_by_time.keys()
        )

        new_count = len(candles_by_time)

        # Không lấy thêm được dữ liệu
        if (
            new_count == old_count
            and oldest_time == old_oldest
        ):
            break

        request_number += 1

        time.sleep(0.25)

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    candles = sorted(
        candles_by_time.values(),
        key=lambda x: x["time"]
    )

    # --------------------------------------------------------
    # CHỈ LẤY limit NẾN CUỐI
    # --------------------------------------------------------

    if len(candles) > limit:
        candles = candles[-limit:]

    return candles


# ============================================================
# SINGLE SYMBOL BACKTEST
# ============================================================

def run_symbol_backtest(
    symbol,
    candles=720,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001,
    candle_count=None,
):
    """
    Backtest một symbol.

    Hỗ trợ cả:

        candles=1440

    và:

        candle_count=1440

    để tương thích main.py cũ.
    """

    # --------------------------------------------------------
    # candle_count được ưu tiên nếu được truyền vào
    # --------------------------------------------------------

    if candle_count is not None:
        candles = candle_count

    symbol = symbol.upper()

    allowed = [
        720,
        1440,
        2160,
        2880,
    ]

    if candles not in allowed:
        raise ValueError(
            f"candles phải là một trong: {allowed}"
        )

    # --------------------------------------------------------
    # GET DATA
    # --------------------------------------------------------

    data = get_kraken_candles(
        symbol,
        limit=candles,
    )

    actual_candles = len(data)

    # --------------------------------------------------------
    # KIỂM TRA DỮ LIỆU
    # --------------------------------------------------------

    if actual_candles < 100:
        raise RuntimeError(
            f"Dữ liệu quá ít: "
            f"{actual_candles} candles"
        )

    # --------------------------------------------------------
    # RUN BACKTEST
    # --------------------------------------------------------

    result = run_backtest(
        data,
        initial_balance=initial_balance,
        fee_rate=fee_rate,
        slippage=slippage,
    )

    return {
        "status": "ok",
        "version": VERSION,
        "symbol": symbol,
        "timeframe": TIMEFRAME,

        "requested_candles": candles,
        "actual_candles": actual_candles,

        "source": "Kraken",

        "result": result,
    }


# ============================================================
# MULTI SYMBOL
# ============================================================

def run_multi_backtest(
    symbols=None,
    periods=None,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001,
):

    if symbols is None:
        symbols = [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
        ]

    if periods is None:
        periods = [
            720,
            1440,
            2160,
            2880,
        ]

    results = []

    for symbol in symbols:

        for period in periods:

            try:

                print(
                    f"[BACKTEST v{VERSION}] "
                    f"{symbol} "
                    f"{period} candles"
                )

                result = run_symbol_backtest(
                    symbol=symbol,
                    candle_count=period,
                    initial_balance=initial_balance,
                    fee_rate=fee_rate,
                    slippage=slippage,
                )

                results.append(result)

            except Exception as e:

                results.append({
                    "status": "error",
                    "version": VERSION,
                    "symbol": symbol,
                    "timeframe": TIMEFRAME,
                    "requested_candles": period,
                    "actual_candles": 0,
                    "source": "Kraken",
                    "message": str(e),
                })

    return {
        "status": "ok",
        "version": VERSION,
        "strategy": "Signal v1.6.1",
        "source": "Kraken",
        "symbols": symbols,
        "periods": periods,
        "results": results,
    }


# ============================================================
# BUILD SUMMARY
# ============================================================

def build_summary(results):

    summary = []

    for item in results:

        if item.get("status") != "ok":

            summary.append({
                "symbol": item.get("symbol"),
                "requested_candles":
                    item.get("requested_candles"),
                "actual_candles":
                    item.get("actual_candles"),
                "status": "ERROR",
                "message": item.get("message"),
            })

            continue

        result = item.get(
            "result",
            {}
        )

        account = result.get(
            "account",
            {}
        )

        trades = result.get(
            "trades",
            {}
        )

        performance = result.get(
            "performance",
            {}
        )

        risk = result.get(
            "risk",
            {}
        )

        buy = result.get(
            "buy",
            {}
        )

        sell = result.get(
            "sell",
            {}
        )

        summary.append({

            "symbol":
                item.get("symbol"),

            "requested_candles":
                item.get("requested_candles"),

            "actual_candles":
                item.get("actual_candles"),

            "initial_balance":
                account.get("initial_balance"),

            "final_balance":
                account.get("final_balance"),

            "total_profit":
                account.get("total_profit"),

            "return_percent":
                account.get(
                    "total_return_percent"
                ),

            "trades":
                trades.get("total"),

            "wins":
                trades.get("wins"),

            "losses":
                trades.get("losses"),

            "win_rate":
                trades.get("win_rate"),

            "profit_factor":
                performance.get(
                    "profit_factor"
                ),

            "max_drawdown":
                risk.get("max_drawdown"),

            "max_drawdown_percent":
                risk.get(
                    "max_drawdown_percent"
                ),

            "buy_trades":
                buy.get("trades"),

            "buy_win_rate":
                buy.get("win_rate"),

            "sell_trades":
                sell.get("trades"),

            "sell_win_rate":
                sell.get("win_rate"),

            "status":
                "OK",
        })

    return summary


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "Binance AI Trading Pro "
        f"Backtest v{VERSION}"
    )
    print(
        "Strategy: Signal v1.6.1"
    )
    print(
        "Source: Kraken"
    )
    print("=" * 70)

    result = run_symbol_backtest(
        symbol="BTCUSDT",
        candle_count=1440,
        initial_balance=1000.0,
        fee_rate=0.0004,
        slippage=0.0001,
    )

    print()

    print(
        "Requested:",
        result["requested_candles"]
    )

    print(
        "Actual:",
        result["actual_candles"]
    )

    print(
        "Final balance:",
        result["result"]["account"][
            "final_balance"
        ]
    )

    print(
        "Profit:",
        result["result"]["account"][
            "total_profit"
        ]
    )

    print(
        "Return:",
        result["result"]["account"][
            "total_return_percent"
        ]
    )

    print(
        "Trades:",
        result["result"]["trades"]["total"]
    )

    print(
        "Win rate:",
        result["result"]["trades"]["win_rate"]
    )

    print(
        "Profit factor:",
        result["result"]["performance"][
            "profit_factor"
        ]
    )

    print(
        "Max DD:",
        result["result"]["risk"][
            "max_drawdown_percent"
        ]
    )

    print("=" * 70)
