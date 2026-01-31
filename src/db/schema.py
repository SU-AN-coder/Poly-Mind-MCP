"""
数据库 Schema 定义
支持数据库迁移，兼容旧表结构
"""
import os
import sqlite3
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "data/polymarket.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """获取数据库连接"""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return sqlite3.connect(path)


def get_table_columns(cursor, table_name: str) -> set:
    """获取表的所有列名"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def table_exists(cursor, table_name: str) -> bool:
    """检查表是否存在"""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None


def init_db(db_path: Optional[str] = None):
    """
    初始化数据库
    - 创建不存在的表
    - 安全地添加缺失的列
    - 创建索引（仅当列存在时）
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # =========================================================================
    # 创建 markets 表
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_id TEXT UNIQUE,
            slug TEXT UNIQUE,
            question TEXT,
            description TEXT,
            category TEXT,
            yes_token_id TEXT,
            no_token_id TEXT,
            volume REAL DEFAULT 0,
            liquidity REAL DEFAULT 0,
            yes_price REAL DEFAULT 0.5,
            no_price REAL DEFAULT 0.5,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # =========================================================================
    # 创建 trades 表
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_hash TEXT,
            log_index INTEGER DEFAULT 0,
            block_number INTEGER,
            timestamp TEXT,
            maker TEXT,
            taker TEXT,
            side TEXT,
            outcome TEXT,
            price REAL,
            size REAL,
            maker_amount TEXT,
            taker_amount TEXT,
            fee_amount TEXT,
            token_id TEXT,
            condition_id TEXT,
            market_slug TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 检查并添加 trades 表缺失的列
    if table_exists(cursor, 'trades'):
        existing_columns = get_table_columns(cursor, 'trades')
        
        # 需要添加的列及其定义
        columns_to_add = {
            'market_slug': 'TEXT',
            'outcome': 'TEXT',
            'price': 'REAL',
            'size': 'REAL',
            'log_index': 'INTEGER DEFAULT 0',
            'fee_amount': 'TEXT',
            'condition_id': 'TEXT',
        }
        
        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_type}")
                    print(f"   ✅ 添加列: trades.{col_name}")
                except sqlite3.OperationalError:
                    pass  # 列已存在
    
    # =========================================================================
    # 创建 events 表
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            title TEXT,
            slug TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # =========================================================================
    # 创建 trader_profiles 表
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trader_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT UNIQUE,
            trade_count INTEGER DEFAULT 0,
            total_volume REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            avg_position_size REAL DEFAULT 0,
            labels TEXT,
            style TEXT,
            risk_level TEXT,
            first_trade_at TEXT,
            last_trade_at TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # =========================================================================
    # 创建 traders 表（兼容旧版）
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT UNIQUE,
            first_seen TEXT,
            last_seen TEXT,
            trade_count INTEGER DEFAULT 0,
            total_volume REAL DEFAULT 0
        )
    """)
    
    # =========================================================================
    # 创建 sync_state 表
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            id INTEGER PRIMARY KEY,
            last_block INTEGER DEFAULT 0,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # =========================================================================
    # 创建 indexer_state 表
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS indexer_state (
            id INTEGER PRIMARY KEY,
            last_block INTEGER DEFAULT 0,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # =========================================================================
    # 安全创建索引（仅当列存在时）
    # =========================================================================
    if table_exists(cursor, 'trades'):
        columns = get_table_columns(cursor, 'trades')
        
        if 'maker' in columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_maker ON trades(maker)")
        if 'taker' in columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_taker ON trades(taker)")
        if 'block_number' in columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_block ON trades(block_number)")
        if 'market_slug' in columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_market_slug ON trades(market_slug)")
        if 'timestamp' in columns:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
    
    if table_exists(cursor, 'markets'):
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_markets_slug ON markets(slug)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_markets_condition ON markets(condition_id)")
    
    if table_exists(cursor, 'trader_profiles'):
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_address ON trader_profiles(address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_win_rate ON trader_profiles(win_rate)")
    
    conn.commit()
    conn.close()
    
    print("   ✅ 数据库初始化完成")


def reset_db(db_path: Optional[str] = None):
    """重置数据库（危险操作）"""
    path = db_path or DB_PATH
    if os.path.exists(path):
        os.remove(path)
        print(f"   ⚠️ 已删除旧数据库: {path}")
    init_db(db_path)


def get_last_indexed_block(db_path: Optional[str] = None) -> int:
    """获取最后索引的区块号"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # 尝试从 indexer_state 表获取
    try:
        cursor.execute("SELECT last_block FROM indexer_state WHERE id = 1")
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]
    except sqlite3.OperationalError:
        pass
    
    # 尝试从 sync_state 表获取
    try:
        cursor.execute("SELECT last_block FROM sync_state WHERE id = 1")
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]
    except sqlite3.OperationalError:
        pass
    
    conn.close()
    return 0


def set_last_indexed_block(block_number: int, db_path: Optional[str] = None):
    """设置最后索引的区块号"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # 更新 indexer_state 表
    cursor.execute("""
        INSERT INTO indexer_state (id, last_block, last_update) 
        VALUES (1, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET 
            last_block = excluded.last_block,
            last_update = CURRENT_TIMESTAMP
    """, (block_number,))
    
    # 同时更新 sync_state 表（兼容性）
    cursor.execute("""
        INSERT INTO sync_state (id, last_block, last_update) 
        VALUES (1, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET 
            last_block = excluded.last_block,
            last_update = CURRENT_TIMESTAMP
    """, (block_number,))
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
