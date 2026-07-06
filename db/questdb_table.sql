##目标db
### QuestDB 9.3.3 连接信息

| 项目 | 值 |
|------|-----|
| Host | 127.0.0.1 |
| HTTP REST API | 9000 |
| HTTP 接口 | http://127.0.0.1:9000/exec |
| Ingress 协议 | http::addr=127.0.0.1:9000 |
| ILP 端口 | 9009 |
| PostgreSQL Wire | 8812 |

#### 端口说明
| 端口 | 协议 | 用途 |
|------|------|------|
| 8812 | PostgreSQL | PostgreSQL Wire Protocol (SQL 查询) |
| 9000 | HTTP | REST API (查询/写入) |
| 9009 | ILP | InfluxDB Line Protocol (高性能写入) |

-- 股票日线行情表（QuestDB）
-- 数据来源：tushare daily + daily_basic 接口合并
-- 指定时间戳：trade_date，按年分区，按 (ts_code, trade_date) 去重
CREATE TABLE IF NOT EXISTS stock_daily (
    ts_code         SYMBOL INDEX CAPACITY 8192,  -- TS股票代码，如 000001.SZ
    trade_date      TIMESTAMP,                    -- 交易日期，指定时间戳
    open            FLOAT,                        -- 开盘价
    high            FLOAT,                        -- 最高价
    low             FLOAT,                        -- 最低价
    close           FLOAT,                        -- 收盘价（未复权）
    volume          FLOAT,                        -- 成交量（手）
    amount          FLOAT,                        -- 成交额（千元）
    change          FLOAT,                        -- 涨跌额 = close - pre_close
    pct_chg         FLOAT,                        -- 涨跌幅（%）= (close - pre_close) / pre_close * 100
    turnover_rate   FLOAT,                        -- 换手率（%），来源 daily_basic
    turnover_rate_f FLOAT,                        -- 换手率-自由流通股（%），来源 daily_basic
    total_share     FLOAT,                        -- 总股本（万股），来源 daily_basic
    float_share     FLOAT,                        -- 流通股本（万股），来源 daily_basic
    free_share      FLOAT,                        -- 自由流通股本（万股），来源 daily_basic
    pe_ttm          FLOAT,                        -- 市盈率TTM，亏损时为空，来源 daily_basic
    net_amount      FLOAT                         -- 个股资金净流入（元），来源 moneyflow_dc（暂不采集）
) timestamp(trade_date) PARTITION BY YEAR
  DEDUP UPSERT KEYS(ts_code, trade_date);

-- ST股票列表表（QuestDB）
-- 数据来源：tushare stock_st 接口
-- 记录每日ST/*ST/退市整理等特殊处理股票，按年分区，按 (ts_code, trade_date) 去重
CREATE TABLE IF NOT EXISTS stock_st (
    ts_code     SYMBOL INDEX CAPACITY 8192,  -- TS股票代码，如 000001.SZ
    name        STRING,                      -- 股票名称，如 *ST平安
    trade_date  TIMESTAMP,                   -- 交易日期，指定时间戳
    type        SYMBOL,                      -- ST类型代码
    type_name   STRING                       -- ST类型名称，如 ST/*ST/退市整理等
) TIMESTAMP(trade_date) PARTITION BY YEAR
  DEDUP UPSERT KEYS(ts_code, trade_date);

-- 股票复权因子表（QuestDB）
-- 数据来源：tushare adj_factor 接口
-- 指定时间戳：trade_date，按年分区，按 (ts_code, trade_date) 去重
CREATE TABLE IF NOT EXISTS stock_adj_factor (
    ts_code     SYMBOL INDEX CAPACITY 8192,  -- TS股票代码，如 000001.SZ
    trade_date  TIMESTAMP,                    -- 交易日期，指定时间戳
    adj_factor  FLOAT                         -- 复权因子
) TIMESTAMP(trade_date) PARTITION BY YEAR
  DEDUP UPSERT KEYS(ts_code, trade_date);

-- 个股资金流向表（QuestDB）
-- 数据来源：tushare moneyflow（2010年起）+ moneyflow_dc（20230911起）
-- dc_ 前缀字段来自 moneyflow_dc，其余来自 moneyflow
-- 2022年及之前 dc_ 字段为空，仅 moneyflow 有数据
-- 指定时间戳：trade_date，按年分区，按 (ts_code, trade_date) 去重
CREATE TABLE IF NOT EXISTS stock_daily_flow (
    ts_code              SYMBOL INDEX CAPACITY 8192,  -- TS股票代码，如 000001.SZ
    trade_date           TIMESTAMP,                    -- 交易日期，指定时间戳
    dc_net_amount        FLOAT,                        -- 主力净流入额（万元），来源 moneyflow_dc
    dc_net_amount_rate   FLOAT,                        -- 主力净流入净占比（%），来源 moneyflow_dc
    dc_buy_elg_amount    FLOAT,                        -- 超大单净流入额（万元），来源 moneyflow_dc
    dc_buy_elg_amount_rate FLOAT,                      -- 超大单净流入占比（%），来源 moneyflow_dc
    dc_buy_lg_amount     FLOAT,                        -- 大单净流入额（万元），来源 moneyflow_dc
    dc_buy_lg_amount_rate FLOAT,                       -- 大单净流入占比（%），来源 moneyflow_dc
    net_mf_amount        FLOAT,                        -- 净流入额（万元），来源 moneyflow
    sell_elg_amount      FLOAT,                        -- 特大单卖出金额（万元），来源 moneyflow
    buy_elg_amount       FLOAT,                        -- 特大单买入金额（万元），来源 moneyflow
    sell_lg_amount       FLOAT,                        -- 大单卖出金额（万元），来源 moneyflow
    buy_lg_amount        FLOAT,                        -- 大单买入金额（万元），来源 moneyflow
    sell_md_amount       FLOAT,                        -- 中单卖出金额（万元），来源 moneyflow
    buy_md_amount        FLOAT,                        -- 中单买入金额（万元），来源 moneyflow
    sell_sm_amount       FLOAT,                        -- 小单卖出金额（万元），来源 moneyflow
    buy_sm_amount        FLOAT                         -- 小单买入金额（万元），来源 moneyflow
) TIMESTAMP(trade_date) PARTITION BY YEAR
  DEDUP UPSERT KEYS(ts_code, trade_date);

-- 888882指数分钟表
CREATE TABLE 'index_a_min' (
	idx_code SYMBOL INDEX CAPACITY 64,
	time TIMESTAMP,
	open_pct FLOAT,
	close_pct FLOAT,
	high_pct FLOAT,
	low_pct FLOAT,
	open_idx FLOAT,
	close_idx FLOAT,
	high_idx FLOAT,
	low_idx FLOAT,
	weight_close_pct FLOAT,
	weight_close_idx FLOAT,
	amount FLOAT,
	volume FLOAT,
	turnover_rate_f FLOAT
) timestamp(time) PARTITION BY DAY
DEDUP UPSERT KEYS(idx_code,time);

-- 888882指数分钟资金流向表
-- 数据来源：数据源库 stock_flow_min_hist_{year} 聚合 + 目标库 stock_daily 的 float_share
-- main/super/big/med/small_net_flow 为成分股合计(Σ)；buy/sell_amount 为 (个股值/float_share) 的成分股均值
-- excluded_set 冻结于基准日 20220104，float_share 取前一交易日，与 index_a_min 保持一致
-- 指定时间戳：time，按日分区，按 (idx_code, time) 去重
CREATE TABLE IF NOT EXISTS index_a_flow_min (
    idx_code        SYMBOL INDEX CAPACITY 64,   -- 指数代码，固定 888882
    time           TIMESTAMP,                   -- 分钟时间戳（北京墙钟标记 Z）
    main_net_flow  FLOAT,                       -- 主力净流入额合计（Σ 成分股）
    super_net_flow FLOAT,                       -- 超大单净流入额合计（Σ 成分股）
    big_net_flow   FLOAT,                       -- 大单净流入额合计（Σ 成分股）
    med_net_flow   FLOAT,                       -- 中单净流入额合计（Σ 成分股）
    small_net_flow FLOAT,                       -- 小单净流入额合计（Σ 成分股）
    buy_amount     FLOAT,                       -- 均值( buy_amount / float_share )
    sell_amount    FLOAT                        -- 均值( sell_amount / float_share )
) timestamp(time) PARTITION BY DAY
DEDUP UPSERT KEYS(idx_code, time);

-- 指数分钟表
CREATE TABLE 'index_min_hist' (
	idx_code SYMBOL INDEX CAPACITY 64,
	time TIMESTAMP,
	close FLOAT,
	pct_chg FLOAT,
	volume FLOAT,
	amount FLOAT
) timestamp(time) PARTITION BY DAY
DEDUP UPSERT KEYS(idx_code,time);

-- 核心宽基指数分钟表（原始归档数据）
-- 数据来源：本地归档 1分钟_按月归档指数/{YYYY-MM}/YYYYMMDD_1min.zip 内按指数代码命名的 CSV
-- CSV 列：时间,代码,名称,开盘价,收盘价,最高价,最低价,成交额,涨幅,振幅（UTF-8-BOM，无成交量）
-- 导入脚本：gather_hist/gather_index_min_raw.py（2010-01 ~ 2025-12，TARGET_CODES 核心宽基）
-- idx_name 取数据源原值（深证系列 399xxx 仅代码）；time 为北京墙钟直接标记 Z（与 stock_min_{year} 一致）
-- 指定时间戳：time，按日分区，按 (idx_code, time) 去重
CREATE TABLE 'index_min_raw' (
	idx_code SYMBOL INDEX CAPACITY 256,   -- 指数代码 000001/000300/399001...
	idx_name STRING,                        -- 指数名称（数据源原值）
	time TIMESTAMP,                         -- 分钟时间戳（北京墙钟直接标记 Z, 09:30~15:00）
	open FLOAT,                             -- 开盘价
	high FLOAT,                             -- 最高价
	low FLOAT,                              -- 最低价
	close FLOAT,                            -- 收盘价
	amount DOUBLE,                          -- 成交额（元），DOUBLE 精确保真（百亿级 float32 会丢精度）
	pct_chg FLOAT,                          -- 涨幅（%）
	amplitude FLOAT                         -- 振幅（%）
) timestamp(time) PARTITION BY DAY
DEDUP UPSERT KEYS(idx_code,time);

-- 888882指数分钟表（OHLC + 加权OHLC，不含 pct）
-- index_astk_min = index_a_min 的演进版：
--   1. 去掉 *_pct 字段——pct 可由指数间接还原，例如 open_pct = (open_idx - prev_idx)/prev_idx*100，
--      故用 open_idx + prev_idx 即可"间接保存" open_pct，无需单独落库
--   2. 新增 prev_idx / weight_prev_idx：前一交易日收盘指数（全天常数，链式基准）
--   3. 加权指数由原来仅 weight_close_idx 扩展为完整 OHLC（open/high/low）
-- 平权 idx = 前一交易日平权收盘 * (1 + 等权pct/100)
-- 加权 idx = 前一交易日加权收盘 * (1 + Σ(pct*float_share)/Σ(float_share)/100)
-- excluded_set 冻结于基准日 20220104，float_share 取前一交易日，与 index_a_min 一致
-- 指定时间戳：time，按日分区，按 (idx_code, time) 去重
CREATE TABLE 'index_astk_min' (
	idx_code SYMBOL INDEX CAPACITY 64,
	time TIMESTAMP,
	open_idx FLOAT, --平权指数
	close_idx FLOAT,
	high_idx FLOAT,
	low_idx FLOAT,
	prev_idx FLOAT, --前一个交易日收盘指数
	weight_open_idx FLOAT, --加权指数
	weight_close_idx FLOAT,
	weight_high_idx FLOAT,
	weight_low_idx FLOAT,
	weight_prev_idx FLOAT, --前一个交易日收盘指数（加权）
	amount FLOAT,
	volume FLOAT,
	turnover_rate_f FLOAT
) timestamp(time) PARTITION BY DAY
DEDUP UPSERT KEYS(idx_code,time);

-- A股指数日线行情表（QuestDB 目标库）
-- 数据来源：akshare stock_zh_index_daily(symbol=...) 接口（新浪源）
-- symbol 如 sh000001(上证指数) / sz399001(深证成指)，一次返回全量历史
-- 指定时间戳：trade_date，北京日期 T00:00 直接标记 Z（与 stock_daily 一致，墙钟口径）
-- 按年分区，按 (idx_code, trade_date) 去重；导入脚本：gather_hist/gather_index_a_daily.py
CREATE TABLE IF NOT EXISTS index_a_daily (
    idx_code    SYMBOL INDEX CAPACITY 64,   -- 指数代码（akshare 原值，如 sh000001）
    trade_date  TIMESTAMP,                   -- 交易日期，指定时间戳（北京墙钟标记 Z）
    open        FLOAT,                       -- 开盘价
    high        FLOAT,                       -- 最高价
    low         FLOAT,                       -- 最低价
    close       FLOAT,                       -- 收盘价
    volume      LONG                         -- 成交量（akshare 原值整数，手）
) timestamp(trade_date) PARTITION BY YEAR
DEDUP UPSERT KEYS(idx_code, trade_date);


##数据源db
### QuestDB 9.4.0 连接信息

| 项目 | 值 |
|------|-----|
| Host | 127.0.0.1 |
| HTTP REST API | 29000 |
| HTTP 接口 | http://127.0.0.1:29000/exec |
| Ingress 协议 | http::addr=127.0.0.1:29000 |
| ILP 端口 | 29009 |
| PostgreSQL Wire | 28812 |

--股票分钟表
CREATE TABLE 'stock_min_2022' ( 
	ts_code SYMBOL INDEX CAPACITY 8192,
	open FLOAT,
	high FLOAT,
	low FLOAT,
	close FLOAT,
	amount FLOAT,
	volume LONG,
	time TIMESTAMP
) timestamp(time) PARTITION BY DAY
DEDUP UPSERT KEYS(ts_code,time);

