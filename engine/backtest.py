"""
engine/backtest.py

事件驱动回测引擎。

核心设计：
1. 事件驱动 — 按时间顺序逐条处理历史数据，策略只能看到"当前时刻之前"的数据
2. 撮合模拟 — 模拟真实成交，包括手续费、滑点
3. 持仓管理 — 实时跟踪仓位、成本、盈亏
4. 性能指标 — 收益率、最大回撤、夏普比率、胜率
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import pandas as pd
import numpy as np
from loguru import logger


# ── 数据结构 ──────────────────────────────────

@dataclass
class Bar:
    """一根 K 线（OHLCV）"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    """策略发出的交易信号"""
    symbol: str
    timestamp: datetime
    side: str          # "buy" 或 "sell"
    quantity: float
    price: float       # 期望成交价（实际会加滑点）
    strategy_id: str


@dataclass
class Trade:
    """一笔成交记录"""
    symbol: str
    timestamp: datetime
    side: str
    quantity: float
    price: float       # 实际成交价（含滑点）
    commission: float  # 手续费
    strategy_id: str


@dataclass
class Position:
    """持仓状态"""
    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0    # 平均持仓成本
    realized_pnl: float = 0.0  # 已实现盈亏

    @property
    def is_empty(self) -> bool:
        return abs(self.quantity) < 1e-8

    def unrealized_pnl(self, current_price: float) -> float:
        """浮动盈亏"""
        return (current_price - self.avg_cost) * self.quantity


@dataclass
class PortfolioSnapshot:
    """每根 K 线结束时的组合快照，用于计算回测指标"""
    timestamp: datetime
    cash: float
    positions_value: float  # 所有持仓按当前价格计算的市值

    @property
    def total_value(self) -> float:
        return self.cash + self.positions_value


# ── 撮合引擎 ──────────────────────────────────

class MatchEngine:
    """
    模拟交易所撮合。

    简化假设：
    - 市价单：以当前 Bar 的收盘价成交
    - 滑点：买入加 slippage，卖出减 slippage
    - 手续费：成交金额 * commission_rate
    """

    def __init__(
        self,
        commission_rate: float = 0.001,   # 0.1%，币安现货标准费率
        slippage: float = 0.0005,         # 0.05% 滑点
    ):
        self.commission_rate = commission_rate
        self.slippage = slippage

    def fill(self, signal: Signal, bar: Bar) -> Optional[Trade]:
        """
        尝试撮合一个信号。
        返回 Trade（成交）或 None（无法成交）。
        """
        # 简单检查：价格不能为 0
        if bar.close <= 0:
            return None

        # 计算实际成交价（加滑点）
        if signal.side == "buy":
            fill_price = bar.close * (1 + self.slippage)
        else:
            fill_price = bar.close * (1 - self.slippage)

        commission = fill_price * signal.quantity * self.commission_rate

        return Trade(
            symbol=signal.symbol,
            timestamp=bar.timestamp,
            side=signal.side,
            quantity=signal.quantity,
            price=fill_price,
            commission=commission,
            strategy_id=signal.strategy_id,
        )


# ── 持仓管理 ──────────────────────────────────

class PositionManager:
    """管理所有持仓，处理买入/卖出后的成本计算。"""

    def __init__(self, initial_cash: float):
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def apply_trade(self, trade: Trade) -> bool:
        """
        将成交应用到持仓。
        返回 False 表示资金不足，交易被拒绝。
        """
        pos = self.get_position(trade.symbol)

        if trade.side == "buy":
            cost = trade.price * trade.quantity + trade.commission
            if cost > self.cash:
                logger.warning(
                    f"资金不足: 需要 {cost:.2f}，当前 {self.cash:.2f}"
                )
                return False

            # 更新平均成本（加权平均）
            total_quantity = pos.quantity + trade.quantity
            if total_quantity > 0:
                pos.avg_cost = (
                    pos.avg_cost * pos.quantity + trade.price * trade.quantity
                ) / total_quantity
            pos.quantity = total_quantity
            self.cash -= cost

        elif trade.side == "sell":
            if trade.quantity > pos.quantity:
                logger.warning(
                    f"持仓不足: 需要卖 {trade.quantity}，当前持有 {pos.quantity}"
                )
                return False

            # 计算已实现盈亏
            realized = (trade.price - pos.avg_cost) * trade.quantity - trade.commission
            pos.realized_pnl += realized
            pos.quantity -= trade.quantity
            self.cash += trade.price * trade.quantity - trade.commission

        return True

    def total_value(self, current_prices: dict[str, float]) -> float:
        """计算当前总资产（现金 + 所有持仓市值）"""
        positions_value = sum(
            pos.quantity * current_prices.get(pos.symbol, pos.avg_cost)
            for pos in self.positions.values()
            if not pos.is_empty
        )
        return self.cash + positions_value


# ── 性能指标计算 ──────────────────────────────

class PerformanceAnalyzer:
    """根据组合快照序列计算回测指标。"""

    def analyze(self, snapshots: list[PortfolioSnapshot], initial_cash: float) -> dict:
        if len(snapshots) < 2:
            return {}

        values = [s.total_value for s in snapshots]
        timestamps = [s.timestamp for s in snapshots]

        total_return = (values[-1] - initial_cash) / initial_cash

        # 最大回撤
        max_drawdown = self._max_drawdown(values)

        # 日收益率序列
        daily_returns = self._daily_returns(values, timestamps)

        # 夏普比率（假设无风险利率 = 0，年化）
        sharpe = self._sharpe_ratio(daily_returns)

        # 年化收益率
        days = (timestamps[-1] - timestamps[0]).days or 1
        annualized_return = (1 + total_return) ** (365 / days) - 1

        return {
            "initial_cash":       f"${initial_cash:,.2f}",
            "final_value":        f"${values[-1]:,.2f}",
            "total_return":       f"{total_return:.2%}",
            "annualized_return":  f"{annualized_return:.2%}",
            "max_drawdown":       f"{max_drawdown:.2%}",
            "sharpe_ratio":       f"{sharpe:.2f}",
            "total_bars":         len(snapshots),
        }

    def _max_drawdown(self, values: list[float]) -> float:
        """从历史最高点跌到最低点的最大跌幅。"""
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _daily_returns(
        self, values: list[float], timestamps: list[datetime]
    ) -> list[float]:
        """计算每期收益率。"""
        returns = []
        for i in range(1, len(values)):
            if values[i - 1] > 0:
                returns.append((values[i] - values[i - 1]) / values[i - 1])
        return returns

    def _sharpe_ratio(self, returns: list[float], periods_per_year: int = 365) -> float:
        """夏普比率 = 平均收益 / 收益标准差 * sqrt(年化周期数)"""
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        std = arr.std()
        if std == 0:
            return 0.0
        return (arr.mean() / std) * np.sqrt(periods_per_year)


# ── 回测引擎主体 ──────────────────────────────

class BacktestEngine:
    """
    回测引擎主类。

    使用方式：
        engine = BacktestEngine(initial_cash=100_000)
        engine.add_strategy(MyStrategy())
        results = engine.run(bars)
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        commission_rate: float = 0.001,
        slippage: float = 0.0005,
    ):
        self.initial_cash = initial_cash
        self.match_engine = MatchEngine(commission_rate, slippage)
        self.position_manager = PositionManager(initial_cash)
        self.analyzer = PerformanceAnalyzer()

        self.strategies = []
        self.trades: list[Trade] = []
        self.snapshots: list[PortfolioSnapshot] = []
        self.current_prices: dict[str, float] = {}

    def add_strategy(self, strategy):
        """注册一个策略。"""
        self.strategies.append(strategy)
        logger.info(f"📋 注册策略: {strategy.strategy_id}")

    def run(self, bars: list[Bar]) -> dict:
        """
        主循环：按时间顺序处理每根 K 线。

        每根 Bar 的处理流程：
        1. 更新当前价格
        2. 让所有策略生成信号
        3. 撮合信号
        4. 记录快照
        """
        logger.info(f"🚀 开始回测: {len(bars)} 根 K 线")
        logger.info(f"   时间范围: {bars[0].timestamp} → {bars[-1].timestamp}")
        logger.info(f"   初始资金: ${self.initial_cash:,.2f}")

        for i, bar in enumerate(bars):
            # 1. 更新当前价格
            self.current_prices[bar.symbol] = bar.close

            # 2. 策略生成信号（只能看到 bar[0..i] 的数据，不能看未来）
            history = bars[:i + 1]
            for strategy in self.strategies:
                signals = strategy.on_bar(bar, history, self.position_manager)
                for signal in (signals or []):
                    # 3. 撮合
                    trade = self.match_engine.fill(signal, bar)
                    if trade:
                        success = self.position_manager.apply_trade(trade)
                        if success:
                            self.trades.append(trade)
                            logger.debug(
                                f"✅ 成交: {trade.side.upper()} {trade.symbol} "
                                f"x{trade.quantity} @ {trade.price:.2f}"
                            )

            # 4. 记录快照
            total = self.position_manager.total_value(self.current_prices)
            positions_value = total - self.position_manager.cash
            self.snapshots.append(PortfolioSnapshot(
                timestamp=bar.timestamp,
                cash=self.position_manager.cash,
                positions_value=positions_value,
            ))

        # 计算指标
        results = self.analyzer.analyze(self.snapshots, self.initial_cash)
        results["total_trades"] = len(self.trades)

        logger.info("📊 回测完成")
        for k, v in results.items():
            logger.info(f"   {k}: {v}")

        return results