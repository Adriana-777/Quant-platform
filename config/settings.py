"""
config/settings.py
全局配置 —— 所有敏感信息从环境变量读取，绝不硬编码
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Binance ───────────────────────────────────────────────────────────────────
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET     = os.getenv("BINANCE_SECRET", "")
BINANCE_WS_URL     = os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443")

# ── Alpaca ────────────────────────────────────────────────────────────────────
ALPACA_API_KEY     = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET      = os.getenv("ALPACA_SECRET", "")
ALPACA_WS_URL      = os.getenv("ALPACA_WS_URL", "wss://stream.data.alpaca.markets/v2")

# ── Kafka ─────────────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_BINANCE     = os.getenv("KAFKA_TOPIC_BINANCE", "market.binance.tick")
KAFKA_TOPIC_ALPACA      = os.getenv("KAFKA_TOPIC_ALPACA",  "market.alpaca.tick")

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB   = int(os.getenv("REDIS_DB",   0))

# ── PostgreSQL ────────────────────────────────────────────────────────────────
PG_HOST     = os.getenv("PG_HOST",     "localhost")
PG_PORT     = int(os.getenv("PG_PORT", 5432))
PG_USER     = os.getenv("PG_USER",     "quant")
PG_PASSWORD = os.getenv("PG_PASSWORD", "quant123")
PG_DB       = os.getenv("PG_DB",       "quant_platform")
PG_DSN      = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# ── 风控参数 ───────────────────────────────────────────────────────────────────
MAX_DAILY_DRAWDOWN  = float(os.getenv("MAX_DAILY_DRAWDOWN",  0.02))
MAX_POSITION_SIZE   = float(os.getenv("MAX_POSITION_SIZE",   0.10))
