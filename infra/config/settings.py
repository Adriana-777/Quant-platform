from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

class KafkaSettings(BaseSettings):
    bootstrap_servers: str = Field(default="localhost:9092")
    class Config:
        env_prefix = "KAFKA_"

class RedisSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: str = Field(default="")
    class Config:
        env_prefix = "REDIS_"

class BinanceSettings(BaseSettings):
    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    testnet: bool = Field(default=True)
    class Config:
        env_prefix = "BINANCE_"

class AlpacaSettings(BaseSettings):
    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    paper_trading: bool = Field(default=True)
    class Config:
        env_prefix = "ALPACA_"

class Settings(BaseSettings):
    env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    binance: BinanceSettings = Field(default_factory=BinanceSettings)
    alpaca: AlpacaSettings = Field(default_factory=AlpacaSettings)
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
