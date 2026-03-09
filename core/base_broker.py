"""
经纪商基类 - 模拟撮合和真实下单实现同一个接口
回测和实盘切换时，引擎代码不需要任何修改
"""
from abc import ABC, abstractmethod
from queue import Queue
from core.event import OrderEvent, FillEvent


class BaseBroker(ABC):

    def __init__(self, event_queue: Queue):
        self.event_queue = event_queue

    @abstractmethod
    def execute_order(self, order: OrderEvent) -> None:
        """执行订单，成交后将 FillEvent 放入队列"""
        raise NotImplementedError

    @abstractmethod
    def get_account_balance(self) -> dict:
        """返回账户余额信息"""
        raise NotImplementedError
