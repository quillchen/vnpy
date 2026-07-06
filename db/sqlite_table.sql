-- sqlite: D:\VSCodeProjects\stka\backend\data\sqlite_db.db

-- 交易日历表
-- 数据来源：tushare trade_cal 接口
-- 包含各大交易所的交易日历数据
create table trader_calendar
(
    id             INTEGER  primary key autoincrement,  -- 自增主键
    exchange       TEXT     not null,                    -- 交易所：SSE上交所 SZSE深交所 CFFEX中金所 SHFE上期所 CZCE郑商所 DCE大商所 INE上能源
    cal_date       TEXT     not null,                    -- 日历日期，如 20200101
    is_open        TEXT     not null,                    -- 是否交易：0休市 1交易
    pretrade_date  TEXT,                                 -- 上一个交易日
    UNIQUE(exchange, cal_date)
);

-- 股票基础信息表
-- 数据来源：tushare stock_basic 接口
-- 包含所有上市状态（L上市/D退市/P暂停上市/G未交易）的股票
create table stock_all
(
    id          INTEGER  primary key autoincrement,  -- 自增主键，按symbol从小到大排序
    ts_code     TEXT not null unique,                -- TS股票代码，如 000001.SZ
    symbol      TEXT not null,                       -- 股票代码，如 000001
    name        TEXT not null,                       -- 股票名称，如 平安银行
    area        TEXT,                                -- 地域，如 深圳
    industry    TEXT,                                -- 所属行业，如 银行
    market      TEXT,                                -- 市场类型（主板/创业板/科创板/CDR/北交所）
    exchange    TEXT,                                -- 交易所：SSE上交所 SZSE深交所 BSE北交所
    list_date   TEXT,                                -- 上市日期，如 19910403
    delist_date TEXT,                                -- 退市日期，未退市为空
    is_hs       TEXT,                                -- 是否沪深港通标的：N否 H沪股通 S深股通
    list_status TEXT,                                -- 上市状态：L上市 D退市 P暂停上市 G未交易
    is_st       INTEGER default 0                    -- 是否ST：0否 1是
);

--同花顺板块表
sector_ths_info 

--同花顺板块成分表
sector_ths_item

-- 模型特征信息表
-- 登记每个候选特征的元数据、归属训练目标与训练方式、校验状态、版本
-- 特征新增/变更通过 run_train 自动同步：已存在则 upsert 并 version+1，代码中删除则标 deprecated（不物理删除）
create table model_feature
(
    id                 INTEGER primary key autoincrement,  -- 自增主键
    feature_key        TEXT    not null,                   -- 特征标识，如 idx_ret_1d（对应 define_features.FeatureDef.name）
    feature_name       TEXT,                               -- 中文描述，如 过去1日涨跌幅(%)
    category           TEXT,                               -- 特征类别：A指数统计 B市场微观结构 C分钟高频 D日历效应 E外盘领先指标(NK225)
    formula_desc       TEXT,                               -- 公式伪代码描述
    data_source        TEXT,                               -- 数据源表，如 index_a_min_daily
    window             TEXT,                               -- 窗口参数，如 20d
    is_dimensionless   INTEGER default 1,                  -- 是否无量纲：0否 1是
    is_look_ahead_safe INTEGER default 1,                  -- 是否无未来函数：0否 1是
    target             TEXT    not null,                   -- 训练目标，如 888882_5class（888882指数5段预测）
    algo               TEXT    not null,                   -- 训练方式/算法，如 xgboost
    status             TEXT    not null default 'active',  -- 状态：active生效 inactive未通过校验 deprecated已废弃
    validation_pass    INTEGER,                            -- 是否通过特征校验：0否 1是（来自 feature_validation_report.csv）
    version            INTEGER not null default 1,         -- 版本号，元数据变更时递增
    updated_at         TEXT,                               -- 最后同步时间（本地时间 yyyy-MM-dd HH:mm:ss）
    remark             TEXT,                               -- 备注
    UNIQUE(feature_key, target, algo)                      -- 同一特征在同一 目标+算法 下唯一
);

-- 训练记录表
-- 每次 run_train 写入一行：使用的特征、数据范围、超参、结果指标、产出文件、时间
create table train_log
(
    id                 INTEGER primary key autoincrement,  -- 自增主键
    train_id           TEXT    not null,                   -- 训练唯一编号（时间戳+短随机后缀，如 20260616_023715_a3f2）
    target             TEXT    not null,                   -- 训练目标，如 888882_5class
    algo               TEXT    not null,                   -- 训练方式，如 xgboost
    features_used      TEXT,                               -- 本次使用特征列表（JSON 数组，如 ["idx_ret_1d","min_position"]）
    n_features         INTEGER,                            -- 使用特征数
    n_train            INTEGER,                            -- 训练样本数
    n_test             INTEGER,                            -- 测试样本数
    train_start        TEXT,                               -- 训练集起始交易日 yyyy-MM-dd
    train_end          TEXT,                               -- 训练集结束交易日 yyyy-MM-dd
    test_start         TEXT,                               -- 测试集起始交易日 yyyy-MM-dd
    test_end           TEXT,                               -- 测试集结束交易日 yyyy-MM-dd
    label_distribution TEXT,                               -- 标签分布（JSON，如 {"0":147,"1":149,...}）
    params_json        TEXT,                               -- 模型超参（JSON，来自 train.DEFAULT_PARAMS）
    log_loss           REAL,                               -- 测试集对数损失
    accuracy           REAL,                               -- 测试集准确率
    f1_macro           REAL,                               -- 测试集宏F1
    kappa              REAL,                               -- Cohen Kappa
    confusion_matrix   TEXT,                               -- 混淆矩阵（JSON 二维数组 5×5）
    model_path         TEXT,                               -- 模型文件路径
    eval_csv_path      TEXT,                               -- 特征评估CSV路径
    trained_at         TEXT,                               -- 训练时间（本地时间 yyyy-MM-dd HH:mm:ss）
    duration_sec       REAL,                               -- 训练耗时（秒）
    remark             TEXT,                               -- 备注
    UNIQUE(train_id)
);

