"""
data/feeds/binance_feed.py

Binance WebSocket 行情采集服务。
订阅多个交易对的实时 Tick 数据，发送到 Kafka。

核心设计决策：
1. 用 asyncio 而不是多线程 —— WebSocket 是 IO 密集型，协程更高效
2. 自动重连 —— 网络断开后指数退避重试，不丢数据
3. 心跳检测 —— 定期发送 ping，防止连接被服务器静默关闭
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Optional

import websockets
from confluent_kafka import Producer
from loguru import logger

from data.schemas.models import Market, Tick
from infra.config.settings import get_settings
from infra.kafka.topics import Topics


# ── 配置 ──────────────────────────────────────
SYMBOLS = [
    "btcusdt",   # 比特币
    "ethusdt",   # 以太坊
    "bnbusdt",   # BNB
]

# 订阅多个交易对的聚合流
# <symbol>@aggTrade: 最新成交价和成交量
# <symbol>@bookTicker: 最优买卖价
STREAMS = [f"{s}@aggTrade" for s in SYMBOLS]
TESTNET_WS_URL = "wss://testnet.binance.vision/ws"
MAINNET_WS_URL = "wss://stream.binance.com:9443/ws"

# 重连配置
MAX_RETRIES = 10
BASE_RETRY_DELAY = 1    # 秒，指数退避起点
MAX_RETRY_DELAY = 60    # 秒，最长等待时间


class BinanceFeed:
    """
    Binance WebSocket 行情采集器。

    生命周期：
    1. 初始化 Kafka Producer
    2. 建立 WebSocket 连接
    3. 接收消息 → 解析 → 发送到 Kafka
    4. 断线自动重连
    """

    def __init__(self):
        self.settings = get_settings()
        self.producer = self._init_producer()
        self.ws_url = (
            TESTNET_WS_URL
            if self.settings.binance.testnet
            else MAINNET_WS_URL
        )
        self._running = False
        self._msg_count = 0
        self._last_log_time = time.time()

    def _init_producer(self) -> Producer:
        """初始化 Kafka Producer，配置重试和压缩。"""
        return Producer({
            "bootstrap.servers": self.settings.kafka.bootstrap_servers,
            "acks": "1",                  # 等待 leader 确认，平衡速度和可靠性
            "retries": 3,
            "compression.type": "lz4",    # 压缩减少网络传输
            "linger.ms": 5,               # 等 5ms 批量发送，提升吞吐量
        })

    def _delivery_callback(self, err, msg):
        """Kafka 消息发送回调，记录失败。"""
        if err:
            logger.error(f"Kafka 发送失败: {err} | topic={msg.topic()}")

    def _parse_agg_trade(self, raw: dict) -> Optional[Tick]:
        """
        解析 aggTrade 消息。

        Binance aggTrade 格式：
        {
            "e": "aggTrade",   # 事件类型
            "E": 1234567890,   # 事件时间（ms）
            "s": "BTCUSDT",    # 交易对
            "p": "50000.00",   # 成交价
            "q": "0.001",      # 成交量
            "T": 1234567890,   # 成交时间（ms）
            "m": false         # 是否是做市商
        }
        """
        try:
            return Tick(
                symbol=raw["s"],
                market=Market.CRYPTO,
                timestamp=datetime.fromtimestamp(
                    raw["T"] / 1000,
                    tz=timezone.utc
                ),
                price=float(raw["p"]),
                volume=float(raw["q"]),
                exchange="binance_testnet" if self.settings.binance.testnet else "binance",
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"解析失败: {e} | raw={raw}")
            return None

    def _send_to_kafka(self, tick: Tick):
        """发送 Tick 到 Kafka，使用 symbol 作为 key 保证同一交易对有序。"""
        self.producer.produce(
            topic=Topics.CRYPTO_TICK.name,
            key=tick.symbol.encode(),
            value=tick.to_json().encode(),
            callback=self._delivery_callback,
        )
        # 非阻塞 poll，触发回调
        self.producer.poll(0)

    def _log_stats(self):
        """每 10 秒打印一次采集统计。"""
        now = time.time()
        elapsed = now - self._last_log_time
        if elapsed >= 10:
            rate = self._msg_count / elapsed
            logger.info(
                f"📊 采集速率: {rate:.1f} msg/s | "
                f"累计: {self._msg_count} | "
                f"symbols: {SYMBOLS}"
            )
            self._msg_count = 0
            self._last_log_time = now

    async def _connect_and_consume(self):
        """建立 WebSocket 连接并持续消费消息。"""
        streams_path = "/".join(STREAMS)
        # 订阅多个流：/ws/stream1/stream2/stream3
        # 测试网和主网 URL 格式不同
        if self.settings.binance.testnet:
            url = f"wss://stream.testnet.binance.vision/ws/{STREAMS[0]}"
        else:
            url = f"wss://stream.binance.com:9443/stream?streams={streams_path}"

        logger.info(f"🔌 连接 Binance WebSocket: {url}")


        async with websockets.connect(
            url,
            ping_interval=20,     # 每 20s 发送 ping
            ping_timeout=10,      # 10s 没收到 pong 则断开
            close_timeout=5,
        ) as ws:
            logger.info(f"✅ WebSocket 连接成功 | 订阅: {STREAMS}")

            async for raw_msg in ws:
                if not self._running:
                    break

                try:
                    data = json.loads(raw_msg)

                    # 多流模式下消息格式：{"stream": "btcusdt@aggTrade", "data": {...}}
                    if "data" in data:
                        payload = data["data"]
                    else:
                        payload = data

                    if payload.get("e") == "aggTrade":
                        tick = self._parse_agg_trade(payload)
                        if tick:
                            self._send_to_kafka(tick)
                            self._msg_count += 1
                            self._log_stats()

                except json.JSONDecodeError as e:
                    logger.warning(f"JSON 解析失败: {e}")
                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")

    async def run(self):
        """主循环，带指数退避重连。"""
        self._running = True
        retry_count = 0
        retry_delay = BASE_RETRY_DELAY

        logger.info("🚀 Binance 行情采集服务启动")

        while self._running:
            try:
                await self._connect_and_consume()

                # 正常断开（_running=False），退出循环
                if not self._running:
                    break

                # 非预期断开，重连
                logger.warning("WebSocket 连接断开，准备重连...")
                retry_count = 0
                retry_delay = BASE_RETRY_DELAY

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"连接关闭: {e}")
            except OSError as e:
                logger.error(f"网络错误: {e}")
            except Exception as e:
                logger.error(f"未知错误: {e}")

            # 指数退避
            if retry_count >= MAX_RETRIES:
                logger.error(f"重试次数超过 {MAX_RETRIES} 次，停止重连")
                break

            logger.info(f"⏳ {retry_delay}s 后重连 (第 {retry_count + 1} 次)...")
            await asyncio.sleep(retry_delay)
            retry_count += 1
            retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

        # 确保所有消息都发送完毕
        self.producer.flush()
        logger.info("👋 Binance 采集服务已停止")

    def stop(self):
        self._running = False


async def main():
    feed = BinanceFeed()
    try:
        await feed.run()
    except KeyboardInterrupt:
        logger.info("收到停止信号")
        feed.stop()


if __name__ == "__main__":
    asyncio.run(main())