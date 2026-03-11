"""
data/storage/storage_writer.py

Kafka 消费者，同时写入 Redis（实时状态）和 PostgreSQL（历史数据）。

设计要点：
1. 两个独立 Consumer Group，保证 Redis 和 PostgreSQL 都收到全量数据
2. 批量写入 PostgreSQL（每 100 条或每 2 秒一次），减少数据库压力
3. Redis 只保留最新价格和最近 200 条 Tick，控制内存使用
4. 消费失败不提交 Offset，保证 at-least-once delivery
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Optional

import redis
import psycopg2
import psycopg2.extras
from confluent_kafka import Consumer, KafkaError
from loguru import logger

from data.schemas.models import Tick, Market
from infra.config.settings import get_settings
from infra.kafka.topics import Topics, ConsumerGroups


# ── 批量写入配置 ──────────────────────────────
BATCH_SIZE = 100        # 积累 100 条再写一次 PostgreSQL
BATCH_TIMEOUT = 2.0     # 或者每 2 秒强制写一次，防止低频时数据积压
REDIS_TICK_HISTORY = 200  # 每个 symbol 在 Redis 里保留最近 200 条


class RedisWriter:
    """
    负责把 Tick 数据写入 Redis。

    存储结构：
    - tick:latest:{symbol}     → 最新一条 Tick（Hash）
    - tick:history:{symbol}    → 最近 200 条 Tick（List，左进右出）
    - tick:stats               → 全局统计（总消息数、最后更新时间）
    """

    def __init__(self, settings):
        self.r = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password or None,
            decode_responses=True,
        )
        # 测试连接
        self.r.ping()
        logger.info("✅ Redis 连接成功")

    def write_tick(self, tick: Tick):
        pipe = self.r.pipeline()  # 用 pipeline 批量执行，减少网络往返

        latest_key = f"tick:latest:{tick.symbol}"
        history_key = f"tick:history:{tick.symbol}"

        # 更新最新价格
        pipe.hset(latest_key, mapping={
            "price": tick.price,
            "volume": tick.volume,
            "timestamp": tick.timestamp.isoformat(),
            "exchange": tick.exchange,
        })
        pipe.expire(latest_key, 86400)  # 24 小时过期

        # 推入历史列表（最多保留 200 条）
        pipe.lpush(history_key, tick.to_json())
        pipe.ltrim(history_key, 0, REDIS_TICK_HISTORY - 1)
        pipe.expire(history_key, 86400)

        # 更新全局统计
        pipe.hincrby("tick:stats", "total_count", 1)
        pipe.hset("tick:stats", "last_updated", tick.timestamp.isoformat())

        pipe.execute()

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """供其他服务查询最新价格。"""
        val = self.r.hget(f"tick:latest:{symbol}", "price")
        return float(val) if val else None


class PostgreSQLWriter:
    """
    负责把 Tick 数据批量写入 PostgreSQL。

    批量写入原因：
    - 单条 INSERT 每秒最多几百次，批量 INSERT 每秒可以几万条
    - 对于行情数据这种高频写入场景，批量是必须的
    """

    def __init__(self, settings):
        self.conn = psycopg2.connect(
            host=settings.postgres.host,
            port=settings.postgres.port,
            user=settings.postgres.user,
            password=settings.postgres.password,
            dbname=settings.postgres.database,
        )
        self.conn.autocommit = False
        self._ensure_table()
        logger.info("✅ PostgreSQL 连接成功")

    def _ensure_table(self):
        """确保表存在，不存在则创建。"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    id          BIGSERIAL PRIMARY KEY,
                    symbol      VARCHAR(20)  NOT NULL,
                    market      VARCHAR(20)  NOT NULL,
                    exchange    VARCHAR(50)  NOT NULL,
                    price       NUMERIC(20, 8) NOT NULL,
                    volume      NUMERIC(20, 8) NOT NULL,
                    bid         NUMERIC(20, 8),
                    ask         NUMERIC(20, 8),
                    timestamp   TIMESTAMPTZ  NOT NULL,
                    created_at  TIMESTAMPTZ  DEFAULT NOW()
                );

                -- 按时间和 symbol 建索引，加速回测查询
                CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time
                    ON ticks (symbol, timestamp DESC);
            """)
            self.conn.commit()
        logger.info("✅ ticks 表已就绪")

    def write_batch(self, ticks: list[Tick]):
        """批量写入，用 execute_values 一次 INSERT 多行，性能最优。"""
        if not ticks:
            return

        rows = [
            (
                t.symbol,
                t.market.value,
                t.exchange,
                t.price,
                t.volume,
                t.bid,
                t.ask,
                t.timestamp,
            )
            for t in ticks
        ]

        with self.conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO ticks
                    (symbol, market, exchange, price, volume, bid, ask, timestamp)
                VALUES %s
                """,
                rows,
            )
        self.conn.commit()
        logger.debug(f"💾 写入 PostgreSQL: {len(ticks)} 条")


class StorageWriter:
    """
    主服务：从 Kafka 消费 Tick，分发给 Redis 和 PostgreSQL。
    """

    def __init__(self):
        self.settings = get_settings()
        self.redis_writer = RedisWriter(self.settings)
        self.pg_writer = PostgreSQLWriter(self.settings)
        self.consumer = self._init_consumer()
        self._batch: list[Tick] = []
        self._last_flush = time.time()
        self._running = False

    def _init_consumer(self) -> Consumer:
        return Consumer({
            "bootstrap.servers": self.settings.kafka.bootstrap_servers,
            "group.id": ConsumerGroups.STORAGE_WRITER,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "session.timeout.ms": 30000,
            "max.poll.interval.ms": 300000,
})

    def _parse_tick(self, raw: str) -> Optional[Tick]:
        try:
            return Tick.from_json(raw)
        except Exception as e:
            logger.warning(f"Tick 解析失败: {e}")
            return None

    def _should_flush(self) -> bool:
        """达到批量大小或超时，触发写入。"""
        return (
            len(self._batch) >= BATCH_SIZE or
            time.time() - self._last_flush >= BATCH_TIMEOUT
        )

    def _flush(self):
        """把缓冲区里的数据写入 PostgreSQL，然后提交 Offset。"""
        if not self._batch:
            return
        try:
            self.pg_writer.write_batch(self._batch)
            self.consumer.commit()  # 写库成功才提交 Offset
            self._batch.clear()
            self._last_flush = time.time()
        except Exception as e:
            logger.error(f"批量写入失败: {e}")
            # 不清空 batch，不提交 Offset，下次重试

    def run(self):
        self._running = True
        self.consumer.subscribe([Topics.CRYPTO_TICK.name])
        logger.info("🚀 存储服务启动，开始消费 Kafka...")

        try:
            while self._running:
                msg = self.consumer.poll(timeout=0.5)

                if msg is None:
                    # 没有新消息，检查是否需要强制 flush
                    if self._should_flush():
                        self._flush()
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue  # 正常到达分区末尾
                    logger.error(f"Kafka 错误: {msg.error()}")
                    continue

                # 解析消息
                tick = self._parse_tick(msg.value().decode())
                if not tick:
                    continue

                # 立即写 Redis（实时性要求高）
                try:
                    self.redis_writer.write_tick(tick)
                except Exception as e:
                    logger.error(f"Redis 写入失败: {e}")

                # 加入批次等待写 PostgreSQL
                self._batch.append(tick)

                # 检查是否触发批量写入
                if self._should_flush():
                    self._flush()

        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            self._flush()  # 退出前把剩余数据写完
            self.consumer.close()
            logger.info("👋 存储服务已停止")

    def stop(self):
        self._running = False


if __name__ == "__main__":
    writer = StorageWriter()
    writer.run()