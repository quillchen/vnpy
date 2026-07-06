"""
QuestDB 连接工具类

支持两个 QuestDB 实例：
- 数据源 DB (9.4.0): 原始行情数据存储
  - HTTP: 29000, ILP: 29009, PG: 28812
- 目标 DB (9.3.3): 数据聚合后的目标存储
  - HTTP: 9000, ILP: 9009, PG: 8812

使用方式：
  from db.questdb_connect import get_source_client, get_target_client
  source = get_source_client()   # 数据源 (9.4.0)
  target = get_target_client()   # 目标 DB (9.3.3)
"""

import pandas as pd
from questdb.ingress import Sender
import requests
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class QuestDBClient:
    """QuestDB 客户端工具类"""

    def __init__(self, host: str = "127.0.0.1", http_port: int = 9000, ilp_port: int = 9009):
        self.host = host
        self.http_port = http_port
        self.ilp_port = ilp_port

    # ==================== 查询相关 ====================

    def query(self, sql: str) -> pd.DataFrame:
        url = f"http://{self.host}:{self.http_port}/exec"
        params = {"query": sql}
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        columns = [col['name'] for col in data['columns']]
        rows = data['dataset']
        return pd.DataFrame(rows, columns=columns)

    def query_raw(self, sql: str) -> Dict[str, Any]:
        url = f"http://{self.host}:{self.http_port}/exec"
        params = {"query": sql}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def query_csv(self, sql: str) -> pd.DataFrame:
        """通过 /exp (CSV) 端点查询，返回 DataFrame。

        比 /exec (JSON) 快很多，尤其适合大结果集（百万级行）：
        CSV 体积更小、pandas 直接 read_csv 解析，避免 JSON→list→DataFrame 的开销。
        """
        from io import StringIO
        url = f"http://{self.host}:{self.http_port}/exp"
        response = requests.get(url, params={"query": sql})
        response.raise_for_status()
        return pd.read_csv(StringIO(response.text))

    def query_parquet(self, sql: str) -> pd.DataFrame:
        """/exp?fmt=parquet 流式下载到临时文件再 pd.read_parquet（批量查询方式C）。

        列式二进制，是读进 DataFrame 最快的方式，适合大批量结果集（百万级行）。
        参考 D:\\VSCodeProjects\\data_gather\\query_questdb_bulk_demo.py 的方式C。
        同步阻塞：流式写临时文件(1MB 分块) → read_parquet → 删除临时文件。
        依赖 pyarrow（pd.read_parquet 引擎）。
        """
        import os
        import tempfile
        url = f"http://{self.host}:{self.http_port}/exp"
        fd, path = tempfile.mkstemp(suffix=".parquet")
        os.close(fd)
        try:
            with requests.get(url, params={"query": sql, "fmt": "parquet"},
                              stream=True, timeout=600) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1 << 20):   # 1MB 分块写盘
                        f.write(chunk)
            return pd.read_parquet(path)
        finally:
            os.unlink(path)

    # ==================== 写入相关 ====================

    @contextmanager
    def get_sender(self):
        """获取 ILP Sender，优先使用 HTTP 协议"""
        conf = f"http::addr={self.host}:{self.http_port};"
        with Sender.from_conf(conf) as sender:
            yield sender

    def insert_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        at: Optional[str] = None,
        symbols: Optional[List[str]] = None
    ) -> None:
        """通过 HTTP  写入 DataFrame"""
        conf = f"http::addr={self.host}:{self.http_port};"
        with Sender.from_conf(conf) as sender:
            if symbols:
                sender.dataframe(df, table_name=table_name, at=at, symbols=symbols)
            else:
                sender.dataframe(df, table_name=table_name, at=at)

    # ==================== 表管理 ====================

    def create_table(self, sql: str) -> None:
        self.query_raw(sql)

    def drop_table(self, table_name: str, if_exists: bool = True) -> None:
        sql = f"DROP TABLE{' IF EXISTS' if if_exists else ''} {table_name}"
        self.query_raw(sql)

    def table_exists(self, table_name: str) -> bool:
        try:
            self.query(f"SELECT 1 FROM {table_name} LIMIT 1")
            return True
        except Exception:
            return False

    def get_tables(self) -> List[str]:
        df = self.query("SHOW TABLES")
        return df.iloc[:, 0].tolist()

    def get_table_columns(self, table_name: str) -> pd.DataFrame:
        return self.query(f"SHOW COLUMNS FROM {table_name}")


# ==================== 双实例配置 ====================

# 数据源 DB (QuestDB 9.4.0) — 原始行情数据
SOURCE_HOST = "127.0.0.1"
SOURCE_HTTP_PORT = 29000
SOURCE_ILP_PORT = 29009

# 目标 DB (QuestDB 9.3.3) — 数据聚合后的目标存储
TARGET_HOST = "127.0.0.1"
TARGET_HTTP_PORT = 9000
TARGET_ILP_PORT = 9009

# 模块级单例
_source_client: Optional[QuestDBClient] = None
_target_client: Optional[QuestDBClient] = None


def get_source_client() -> QuestDBClient:
    """获取数据源 DB 客户端 (QuestDB 9.4.0, HTTP:29000 / PG:28812)"""
    global _source_client
    if _source_client is None:
        _source_client = QuestDBClient(SOURCE_HOST, SOURCE_HTTP_PORT, SOURCE_ILP_PORT)
    return _source_client


def get_target_client() -> QuestDBClient:
    """获取目标 DB 客户端 (QuestDB 9.3.3, HTTP:9000 / PG:8812)"""
    global _target_client
    _target_client = QuestDBClient(TARGET_HOST, TARGET_HTTP_PORT, TARGET_ILP_PORT)
    return _target_client


# 兼容旧代码：get_client 默认返回数据源客户端
def get_client(host: str = "127.0.0.1", http_port: int = 9000, ilp_port: int = 9009) -> QuestDBClient:
    """获取 QuestDB 客户端，默认连接数据源 DB (9.3.3)"""
    return get_target_client()
