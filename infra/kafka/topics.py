from dataclasses import dataclass

@dataclass(frozen=True)
class TopicConfig:
    name: str
    partitions: int
    replication_factor: int
    retention_ms: int

class Topics:
    CRYPTO_TICK = TopicConfig(name="crypto.tick", partitions=4, replication_factor=1, retention_ms=86_400_000)
    CRYPTO_OHLCV = TopicConfig(name="crypto.ohlcv", partitions=2, replication_factor=1, retention_ms=604_800_000)
    EQUITY_TICK = TopicConfig(name="equity.tick", partitions=4, replication_factor=1, retention_ms=86_400_000)
    EQUITY_OHLCV = TopicConfig(name="equity.ohlcv", partitions=2, replication_factor=1, retention_ms=604_800_000)
    SIGNALS = TopicConfig(name="trading.signals", partitions=2, replication_factor=1, retention_ms=3_600_000)
    ORDERS = TopicConfig(name="trading.orders", partitions=2, replication_factor=1, retention_ms=604_800_000)

class ConsumerGroups:
    STORAGE_WRITER = "storage.writer"
    REDIS_UPDATER = "redis.updater"
    BACKTEST_FEEDER = "backtest.feeder"
    MONITOR_REALTIME = "monitor.realtime"
    RISK_CHECKER = "risk.checker"
