"""
CPO 海龟策略回测 —— Runner

等权独立回测：149 只成分股各分配等额资金独立跑海龟，合并日盈亏得组合净值。
用法：
    python -m cpo_turtle.run_backtest --smoke   # 单只冒烟（中际旭创）
    python -m cpo_turtle.run_backtest           # 全量 149 只
"""

import sys
import pathlib
from datetime import datetime, date

import pandas as pd
from tqdm import tqdm

# 兜底项目根，兼容 `python cpo_turtle/run_backtest.py` 直接运行
_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vnpy.trader.constant import Interval
from vnpy_ctastrategy.backtesting import BacktestingEngine

from cpo_turtle import config as C
from cpo_turtle.data_loader import get_cpo_members, load_all_bars, load_bars, to_vt_symbol
from cpo_turtle.turtle_strategy import TurtleStrategy


SMOKE_CODE = "300308.SZ"   # 中际旭创


def _run_one(ts_code: str, bars: list, capital: float) -> tuple[pd.DataFrame, dict]:
    """对单只成分股跑一次回测，返回 (daily_df, statistics)"""
    engine = BacktestingEngine()
    engine.output = lambda msg: None     # 静音引擎逐根进度输出
    engine.set_parameters(
        vt_symbol=to_vt_symbol(ts_code),
        interval=Interval.DAILY,
        start=bars[0].datetime,
        end=datetime.strptime(C.BT_END, "%Y-%m-%d"),
        rate=C.RATE,
        slippage=C.SLIPPAGE,
        size=C.SIZE,
        pricetick=C.PRICETICK,
        capital=capital,
    )
    engine.add_strategy(TurtleStrategy, {})
    engine.history_data = bars          # 直接注入，跳过 load_data
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    statistics = engine.calculate_statistics(output=False)
    return daily_df, statistics


def _portfolio(daily_dfs: list[pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """合并各只日盈亏 → 组合日盈亏，裁剪到回测起点后算组合统计

    calculate_statistics 需要 net_pnl/commission/slippage/turnover/trade_count 列，
    故对各只 daily_df 按交易日对齐求和（这些都是可加的量）。
    """
    cols = ["net_pnl", "commission", "slippage", "turnover", "trade_count"]
    parts = [d[cols] for d in daily_dfs if not d.empty]
    combo = pd.concat(parts).groupby(level=0).sum()
    combo = combo[combo.index >= date.fromisoformat(C.BT_START)]

    engine = BacktestingEngine()
    engine.output = lambda msg: None
    engine.capital = C.TOTAL_CAPITAL
    statistics = engine.calculate_statistics(df=combo, output=False)
    return combo, statistics


def run_smoke() -> None:
    """单只冒烟：中际旭创全链路跑通"""
    bars = load_bars(SMOKE_CODE)
    print(f"[smoke] {SMOKE_CODE} bars={len(bars)}  起止 {bars[0].datetime.date()} ~ {bars[-1].datetime.date()}")
    daily_df, stat = _run_one(SMOKE_CODE, bars, capital=C.TOTAL_CAPITAL)
    print(f"[smoke] 成交笔数={len(daily_df)}  交易日={len(daily_df)}")
    print(f"[smoke] 总收益={stat.get('total_return', 0):.2f}%  年化={stat.get('annual_return', 0):.2f}%  "
          f"最大回撤={stat.get('max_ddpercent', 0):.2f}%  Sharpe={stat.get('sharpe_ratio', 0):.2f}")


def run_all() -> None:
    """全量等权回测"""
    members = get_cpo_members()
    print(f"CPO 成分股: {len(members)} 只，开始加载复权日线 ...")
    all_bars = load_all_bars(members)
    valid = {k: v for k, v in all_bars.items() if v}
    print(f"有效（剔 ST/停牌/新股/历史不足）: {len(valid)} 只")

    per_stock = C.TOTAL_CAPITAL / len(valid)
    print(f"总资金 {C.TOTAL_CAPITAL:,.0f}，每只分配 {per_stock:,.0f}")

    daily_dfs: list[pd.DataFrame] = []
    per_symbol: list[dict] = []
    for ts_code, bars in tqdm(valid.items(), desc="回测"):
        try:
            daily_df, stat = _run_one(ts_code, bars, per_stock)
        except Exception as exc:    # noqa: BLE001
            print(f"  {ts_code} 回测失败: {exc}")
            continue
        if daily_df.empty:
            continue
        daily_dfs.append(daily_df)
        stat = dict(stat)
        stat["ts_code"] = ts_code
        per_symbol.append(stat)

    print("\n========== 组合统计 ==========")
    combo, combo_stat = _portfolio(daily_dfs)
    # 打印关键指标
    for key in ("total_return", "annual_return", "max_ddpercent", "sharpe_ratio",
                "return_drawdown_ratio", "total_trade_count"):
        print(f"  {key}: {combo_stat.get(key)}")

    # 输出文件
    csv_path = C.OUTPUT_DIR / C.RESULT_CSV
    pd.DataFrame(per_symbol).to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n单只统计已写入: {csv_path}")

    # 组合资金曲线图
    try:
        engine = BacktestingEngine()
        engine.capital = C.TOTAL_CAPITAL
        engine.calculate_statistics(df=combo, output=False)   # 给 combo 补 balance/drawdown 列
        fig = engine.show_chart(combo)
        html_path = C.OUTPUT_DIR / "portfolio_curve.html"
        fig.write_html(str(html_path))
        print(f"组合曲线已写入: {html_path}")
    except Exception as exc:    # noqa: BLE001
        print(f"绘图失败（不影响统计）: {exc}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="单只冒烟")
    args = parser.parse_args()
    if args.smoke:
        run_smoke()
    else:
        run_all()
