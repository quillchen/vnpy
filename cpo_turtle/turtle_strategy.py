"""
CPO 海龟策略回测 —— 策略层

long-only 海龟趋势策略（A 股适配）：
- 入场：突破前 entry_window 日最高（唐奇安上轨），stop buy
- 加仓：每上涨 0.5×ATR 加一单元，最多 max_units 单元
- 止损/离场：min(入场价-2×ATR, 前 exit_window 日最低)，stop sell
- A 股适配：只做多、T+1（当日买入次日才可卖）、涨跌停（涨停不买/跌停不卖）、100 股下取整
"""

import numpy as np

from vnpy_ctastrategy.template import CtaTemplate
from vnpy.trader.constant import Direction
from vnpy.trader.object import BarData, TradeData
from vnpy.trader.utility import ArrayManager, round_to, floor_to

from . import config as C


class TurtleStrategy(CtaTemplate):
    """CPO long-only 海龟策略"""

    author: str = "CPO Turtle"

    # ===== 参数 =====
    entry_window: int = C.ENTRY_WINDOW
    exit_window: int = C.EXIT_WINDOW
    atr_window: int = C.ATR_WINDOW
    risk_percent: float = C.RISK_PERCENT
    max_units: int = C.MAX_UNITS
    atr_stop_mult: float = C.ATR_STOP_MULT

    parameters = [
        "entry_window", "exit_window", "atr_window",
        "risk_percent", "max_units", "atr_stop_mult",
    ]

    # ===== 变量 =====
    entry_up: float = 0.0
    exit_down: float = 0.0
    atr_value: float = 0.0
    units: int = 0
    entry_price: float = 0.0

    variables = ["entry_up", "exit_down", "atr_value", "units", "entry_price"]

    def on_init(self) -> None:
        """初始化：预热数据已在 history_data 中，无需 load_bar"""
        self.am: ArrayManager = ArrayManager(size=C.AM_SIZE)
        self.units = 0
        self.entry_price = 0.0
        self.last_buy_date = None
        self.write_log("策略初始化")

    def on_bar(self, bar: BarData) -> None:
        """新的日线"""
        self.cancel_all()
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # 唐奇安通道（不含当日：突破"前 N 日"高/低）与 ATR
        self.entry_up = float(np.max(self.am.high_array[-self.entry_window - 1: -1]))
        self.exit_down = float(np.min(self.am.low_array[-self.exit_window - 1: -1]))
        self.atr_value = self.am.atr(self.atr_window)

        if self.atr_value <= 0:
            return

        pricetick: float = self.get_pricetick()
        extra: dict = bar.extra or {}
        limit_up: bool = extra.get("limit_up", False)
        limit_down: bool = extra.get("limit_down", False)
        today = bar.datetime.date()

        # ---- 建仓 / 加仓（未涨停）----
        if self.units < self.max_units and not limit_up:
            unit: float = self.cta_engine.capital * self.risk_percent / (self.atr_value * C.SIZE)
            unit = floor_to(unit, C.MIN_VOLUME)
            if unit >= C.MIN_VOLUME:
                if self.units == 0:
                    price: float = round_to(self.entry_up, pricetick)
                else:
                    price = round_to(self.entry_price + 0.5 * self.atr_value, pricetick)
                self.buy(price, unit, stop=True)

        # ---- 止损 / 离场（持仓、非 T+1 买入日、未跌停）----
        if (
            self.pos > 0
            and self.last_buy_date != today
            and not limit_down
        ):
            stop_price: float = self.entry_price - self.atr_stop_mult * self.atr_value
            exit_price: float = max(stop_price, self.exit_down)
            exit_price = round_to(exit_price, pricetick)
            self.sell(exit_price, abs(self.pos), stop=True)

    def on_trade(self, trade: TradeData) -> None:
        """成交回调：跟踪建仓单元/入场价/T+1 日期"""
        if trade.direction == Direction.LONG:
            if self.units == 0:
                self.entry_price = trade.price
            self.units += 1
            self.last_buy_date = self.cta_engine.datetime.date()
        else:
            # 平仓（long-only 下 SHORT 即卖出离场），状态清零
            self.units = 0
            self.entry_price = 0.0

    def on_stop(self) -> None:
        """"""
        return

    def on_order(self, order) -> None:
        """"""
        return
