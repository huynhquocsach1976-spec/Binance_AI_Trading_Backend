import requests
from backtest_engine import run_backtest


# ============================================================
# BACKTEST v1.2
# Multi-Symbol + nhiều giai đoạn lịch sử
# Giữ nguyên Signal v1.6.1
# ============================================================

VERSION = "1.2.0"

KRAKEN_URL = "https://api.kraken.com/0/public/OHLC"

PAIR_MAP = {
    "BTCUSDT": "XBTUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD"
}


# ============================================================
# LẤY DỮ LIỆU KRAKEN
# ============================================================

def get_kraken_candles(symbol: str, limit: int = 720):
    """
    Lấy dữ liệu nến 1H từ Kraken.

    Kraken có giới hạn số lượng candle trả về mỗi request,
    nên v1.2 lấy nhiều lần nếu cần dữ liệu lớn hơn.
    """

    symbol = symbol.upper()

    if symbol not in PAIR_MAP:
        raise ValueError(
            f"Symbol chưa được hỗ trợ: {symbol}"
        )

    pair = PAIR_MAP[symbol]

    all_candles = []

    # Kraken OHLC thường trả khoảng 720 candle gần nhất.
    # Ta lấy nhiều batch để cố gắng thu thập dữ liệu lịch sử.
    since = None

    max_requests = max(1, (limit // 700) + 3)

    for _ in range(max_requests):

        params = {
            "pair": pair,
            "interval": 60
        }

        if since is not None:
            params["since"] = since

        response = requests.get(
            KRAKEN_URL,
            params=params,
            timeout=20
        )

        if response.status_code != 200:
            raise Exception(
                f"Kraken HTTP {response.status_code}: "
                f"{response.text}"
            )

        data = response.json()

        if data.get("error"):
            raise Exception(
                f"Kraken error: {data['error']}"
            )

        result = data.get("result", {})

        candles_raw = None

        for key, value in result.items():
            if key != "last":
                candles_raw = value
                break

        if not candles_raw:
            break

        for candle in candles_raw:

            item = {
                "time": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "vwap": float(candle[5]),
                "volume": float(candle[6]),
                "trades": int(candle[7])
            }

            all_candles.append(item)

        # Không cần lấy thêm nếu đã đủ
        if len(all_candles) >= limit:
            break

        new_since = result.get("last")

        if new_since is None:
            break

        try:
            new_since = int(new_since)
        except Exception:
            break

        # Nếu since không thay đổi thì dừng
        if since == new_since:
            break

        since = new_since

    # Loại candle trùng
    unique = {}

    for candle in all_candles:
        unique[candle["time"]] = candle

    candles = list(unique.values())

    # Sắp xếp theo thời gian tăng dần
    candles.sort(
        key=lambda x: x["time"]
    )

    # Chỉ lấy số lượng cần thiết
    if len(candles) > limit:
        candles = candles[-limit:]

    return candles


# ============================================================
# CHẠY BACKTEST CHO 1 SYMBOL
# ============================================================

def run_symbol_backtest(
    symbol: str,
    candle_count: int = 720,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001
):

    candles = get_kraken_candles(
        symbol,
        candle_count
    )

    if len(candles) < 100:

        return {
            "status": "error",
            "symbol": symbol,
            "requested_candles": candle_count,
            "actual_candles": len(candles),
            "message": (
                "Không đủ dữ liệu nến để backtest"
            )
        }

    result = run_backtest(
        candles,
        initial_balance=initial_balance,
        fee_rate=fee_rate,
        slippage=slippage
    )

    return {
        "status": "ok",
        "version": VERSION,
        "symbol": symbol,
        "timeframe": "1h",
        "requested_candles": candle_count,
        "actual_candles": len(candles),
        "source": "Kraken",
        "result": result
    }


# ============================================================
# CHẠY MULTI-SYMBOL + MULTI-PERIOD
# ============================================================

def run_multi_backtest(
    symbols=None,
    periods=None,
    initial_balance: float = 1000.0,
    fee_rate: float = 0.0004,
    slippage: float = 0.0001
):

    if symbols is None:
        symbols = [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT"
        ]

    if periods is None:
        periods = [
            720,
            1440,
            2160,
            2880
        ]

    results = []

    for symbol in symbols:

        symbol = symbol.upper()

        for candle_count in periods:

            print(
                f"[BACKTEST v1.2] "
                f"{symbol} - {candle_count} candles"
            )

            try:

                result = run_symbol_backtest(
                    symbol=symbol,
                    candle_count=candle_count,
                    initial_balance=initial_balance,
                    fee_rate=fee_rate,
                    slippage=slippage
                )

                results.append(result)

            except Exception as e:

                results.append({
                    "status": "error",
                    "version": VERSION,
                    "symbol": symbol,
                    "requested_candles": candle_count,
                    "message": str(e)
                })

    return {
        "status": "ok",
        "version": VERSION,
        "strategy": "Signal v1.6.1",
        "timeframe": "1h",
        "symbols": symbols,
        "periods": periods,
        "settings": {
            "initial_balance": initial_balance,
            "fee_rate_per_side": fee_rate,
            "slippage": slippage
        },
        "results": results
    }


# ============================================================
# TẠO BẢNG TỔNG HỢP
# ============================================================

def build_summary(results):

    summary = []

    for item in results:

        if item.get("status") != "ok":
            summary.append({
                "symbol": item.get("symbol"),
                "candles": item.get(
                    "requested_candles"
                ),
                "actual_candles": item.get(
                    "actual_candles",
                    0
                ),
                "status": "ERROR"
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

            "symbol": item.get(
                "symbol"
            ),

            "candles": item.get(
                "requested_candles"
            ),

            "actual_candles": item.get(
                "actual_candles"
            ),

            "final_balance": account.get(
                "final_balance"
            ),

            "profit": account.get(
                "total_profit"
            ),

            "return_percent": account.get(
                "total_return_percent"
            ),

            "trades": trades.get(
                "total"
            ),

            "wins": trades.get(
                "wins"
            ),

            "losses": trades.get(
                "losses"
            ),

            "win_rate": trades.get(
                "win_rate"
            ),

            "profit_factor": performance.get(
                "profit_factor"
            ),

            "max_drawdown": risk.get(
                "max_drawdown"
            ),

            "max_drawdown_percent": risk.get(
                "max_drawdown_percent"
            ),

            "buy_trades": buy.get(
                "trades"
            ),

            "buy_win_rate": buy.get(
                "win_rate"
            ),

            "sell_trades": sell.get(
                "trades"
            ),

            "sell_win_rate": sell.get(
                "win_rate"
            ),

            "status": "OK"
        })

    return summary


# ============================================================
# CHẠY TRỰC TIẾP FILE
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("BINANCE AI TRADING PRO")
    print("BACKTEST v1.2")
    print("Multi-Symbol + Multi-Period")
    print("Strategy: Signal v1.6.1")
    print("=" * 70)

    data = run_multi_backtest()

    summary = build_summary(
        data["results"]
    )

    print()
    print("=" * 70)
    print("KẾT QUẢ TỔNG HỢP")
    print("=" * 70)

    for row in summary:

        print()
        print(
            f"{row['symbol']} | "
            f"{row['candles']} candles"
        )

        if row["status"] == "ERROR":

            print("  ERROR")

            continue

        print(
            f"  Actual candles: "
            f"{row['actual_candles']}"
        )

        print(
            f"  Trades: "
            f"{row['trades']}"
        )

        print(
            f"  Win rate: "
            f"{row['win_rate']}%"
        )

        print(
            f"  Profit Factor: "
            f"{row['profit_factor']}"
        )

        print(
            f"  Return: "
            f"{row['return_percent']}%"
        )

        print(
            f"  Max DD: "
            f"{row['max_drawdown_percent']}%"
        )

        print(
            f"  BUY: "
            f"{row['buy_trades']} trades / "
            f"{row['buy_win_rate']}%"
        )

        print(
            f"  SELL: "
            f"{row['sell_trades']} trades / "
            f"{row['sell_win_rate']}%"
        )

    print()
    print("=" * 70)
    print("BACKTEST v1.2 HOÀN TẤT")
    print("=" * 70)
