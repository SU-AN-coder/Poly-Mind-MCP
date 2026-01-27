"""
数据库Schema定义
"""
import sqlite3
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def init_db(db_path: str) -> sqlite3.Connection:
    """初始化数据库"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建表
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug VARCHAR UNIQUE,
            title VARCHAR,
            description TEXT,
            status VARCHAR,
            created_at TIMESTAMP,
            UNIQUE(slug)
        );
        
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            slug VARCHAR UNIQUE,
            condition_id VARCHAR,
            question_id VARCHAR,
            oracle VARCHAR,
            collateral_token VARCHAR,
            yes_token_id VARCHAR,
            no_token_id VARCHAR,
            enable_neg_risk BOOLEAN,
            status VARCHAR,
            created_at TIMESTAMP,
            UNIQUE(condition_id),
            FOREIGN KEY(event_id) REFERENCES events(id)
        );
        
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id INTEGER,
            tx_hash VARCHAR,
            log_index INTEGER,
            maker VARCHAR,
            taker VARCHAR,
            side VARCHAR,
            outcome VARCHAR,
            price DECIMAL,
            size DECIMAL,
            timestamp TIMESTAMP,
            UNIQUE(tx_hash, log_index),
            FOREIGN KEY(market_id) REFERENCES markets(id)
        );
        
        CREATE TABLE IF NOT EXISTS sync_state (
            key VARCHAR PRIMARY KEY,
            last_block INTEGER,
            updated_at TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_trades_market_id ON trades(market_id);
        CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
        CREATE INDEX IF NOT EXISTS idx_markets_condition_id ON markets(condition_id);
        """)
        
        conn.commit()
        logger.info(f"数据库初始化成功: {db_path}")
        return conn
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


def get_connection(db_path: str) -> sqlite3.Connection:
    """获取数据库连接"""
    return sqlite3.connect(db_path)
