"""
infra/config/settings.py

统一配置管理。
用 pydantic-settings 从环境变量读取，本地开发从 .env 读取。
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class KafkaSettings(BaseSettings):
    bootstrap_servers: str = Field(default="localhost:9092")
    producer_acks: str = Field(default="1")        # "all" for production
    consumer_group_prefix: str = Field(default="quant")

    class Config:
        env_prefix = "KAFKA_"


class RedisSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: str = Field(default="")
    tick_ttl_seconds: int = Field(default=86400)   # Tick 缓存 24 小时

    class Config:
        env_prefix = "REDIS_"


class PostgresSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="quant")
    password: str = Field(default="quant123")
    database: str = Field(default="quant_platform")

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    class Config:
        env_prefix = "POSTGRES_"


class BinanceSettings(BaseSettings):
    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    testnet: bool = Field(default=True)            # 默认用测试网，保护资金
    ws_url: str = Field(default="wss://stream.binance.com:9443/ws")

    class Config:
        env_prefix = "BINANCE_"


class AlpacaSettings(BaseSettings):
    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    paper_trading: bool = Field(default=True)      # 默认用 paper trading
    ws_url: str = Field(default="wss://stream.data.alpaca.markets/v2/iex")

    class Config:
        env_prefix = "ALPACA_"


class Settings(BaseSettings):
    env: str = Field(default="development")        # development / production
    log_level: str = Field(default="INFO")

    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    binance: BinanceSettings = Field(default_factory=BinanceSettings)
    alpaca: AlpacaSettings = Field(default_factory=AlpacaSettings)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """
    单例模式，全局共享同一个配置实例。
    用法：from infra.config.settings import get_settings
          settings = get_settings()
    """
    return Settings()
