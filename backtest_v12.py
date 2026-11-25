import requests
import time

from backtest_engine import run_backtest


VERSION = "1.2.1"

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

PAIR_MAP = {
    "BTCUSDT": "XBTUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD",
}

# Kraken OHLC API thường giới hạn số nến trả về mỗi request.
# 1h = 3600 giây.
TIMEFRAME = "1h"
INTERVAL_MINUTES = 60
INTERVAL_SECONDS = 3600

# Giới hạn mỗi lần lấy dữ liệu.
KRAKEN_BATCH_LIMIT = 720


# ============================================================
# HELPER
# ============================================================

def _normalize_candle(row):
    """
    Kraken OHLC format:

    [
        time,
        open,
        high,
        low,
        close,
        vwap,
        volume,
        count
    ]

    Chuyển về format mà backtest_engine đang sử dụng.
    """

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
# GET KRAKEN OHLC
# ============================================================

def _request_kraken_ohlc(pair, since=None):
    """
    Gọi Kraken OHLC API.

    since:
        Unix timestamp.

    Returns:
        list candles
    """

    params = {
        "pair": pair,
        "interval": 60,
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

        # Kraken trả thêm key "last"
        if key == "last":
            continue

        if not isinstance(rows, list):
            continue

        for row in rows:
            if len(row) < 8:
                continue

            try:
                candles.append(
                    _normalize_candle(row)
                )
            except Exception:
                continue

    return candles


# ============================================================
# GET HISTORICAL CANDLES
# ============================================================

def get_kraken_candles(symbol, limit=720):
    """
    Lấy số lượng nến lịch sử yêu cầu.

    Ví dụ:

        limit=720
        limit=1440
        limit=2160
        limit=2880

    Kraken có giới hạn dữ liệu mỗi request.
    Vì vậy phải chia thành nhiều request.

    Returns:
        candles tăng dần theo timestamp.
    """

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        raise ValueError(
            f"Symbol không được hỗ trợ: {symbol}. "
            f"Chỉ hỗ trợ: {list(PAIR_MAP.keys())}"
        )

    if limit <= 0:
        raise ValueError("limit phải > 0")

    pair = PAIR_MAP[symbol]

    all_candles = {}

    # --------------------------------------------------------
    # LẦN 1
    # --------------------------------------------------------

    batch = _request_kraken_ohlc(pair)

    if not batch:
        raise RuntimeError(
            f"Kraken không trả dữ liệu cho {symbol}"
        )

    for candle in batch:
        all_candles[candle["time"]] = candle

    # --------------------------------------------------------
    # Kraken OHLC có giới hạn dữ liệu.
    #
    # Dùng timestamp của candle cũ nhất hiện có
    # để tiếp tục yêu cầu dữ liệu trước đó.
    # --------------------------------------------------------

    oldest_time = min(all_candles.keys())

    # Số vòng tối đa để tránh loop vô hạn.
    max_requests = max(
        10,
        (limit // KRAKEN_BATCH_LIMIT) + 10
    )

    request_count = 1

    while len(all_candles) < limit and request_count < max_requests:

        # Lùi lại trước candle cũ nhất.
        #
        # Trừ thêm 1 interval để tránh lấy lại
        # đúng candle cũ nhất.
        next_since = oldest_time - INTERVAL_SECONDS

        try:
            batch = _request_kraken_ohlc(
                pair,
                since=next_since,
            )
        except Exception as e:
            raise RuntimeError(
                f"Lỗi lấy lịch sử Kraken "
                f"{symbol}: {str(e)}"
            )

        if not batch:
            break

        previous_count = len(all_candles)

        for candle in batch:
            all_candles[candle["time"]] = candle

        # Tìm candle cũ nhất mới.
        new_oldest_time = min(all_candles.keys())

        # Nếu không tiến thêm được thì dừng.
        if (
            new_oldest_time >= oldest_time
            and len(all_candles) == previous_count
        ):
            break

        oldest_time = new_oldest_time

        request_count += 1

        # Tránh request quá nhanh.
        time.sleep(0.2)

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    candles = sorted(
        all_candles.values(),
        key=lambda x: x["time"]
    )

    # --------------------------------------------------------
    # LẤY ĐÚNG SỐ NẾN CUỐI
    # --------------------------------------------------------

    if len(candles) > limit:
        candles = candles[-limit:]

    return candles


# ============================================================
# RUN SINGLE SYMBOL BACKTEST
# ============================================================

def run_symbol_backtest(
    symbol,
    candles=720,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001,
):
    """
    Backtest một symbol.
    """

    symbol = symbol.upper()

    if candles not in [720, 1440, 2160, 2880]:
        raise ValueError(
            "candles phải là một trong: "
            "720, 1440, 2160, 2880"
        )

    data = get_kraken_candles(
        symbol,
        limit=candles,
    )

    actual_candles = len(data)

    if actual_candles < 100:
        raise RuntimeError(
            f"Dữ liệu quá ít: {actual_candles} candles"
        )

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
# MULTI SYMBOL + MULTI PERIOD
# ============================================================

def run_multi_backtest(
    symbols=None,
    periods=None,
    initial_balance=1000.0,
    fee_rate=0.0004,
    slippage=0.0001,
):
    """
    Chạy:

    BTCUSDT
    ETHUSDT
    SOLUSDT

    với:

    720
    1440
    2160
    2880
    """

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
                    f"{symbol} - {period} candles"
                )

                result = run_symbol_backtest(
                    symbol=symbol,
                    candles=period,
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
    """
    Tạo bảng summary ngắn gọn.
    """

    summary = []

    for item in results:

        if item.get("status") != "ok":
            summary.append({
                "symbol": item.get("symbol"),
                "requested_candles": item.get(
                    "requested_candles"
                ),
                "actual_candles": item.get(
                    "actual_candles"
                ),
                "status": "ERROR",
                "message": item.get("message"),
            })
            continue

        result = item.get("result", {})

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
            "symbol": item.get("symbol"),

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
                account.get("total_return_percent"),

            "trades":
                trades.get("total"),

            "wins":
                trades.get("wins"),

            "losses":
                trades.get("losses"),

            "win_rate":
                trades.get("win_rate"),

            "profit_factor":
                performance.get("profit_factor"),

            "max_drawdown":
                risk.get("max_drawdown"),

            "max_drawdown_percent":
                risk.get("max_drawdown_percent"),

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
    print("Binance AI Trading Pro")
    print(f"Backtest v{VERSION}")
    print("Strategy: Signal v1.6.1")
    print("Source: Kraken")
    print("=" * 70)

    # Test riêng BTC 1440 trước.
    result = run_symbol_backtest(
        symbol="BTCUSDT",
        candles=1440,
        initial_balance=1000.0,
        fee_rate=0.0004,
        slippage=0.0001,
    )

    print()
    print("RESULT")
    print("=" * 70)

    print(
        f"Requested candles : "
        f"{result['requested_candles']}"
    )

    print(
        f"Actual candles    : "
        f"{result['actual_candles']}"
    )

    print(
        f"Final balance     : "
        f"{result['result']['account']['final_balance']}"
    )

    print(
        f"Total profit      : "
        f"{result['result']['account']['total_profit']}"
    )

    print(
        f"Return %          : "
        f"{result['result']['account']['total_return_percent']}"
    )

    print(
        f"Trades            : "
        f"{result['result']['trades']['total']}"
    )

    print(
        f"Win rate          : "
        f"{result['result']['trades']['win_rate']}"
    )

    print(
        f"Profit factor     : "
        f"{result['result']['performance']['profit_factor']}"
    )

    print(
        f"Max DD %          : "
        f"{result['result']['risk']['max_drawdown_percent']}"
    )

    print("=" * 70)
