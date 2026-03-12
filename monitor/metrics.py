"""
monitor/metrics.py

用 prometheus_client 暴露我们服务的监控指标。
Prometheus 每 15 秒来抓一次这个接口的数据。
"""

from prometheus_client import (
    Counter, Gauge, Histogram, start_http_server
)
import time
from loguru import logger


# ── 定义指标 ──────────────────────────────────

# 计数器：只增不减
TICK_RECEIVED = Counter(
    'quant_tick_received_total',
    'Total ticks received from exchange',
    ['symbol', 'exchange']
)

TICK_WRITTEN_REDIS = Counter(
    'quant_tick_written_redis_total',
    'Total ticks written to Redis',
    ['symbol']
)

TICK_WRITTEN_POSTGRES = Counter(
    'quant_tick_written_postgres_total',
    'Total ticks written to PostgreSQL',
    ['symbol']
)

KAFKA_ERRORS = Counter(
    'quant_kafka_errors_total',
    'Total Kafka errors',
    ['error_type']
)

# 仪表盘：可增可减
KAFKA_LAG = Gauge(
    'quant_kafka_consumer_lag',
    'Kafka consumer lag (unprocessed messages)',
    ['consumer_group', 'topic']
)

LATEST_PRICE = Gauge(
    'quant_latest_price',
    'Latest price for each symbol',
    ['symbol']
)

REDIS_MEMORY_BYTES = Gauge(
    'quant_redis_memory_bytes',
    'Redis memory usage in bytes'
)

# 直方图：统计延迟分布
POSTGRES_WRITE_LATENCY = Histogram(
    'quant_postgres_write_latency_seconds',
    'PostgreSQL batch write latency',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

TICK_PROCESSING_LATENCY = Histogram(
    'quant_tick_processing_latency_seconds',
    'End-to-end tick processing latency',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
)


def start_metrics_server(port: int = 8000):
    """启动 metrics HTTP 服务，供 Prometheus 抓取。"""
    start_http_server(port)
    logger.info(f"📡 Metrics 服务启动: http://0.0.0.0:{port}/metrics")