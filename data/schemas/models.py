"""
data/schemas/models.py

所有核心数据结构定义。
用 dataclass 而不是 dict，强类型，IDE 友好，序列化方便。
"""

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

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"

class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Tick:
    """最小行情单元，是整个系统的原始数据单元。"""
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
class OHLCV:
    """K 线数据。"""
    symbol: str
    market: Market
    interval: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int = 0


@dataclass
class Order:
    """订单。策略引擎产生，风控审核，执行层发送。"""
    order_id: str
    strategy_id: str
    symbol: str
    market: Market
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Position:
    """持仓。实盘和回测共用。"""
    strategy_id: str
    symbol: str
    market: Market
    quantity: float          # 正数=多头，负数=空头
    avg_cost: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0

    def update_unrealized_pnl(self, current_price: float) -> None:
        self.unrealized_pnl = (current_price - self.avg_cost) * self.quantity
        self.updated_at = datetime.utcnow()
