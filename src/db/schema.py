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
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


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


def add_column_if_not_exists(cursor, table_name: str, column_name: str, column_type: str):
    """安全地添加列（如果不存在）"""
    columns = get_table_columns(cursor, table_name)
    if column_name not in columns:
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            print(f"   ✅ 添加列: {table_name}.{column_name}")
            return True
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                print(f"   ⚠️ 添加列失败: {table_name}.{column_name} - {e}")
    return False


def init_db(db_path: Optional[str] = None):
    """
    初始化数据库
    - 创建不存在的表
    - 安全地添加缺失的列
    - 创建索引
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    print("   初始化数据库...")
    
    # =========================================================================
    # 创建 markets 表（完整结构）
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT,
            condition_id TEXT UNIQUE,
            slug TEXT,
            question_id TEXT,
            oracle TEXT,
            collateral_token TEXT,
            yes_token_id TEXT,
            no_token_id TEXT,
            enable_neg_risk INTEGER DEFAULT 0,
            outcome_slot_count INTEGER DEFAULT 2,
            status TEXT DEFAULT 'active',
            title TEXT,
            question TEXT,
            description TEXT,
            category TEXT,
            volume REAL DEFAULT 0,
            liquidity REAL DEFAULT 0,
            yes_price REAL DEFAULT 0.5,
            no_price REAL DEFAULT 0.5,
            end_date TEXT,
            active INTEGER DEFAULT 1,
            closed INTEGER DEFAULT 0,
            resolved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 添加 markets 表缺失的列
    if table_exists(cursor, 'markets'):
        markets_columns = {
            'volume': 'REAL DEFAULT 0',
            'liquidity': 'REAL DEFAULT 0',
            'yes_price': 'REAL DEFAULT 0.5',
            'no_price': 'REAL DEFAULT 0.5',
            'question': 'TEXT',
            'description': 'TEXT',
            'category': 'TEXT',
            'end_date': 'TEXT',
            'active': 'INTEGER DEFAULT 1',
            'closed': 'INTEGER DEFAULT 0',
            'resolved': 'INTEGER DEFAULT 0',
        }
        for col_name, col_type in markets_columns.items():
            add_column_if_not_exists(cursor, 'markets', col_name, col_type)
    
    # =========================================================================
    # 创建 trades 表
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_hash TEXT,
            log_index INTEGER DEFAULT 0,
            exchange TEXT,
            order_hash TEXT,
            block_number INTEGER,
            timestamp TEXT,
            maker TEXT,
            taker TEXT,
            maker_asset_id TEXT,
            taker_asset_id TEXT,
            maker_amount TEXT,
            taker_amount TEXT,
            fee TEXT,
            fee_amount TEXT,
            side TEXT,
            outcome TEXT,
            price REAL,
            size REAL,
            token_id TEXT,
            condition_id TEXT,
            market_slug TEXT,
            market_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tx_hash, log_index)
        )
    """)
    
    # 添加 trades 表缺失的列
    if table_exists(cursor, 'trades'):
        trades_columns = {
            'exchange': 'TEXT',
            'order_hash': 'TEXT',
            'maker_asset_id': 'TEXT',
            'taker_asset_id': 'TEXT',
            'fee': 'TEXT',
            'fee_amount': 'TEXT',
            'market_slug': 'TEXT',
            'market_id': 'INTEGER',
            'outcome': 'TEXT',
            'price': 'REAL',
            'size': 'REAL',
            'log_index': 'INTEGER DEFAULT 0',
            'condition_id': 'TEXT',
            'token_id': 'TEXT',
        }
        for col_name, col_type in trades_columns.items():
            add_column_if_not_exists(cursor, 'trades', col_name, col_type)
    
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
            total_trades INTEGER DEFAULT 0,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # =========================================================================
    # 创建索引
    # =========================================================================
    # trades 索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_tx_hash ON trades(tx_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_maker ON trades(maker)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_taker ON trades(taker)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_block ON trades(block_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_market_slug ON trades(market_slug)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_token_id ON trades(token_id)")
    
    # markets 索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_markets_slug ON markets(slug)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_markets_condition ON markets(condition_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_markets_yes_token ON markets(yes_token_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_markets_no_token ON markets(no_token_id)")
    
    # trader_profiles 索引
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
        print(f"   ⚠️ 已删除数据库: {path}")
    init_db(path)


def migrate_db(db_path: Optional[str] = None):
    """迁移数据库 - 添加缺失的列"""
    print("   开始数据库迁移...")
    init_db(db_path)  # init_db 会安全地添加缺失的列
    print("   ✅ 数据库迁移完成")


def get_last_indexed_block(db_path: Optional[str] = None) -> int:
    """获取最后索引的区块号"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_block FROM indexer_state WHERE id = 1")
        row = cursor.fetchone()
        return row[0] if row else 0
    except:
        return 0
    finally:
        conn.close()


def set_last_indexed_block(block_number: int, db_path: Optional[str] = None):
    """设置最后索引的区块号"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO indexer_state (id, last_block, last_update)
        VALUES (1, ?, CURRENT_TIMESTAMP)
    """, (block_number,))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("初始化/迁移数据库...")
    init_db()
    print("完成！")
