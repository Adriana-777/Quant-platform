from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional
import json

class Market(str, Enum):
    CRYPTO = "crypto"
    US_EQUITY = "us_equity"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"

@dataclass
class Tick:
    symbol: str
    market: Market
    timestamp: datetime
    price: float
    volume: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    exchange: str = ""

    def to_json(self) -> str:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["market"] = self.market.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, s: str) -> "Tick":
        d = json.loads(s)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        d["market"] = Market(d["market"])
        return cls(**d)

@dataclass
class Order:
    order_id: str
    strategy_id: str
    symbol: str
    market: Market
    side: OrderSide
    quantity: float
    price: Optional[float]
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
