import asyncio, logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

logger = logging.getLogger(__name__)

@dataclass
class Tick:
    symbol:    str
    price:     float
    volume:    float
    timestamp: datetime
    source:    str
    bid:       float | None = None
    ask:       float | None = None
    extra:     dict = field(default_factory=dict)

    def to_dict(self):
        return {"symbol": self.symbol, "price": self.price, "volume": self.volume,
                "timestamp": self.timestamp.isoformat(), "source": self.source,
                "bid": self.bid, "ask": self.ask}

class BaseFeed(ABC):
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"data.feeds.{name}")
        self._running = False
        self._callbacks: list[Callable[[Tick], None]] = []

    def add_callback(self, fn):
        self._callbacks.append(fn)

    def _emit(self, tick: Tick):
        for fn in self._callbacks:
            try: fn(tick)
            except Exception as e: self.logger.error(f"Callback error: {e}")

    @abstractmethod
    async def connect(self): ...
    @abstractmethod
    async def disconnect(self): ...
    @abstractmethod
    async def subscribe(self, symbols: list[str]): ...
    @abstractmethod
    async def _listen(self): ...

    async def run(self, symbols: list[str]):
        self._running = True
        retry_delay = 1
        while self._running:
            try:
                await self.connect()
                await self.subscribe(symbols)
                self.logger.info(f"{self.name} connected: {symbols}")
                retry_delay = 1
                await self._listen()
            except Exception as e:
                self.logger.error(f"{self.name} error: {e}, retry in {retry_delay}s")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            finally:
                await self.disconnect()

    def stop(self):
        self._running = False
