"""
Kafka Topic 初始化脚本。
在项目启动前运行一次：python scripts/init_kafka_topics.py
"""
import sys
sys.path.insert(0, ".")

from confluent_kafka.admin import AdminClient, NewTopic
from infra.kafka.topics import Topics
from infra.config.settings import get_settings
from loguru import logger


def create_topics():
    settings = get_settings()
    admin = AdminClient({"bootstrap.servers": settings.kafka.bootstrap_servers})

    topic_configs = [
        Topics.CRYPTO_TICK,
        Topics.CRYPTO_OHLCV,
        Topics.EQUITY_TICK,
        Topics.EQUITY_OHLCV,
        Topics.SIGNALS,
        Topics.ORDERS,
    ]

    new_topics = [
        NewTopic(
            tc.name,
            num_partitions=tc.partitions,
            replication_factor=tc.replication_factor,
            config={"retention.ms": str(tc.retention_ms)}
        )
        for tc in topic_configs
    ]

    results = admin.create_topics(new_topics)

    for topic, future in results.items():
        try:
            future.result()
            logger.info(f"✅ Topic created: {topic}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"⏭️  Topic already exists: {topic}")
            else:
                logger.error(f"❌ Failed to create topic {topic}: {e}")


if __name__ == "__main__":
    create_topics()
