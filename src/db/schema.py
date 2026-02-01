"""
数据库 Schema 定义
"""
import os
import sqlite3
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "data/polymarket.db")

# 完整的 Schema SQL（用于测试）
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id TEXT UNIQUE,
    slug TEXT,
    question TEXT,
    description TEXT,
    yes_token_id TEXT,
    no_token_id TEXT,
    volume REAL DEFAULT 0,
    liquidity REAL DEFAULT 0,
    yes_price REAL DEFAULT 0.5,
    no_price REAL DEFAULT 0.5,
    active INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT,
    log_index INTEGER DEFAULT 0,
    maker TEXT,
    taker TEXT,
    side TEXT,
    outcome TEXT,
    price REAL,
    maker_amount TEXT,
    taker_amount TEXT,
    block_number INTEGER,
    timestamp TEXT,
    market_slug TEXT,
    UNIQUE(tx_hash, log_index)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE,
    title TEXT,
    slug TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY,
    last_block INTEGER DEFAULT 0,
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trader_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT UNIQUE,
    trade_count INTEGER DEFAULT 0,
    total_volume REAL DEFAULT 0,
    win_rate REAL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS traders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT UNIQUE,
    first_seen TEXT,
    last_seen TEXT,
    trade_count INTEGER DEFAULT 0,
    total_volume REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS indexer_state (
    id INTEGER PRIMARY KEY,
    last_block INTEGER DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """获取数据库连接"""
    path = db_path or DB_PATH
    
    # 确保目录存在
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None):
    """初始化数据库"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def reset_db(db_path: Optional[str] = None):
    """重置数据库"""
    path = db_path or DB_PATH
    if os.path.exists(path):
        os.remove(path)
    init_db(path)


def migrate_db(db_path: Optional[str] = None):
    """迁移数据库"""
    init_db(db_path)
