"""
策略基类 - 所有策略必须继承这个类
强制实现 on_market_data，确保接口统一
"""
from abc import ABC, abstractmethod
from queue import Queue
from core.event import MarketEvent, SignalEvent


class BaseStrategy(ABC):
    """
    策略基类，所有自定义策略继承此类

    使用方式:
        class MyStrategy(BaseStrategy):
            def on_market_data(self, event: MarketEvent):
                if self.should_buy(event):
                    self.send_signal(event.symbol, OrderSide.BUY)
    """

    def __init__(self, strategy_id: str, symbols: list[str], event_queue: Queue):
        self.strategy_id  = strategy_id
        self.symbols      = symbols
        self.event_queue  = event_queue
        self.is_active    = True

    @abstractmethod
    def on_market_data(self, event: MarketEvent):
        """接收行情，产生信号 - 子类必须实现"""
        raise NotImplementedError

    def send_signal(self, event: MarketEvent, side) -> None:
        """发送交易信号到事件队列"""
        signal = SignalEvent(
            symbol=event.symbol,
            strategy_id=self.strategy_id,
            side=side,
        )
        self.event_queue.put(signal)

    def on_fill(self, fill_event) -> None:
        """成交回调 - 子类可选实现，用于更新内部状态"""
        pass
