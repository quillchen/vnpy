"""
CPO 海龟策略回测 —— 集中配置
"""

from pathlib import Path

# ============ 数据源 ============
SQLITE_PATH: str = r"D:\VSCodeProjects\stka\backend\data\sqlite_db.db"
QUESTDB_HOST: str = "127.0.0.1"
QUESTDB_HTTP_PORT: int = 9000

# ============ 标的 ============
SECTOR_CODE: str = "886033.TI"          # 同花顺：共封装光学(CPO)

# ============ 回测区间 ============
BT_START: str = "2022-01-01"            # 回测统计起点（含）
BT_END: str = "2025-12-31"              # 回测结束（含）
WARMUP_DAYS: int = 90                   # start 前预热日历日，确保指标在起点前已 inited
MIN_BARS: int = 100                     # 成分股最少有效交易日，不足则跳过

# ============ 资金 / 费用（A股） ============
TOTAL_CAPITAL: float = 10_000_000       # 组合总资金
RATE: float = 0.0008                    # 综合费率：佣金万2.5双边 + 印花税千1卖出(近似均摊)
SLIPPAGE: float = 0.01                  # 每股滑点（元）
SIZE: float = 1                         # 股票合约乘数
PRICETICK: float = 0.01                 # A股最小价位
MIN_VOLUME: float = 100                 # 最小交易单位（股，1手）

# ============ 海龟参数 ============
ENTRY_WINDOW: int = 20                  # 入场唐奇安通道（N日最高）
EXIT_WINDOW: int = 10                   # 离场唐奇安通道（N日最低）
ATR_WINDOW: int = 20                    # ATR 计算窗口
RISK_PERCENT: float = 0.01              # 单笔风险占该票分配资金的比例（1%）
MAX_UNITS: int = 4                      # 最大分批建仓单元数
ATR_STOP_MULT: float = 2.0             # 止损 = 入场价 - ATR_STOP_MULT × ATR
AM_SIZE: int = 50                       # ArrayManager 容量

# ============ 输出 ============
OUTPUT_DIR: Path = Path(__file__).parent
RESULT_CSV: str = "result_per_symbol.csv"
