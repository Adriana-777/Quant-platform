"""
strategies/ma_crossover.py

双均线交叉策略（最经典的趋势跟踪策略）。

逻辑：
- 短期均线从下方穿过长期均线 → 金叉 → 买入
- 短期均线从上方穿过长期均线 → 死叉 → 卖出

这个策略本身不重要，目的是验证回测引擎框架正确。
"""

from engine.backtest import Bar, Signal, Position, PositionManager


class MACrossoverStrategy:
    """
    双均线交叉策略。

    参数：
    - short_window: 短期均线周期（默认 5）
    - long_window:  长期均线周期（默认 20）
    - quantity:     每次买入数量
    """

    def __init__(
        self,
        symbol: str,
        short_window: int = 5,
        long_window: int = 20,
        quantity: float = 0.01,   # BTC 每次买 0.01 个
    ):
        self.symbol = symbol
        self.short_window = short_window
        self.long_window = long_window
        self.quantity = quantity
        self.strategy_id = f"ma_{short_window}_{long_window}"

    def on_bar(
        self,
        bar: Bar,
        history: list[Bar],
        position_manager: PositionManager,
    ) -> list[Signal]:
        """
        每根 K 线调用一次，返回信号列表。
        """
        # 数据不够，无法计算均线
        if len(history) < self.long_window:
            return []

        closes = [b.close for b in history if b.symbol == self.symbol]
        if len(closes) < self.long_window:
            return []

        # 计算均线
        short_ma = sum(closes[-self.short_window:]) / self.short_window
        long_ma = sum(closes[-self.long_window:]) / self.long_window

        # 前一根 K 线的均线（用于判断是否发生交叉）
        prev_closes = closes[:-1]
        if len(prev_closes) < self.long_window:
            return []

        prev_short_ma = sum(prev_closes[-self.short_window:]) / self.short_window
        prev_long_ma = sum(prev_closes[-self.long_window:]) / self.long_window

        position = position_manager.get_position(self.symbol)
        signals = []

        # 金叉：短期均线从下方穿越长期均线 → 买入
        if prev_short_ma <= prev_long_ma and short_ma > long_ma:
            if position.is_empty:
                signals.append(Signal(
                    symbol=self.symbol,
                    timestamp=bar.timestamp,
                    side="buy",
                    quantity=self.quantity,
                    price=bar.close,
                    strategy_id=self.strategy_id,
                ))

        # 死叉：短期均线从上方穿越长期均线 → 卖出
        elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
            if not position.is_empty:
                signals.append(Signal(
                    symbol=self.symbol,
                    timestamp=bar.timestamp,
                    side="sell",
                    quantity=position.quantity,
                    price=bar.close,
                    strategy_id=self.strategy_id,
                ))

        return signals