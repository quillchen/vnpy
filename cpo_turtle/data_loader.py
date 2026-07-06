"""
CPO 海龟策略回测 —— 数据层

SQLite 取成分股 → QuestDB 取日线 + 复权因子 → 前复权 → 剔停牌/ST/新股
→ 构造 list[BarData]（涨跌停标志注入 extra）
"""

import sqlite3
from datetime import datetime, timedelta

import pandas as pd

from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval

from db.questdb_connect import get_target_client

from . import config as C


# tushare 后缀 → vnpy Exchange（引擎 set_parameters 要求 SZSE/SSE/BSE）
TS_SUFFIX_TO_EXCHANGE: dict[str, Exchange] = {
    "SZ": Exchange.SZSE,
    "SH": Exchange.SSE,
    "BJ": Exchange.BSE,
}


def split_ts_code(ts_code: str) -> tuple[str, Exchange]:
    """000001.SZ -> ('000001', Exchange.SZSE)"""
    symbol, suffix = ts_code.split(".")
    return symbol, TS_SUFFIX_TO_EXCHANGE[suffix]


def to_vt_symbol(ts_code: str) -> str:
    """000001.SZ -> '000001.SZSE'"""
    symbol, exchange = split_ts_code(ts_code)
    return f"{symbol}.{exchange.value}"


def get_cpo_members() -> list[str]:
    """取 CPO 板块成分股代码（con_code, deleted=0）"""
    con = sqlite3.connect("file:" + C.SQLITE_PATH + "?mode=ro", uri=True)
    try:
        df = pd.read_sql(
            "SELECT con_code FROM sector_ths_item "
            "WHERE ts_code = ? AND deleted = 0 ORDER BY con_code",
            con, params=(C.SECTOR_CODE,)
        )
    finally:
        con.close()
    return df["con_code"].tolist()


def get_st_codes() -> set[str]:
    """回测区间内出现过 ST 处理的股票代码集合"""
    sql = (
        f"SELECT DISTINCT ts_code FROM stock_st "
        f"WHERE trade_date >= '{C.BT_START}' AND trade_date <= '{C.BT_END}'"
    )
    try:
        df = get_target_client().query_csv(sql)
        return set(df["ts_code"].tolist())
    except Exception:
        return set()


def _limit_ratio(symbol: str) -> float:
    """涨跌停比例：创业板/科创板 20%，其余 10%"""
    if symbol.startswith(("300", "301", "688", "689")):
        return 0.20
    return 0.10


def _warmup_start() -> str:
    d = datetime.strptime(C.BT_START, "%Y-%m-%d") - timedelta(days=C.WARMUP_DAYS)
    return d.strftime("%Y-%m-%d")


def load_all_bars(
    members: list[str],
    skip_st: bool = True
) -> dict[str, list[BarData]]:
    """批量取所有成分股的前复权日线，返回 {ts_code: [BarData]}

    含 start 前 WARMUP_DAYS 预热段；自动剔停牌/ST/历史不足的票。
    """
    if not members:
        return {}

    pre_start = _warmup_start()
    st_codes = get_st_codes() if skip_st else set()
    inlist = ",".join("'" + c + "'" for c in members)

    sql_daily = (
        f"SELECT ts_code, trade_date, open, high, low, close, volume, pct_chg "
        f"FROM stock_daily "
        f"WHERE ts_code IN ({inlist}) "
        f"AND trade_date >= '{pre_start}' AND trade_date <= '{C.BT_END}'"
    )
    sql_adj = (
        f"SELECT ts_code, trade_date, adj_factor "
        f"FROM stock_adj_factor "
        f"WHERE ts_code IN ({inlist}) "
        f"AND trade_date >= '{pre_start}' AND trade_date <= '{C.BT_END}'"
    )

    daily = get_target_client().query_csv(sql_daily)
    adj = get_target_client().query_csv(sql_adj)

    # daily 与 adj 的 trade_date 时区表示不同（daily=00:00Z、adj=16:00Z=北京次日00:00），
    # 指向同一北京交易日却产生不同时间戳；统一按北京时区归一到当天 00:00 再 join，
    # 否则两表错位、adj_factor 失配、复权完全失效（会用原价）
    daily["trade_date"] = (
        pd.to_datetime(daily["trade_date"], utc=True)
        .dt.tz_convert("Asia/Shanghai").dt.tz_localize(None).dt.normalize()
    )
    adj["trade_date"] = (
        pd.to_datetime(adj["trade_date"], utc=True)
        .dt.tz_convert("Asia/Shanghai").dt.tz_localize(None).dt.normalize()
    )

    df = daily.merge(adj, on=["ts_code", "trade_date"], how="inner")

    result: dict[str, list[BarData]] = {}
    for ts_code, g in df.groupby("ts_code"):
        if ts_code in st_codes:
            continue

        g = g.sort_values("trade_date").reset_index(drop=True).copy()

        # 剔除停牌（OHLC 全 0）
        suspended = (
            (g["open"] == 0) & (g["high"] == 0)
            & (g["low"] == 0) & (g["close"] == 0)
        )
        g = g[~suspended]
        if len(g) < C.MIN_BARS:
            continue

        # 前复权：以区间末端 adj 为基准（OHLC 复权，volume 不动）
        adj_last = float(g["adj_factor"].iloc[-1])
        ratio = g["adj_factor"].astype(float).to_numpy() / adj_last
        for col in ("open", "high", "low", "close"):
            g[col] = g[col].astype(float).to_numpy() * ratio

        symbol, exchange = split_ts_code(ts_code)
        lim_pct = _limit_ratio(symbol) * 100  # 百分比

        bars: list[BarData] = []
        for row in g.itertuples(index=False):
            pct = float(row.pct_chg) if pd.notna(row.pct_chg) else 0.0
            bar = BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=row.trade_date.to_pydatetime(),
                interval=Interval.DAILY,
                open_price=float(row.open),
                high_price=float(row.high),
                low_price=float(row.low),
                close_price=float(row.close),
                volume=float(row.volume),
                gateway_name="BACKTESTING",
            )
            bar.extra = {
                "limit_up": pct >= lim_pct - 0.5,
                "limit_down": pct <= -lim_pct + 0.5,
            }
            bars.append(bar)

        result[ts_code] = bars

    return result


def load_bars(ts_code: str) -> list[BarData]:
    """单只成分股的前复权日线"""
    return load_all_bars([ts_code]).get(ts_code, [])
