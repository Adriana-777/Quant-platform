"""
scripts/run_backtest.py

用 PostgreSQL 里的真实历史数据跑回测。
"""

import sys
sys.path.insert(0, '/opt/quant_platform')

import psycopg2
from datetime import datetime
from loguru import logger

from engine.backtest import BacktestEngine, Bar
from strategies.ma_crossover import MACrossoverStrategy
from infra.config.settings import get_settings


def load_bars_from_db(symbol: str, limit: int = 1000) -> list[Bar]:
    """从 PostgreSQL 加载历史 Tick 数据，聚合成 1 分钟 K 线。"""
    settings = get_settings()
    conn = psycopg2.connect(
        host=settings.postgres.host,
        port=settings.postgres.port,
        user=settings.postgres.user,
        password=settings.postgres.password,
        dbname=settings.postgres.database,
    )

    with conn.cursor() as cur:
        # 用 PostgreSQL 的 date_trunc 把 tick 数据聚合成 1 分钟 K 线
        cur.execute("""
            SELECT
                date_trunc('minute', timestamp) AS bar_time,
                FIRST_VALUE(price) OVER (
                    PARTITION BY date_trunc('minute', timestamp)
                    ORDER BY timestamp
                ) AS open,
                MAX(price) AS high,
                MIN(price) AS low,
                LAST_VALUE(price) OVER (
                    PARTITION BY date_trunc('minute', timestamp)
                    ORDER BY timestamp
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS close,
                SUM(volume) AS volume
            FROM ticks
            WHERE symbol = %s
            GROUP BY date_trunc('minute', timestamp), timestamp, price
            ORDER BY bar_time
            LIMIT %s
        """, (symbol, limit))

        rows = cur.fetchall()

    conn.close()

    if not rows:
        logger.warning(f"没有找到 {symbol} 的数据，使用模拟数据")
        return _generate_mock_bars(symbol)

    # 去重（同一分钟只保留一条）
    seen = {}
    for row in rows:
        bar_time = row[0]
        if bar_time not in seen:
            seen[bar_time] = Bar(
                symbol=symbol,
                timestamp=bar_time,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
            )

    bars = sorted(seen.values(), key=lambda b: b.timestamp)
    logger.info(f"✅ 从数据库加载 {len(bars)} 根 K 线 ({symbol})")
    return bars


def _generate_mock_bars(symbol: str, n: int = 200) -> list[Bar]:
    """生成模拟数据用于测试（数据库数据不足时使用）。"""
    import random
    from datetime import timedelta

    logger.info(f"生成 {n} 根模拟 K 线")
    bars = []
    price = 69000.0
    ts = datetime(2026, 1, 1)

    for i in range(n):
        change = random.gauss(0, 0.002)  # 正态分布随机游走
        price = price * (1 + change)
        high = price * (1 + abs(random.gauss(0, 0.001)))
        low = price * (1 - abs(random.gauss(0, 0.001)))
        bars.append(Bar(
            symbol=symbol,
            timestamp=ts,
            open=price,
            high=high,
            low=low,
            close=price,
            volume=random.uniform(0.1, 2.0),
        ))
        ts += timedelta(minutes=1)

    return bars


def main():
    logger.info("=" * 50)
    logger.info("🔬 开始回测")
    logger.info("=" * 50)

    # 加载数据
    bars = load_bars_from_db("BTCUSDT", limit=500)

    if len(bars) < 30:
        logger.warning(f"数据只有 {len(bars)} 根，使用模拟数据补充")
        bars = _generate_mock_bars("BTCUSDT", 200)

    # 初始化引擎
    engine = BacktestEngine(
        initial_cash=100_000.0,   # 10 万美元初始资金
        commission_rate=0.001,    # 0.1% 手续费
        slippage=0.0005,          # 0.05% 滑点
    )

    # 注册策略
    strategy = MACrossoverStrategy(
        symbol="BTCUSDT",
        short_window=5,
        long_window=20,
        quantity=0.01,
    )
    engine.add_strategy(strategy)

    # 跑回测
    results = engine.run(bars)

    # 打印结果
    logger.info("=" * 50)
    logger.info("📊 回测结果")
    logger.info("=" * 50)
    for k, v in results.items():
        logger.info(f"  {k:25s}: {v}")


if __name__ == "__main__":
    main()