"""
事件系统 - 整个平台的通信核心
所有模块通过事件队列解耦，而不是直接调用
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(Enum):
    MARKET  = "MARKET"   # 新的行情数据到达
    SIGNAL  = "SIGNAL"   # 策略产生信号
    ORDER   = "ORDER"    # 下单指令
    FILL    = "FILL"     # 成交回报


class OrderSide(Enum):
    BUY  = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT  = "LIMIT"


@dataclass
class MarketEvent:
    """行情事件 - 数据层产生，策略层消费"""
    type: EventType = field(default=EventType.MARKET, init=False)
    symbol:    str       # e.g. "BTCUSDT" or "AAPL"
    exchange:  str       # "binance" | "alpaca"
    timestamp: datetime
    open:   float
    high:   float
    low:    float
    close:  float
    volume: float


@dataclass
class SignalEvent:
    """信号事件 - 策略层产生，引擎消费"""
    type: EventType = field(default=EventType.SIGNAL, init=False)
    symbol:         str
    strategy_id:    str
    side:           OrderSide
    strength:       float = 1.0   # 信号强度，用于仓位sizing
    timestamp:      datetime = field(default_factory=datetime.utcnow)


@dataclass
class OrderEvent:
    """订单事件 - 引擎产生，经纪商消费"""
    type: EventType = field(default=EventType.ORDER, init=False)
    symbol:     str
    order_type: OrderType
    side:       OrderSide
    quantity:   float
    price:      Optional[float] = None   # limit price，market单为None
    timestamp:  datetime = field(default_factory=datetime.utcnow)


@dataclass
class FillEvent:
    """成交事件 - 经纪商产生，portfolio消费"""
    type: EventType = field(default=EventType.FILL, init=False)
    symbol:       str
    side:         OrderSide
    quantity:     float
    fill_price:   float
    commission:   float
    timestamp:    datetime = field(default_factory=datetime.utcnow)
