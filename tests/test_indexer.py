"""
索引器测试 - 完整实现
"""
import pytest
import os
import sys
import sqlite3
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.indexer.store import DataStore
from src.db.schema import SCHEMA_SQL


class TestDataStore:
    """数据存储测试"""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """创建临时数据库（使用真实 schema）"""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 使用真实的 schema
        cursor.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()
        
        return str(db_path)
    
    def test_init(self, temp_db):
        """测试初始化"""
        store = DataStore(temp_db)
        assert store.db_path == temp_db
    
    def test_get_connection(self, temp_db):
        """测试获取数据库连接"""
        store = DataStore(temp_db)
        conn = store._get_conn()
        assert conn is not None
        conn.close()
    
    def test_upsert_market(self, temp_db):
        """测试插入/更新市场"""
        store = DataStore(temp_db)
        
        # 使用与真实 schema 匹配的字段
        market_data = {
            "slug": "test-market",
            "condition_id": "0x" + "a" * 64,
            "question_id": "0x" + "b" * 64,
            "oracle": "0x" + "c" * 40,
            "collateral_token": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "yes_token_id": "123456789",
            "no_token_id": "987654321",
            "enable_neg_risk": False,
            "outcome_slot_count": 2,
            "status": "active",
            "title": "Test Market Title"
        }
        
        # 插入
        result = store.upsert_market(market_data)
        assert result > 0
        
        # 验证插入
        market = store.fetch_market_by_slug("test-market")
        assert market is not None
        assert market["title"] == "Test Market Title"
    
    def test_upsert_market_update(self, temp_db):
        """测试更新已存在的市场"""
        store = DataStore(temp_db)
        
        market_data = {
            "slug": "update-test-market",
            "condition_id": "0x" + "d" * 64,
            "yes_token_id": "111",
            "no_token_id": "222",
            "title": "Original Title"
        }
        
        # 首次插入
        store.upsert_market(market_data)
        
        # 更新
        market_data["title"] = "Updated Title"
        store.upsert_market(market_data)
        
        # 验证更新
        market = store.fetch_market_by_slug("update-test-market")
        assert market["title"] == "Updated Title"
    
    def test_fetch_market_by_slug(self, temp_db):
        """测试按 slug 获取市场"""
        store = DataStore(temp_db)
        
        market_data = {
            "slug": "fetch-test-market",
            "condition_id": "0x" + "e" * 64,
            "yes_token_id": "333",
            "no_token_id": "444",
            "title": "Fetch Test"
        }
        store.upsert_market(market_data)
        
        # 查询存在的市场
        market = store.fetch_market_by_slug("fetch-test-market")
        assert market is not None
        assert market["title"] == "Fetch Test"
        
        # 查询不存在的市场
        not_found = store.fetch_market_by_slug("non-existent-market")
        assert not_found is None
    
    def test_fetch_market_by_condition_id(self, temp_db):
        """测试按 condition_id 获取市场"""
        store = DataStore(temp_db)
        
        condition_id = "0x" + "f" * 64
        market_data = {
            "slug": "condition-test",
            "condition_id": condition_id,
            "yes_token_id": "555",
            "no_token_id": "666"
        }
        store.upsert_market(market_data)
        
        market = store.fetch_market_by_condition_id(condition_id)
        assert market is not None
        assert market["slug"] == "condition-test"
    
    def test_fetch_market_by_token_id(self, temp_db):
        """测试按 token_id 获取市场"""
        store = DataStore(temp_db)
        
        market_data = {
            "slug": "token-test",
            "condition_id": "0x" + "1" * 64,
            "yes_token_id": "yes_token_999",
            "no_token_id": "no_token_888"
        }
        store.upsert_market(market_data)
        
        # 通过 YES token 查询
        market_yes = store.fetch_market_by_token_id("yes_token_999")
        assert market_yes is not None
        
        # 通过 NO token 查询
        market_no = store.fetch_market_by_token_id("no_token_888")
        assert market_no is not None
    
    def test_sync_state_operations(self, temp_db):
        """测试同步状态操作"""
        store = DataStore(temp_db)
        
        # 初始状态
        state = store.get_sync_state()
        assert state["last_block"] == 0
        
        # 更新状态
        store.update_sync_state(100000, total_trades=500)
        
        # 验证更新
        state = store.get_sync_state()
        assert state["last_block"] == 100000
        assert state["total_trades"] == 500
    
    def test_upsert_event(self, temp_db):
        """测试事件插入"""
        store = DataStore(temp_db)
        
        event_data = {
            "slug": "test-event",
            "title": "Test Event Title",
            "description": "Test Description",
            "neg_risk": False,
            "status": "active"
        }
        
        result = store.upsert_event(event_data)
        assert result > 0
        
        # 验证
        event = store.fetch_event_by_slug("test-event")
        assert event is not None
        assert event["title"] == "Test Event Title"


class TestDataStoreTraderProfiles:
    """交易者画像测试"""
    
    @pytest.fixture
    def store_with_data(self, tmp_path):
        """创建带数据的测试存储"""
        db_path = tmp_path / "test_profiles.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()
        
        return DataStore(str(db_path))
    
    def test_trader_profiles_table_exists(self, store_with_data):
        """测试交易者画像表存在"""
        store = store_with_data
        
        # 验证可以查询 trader_profiles 表
        conn = store._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trader_profiles'")
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert result[0] == 'trader_profiles'


class TestIndexerIntegration:
    """索引器集成测试"""
    
    def test_indexer_imports(self):
        """测试索引器模块导入"""
        from src.indexer.run import PolymarketIndexer
        from src.indexer.store import DataStore
        from src.indexer.gamma import GammaAPIClient
        
        assert PolymarketIndexer is not None
        assert DataStore is not None
        assert GammaAPIClient is not None
    
    def test_gamma_client_init(self):
        """测试 GammaAPIClient 初始化"""
        from src.indexer.gamma import GammaAPIClient
        
        client = GammaAPIClient()
        assert client.base_url == "https://gamma-api.polymarket.com"
    
    def test_datastore_constants(self):
        """测试 DataStore 常量"""
        from src.indexer.store import DataStore
        
        # 验证类存在必要方法
        assert hasattr(DataStore, 'upsert_market')
        assert hasattr(DataStore, 'fetch_market_by_slug')
        assert hasattr(DataStore, 'get_sync_state')
        assert hasattr(DataStore, 'update_sync_state')


class TestSchemaValidation:
    """Schema 验证测试"""
    
    def test_schema_creates_all_tables(self, tmp_path):
        """测试 schema 创建所有必要表"""
        db_path = tmp_path / "schema_test.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.executescript(SCHEMA_SQL)
        conn.commit()
        
        # 检查所有表是否创建
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {'events', 'markets', 'trades', 'sync_state', 'trader_profiles'}
        assert expected_tables.issubset(tables)
        
        conn.close()
    
    def test_markets_table_columns(self, tmp_path):
        """测试 markets 表包含必要列"""
        db_path = tmp_path / "columns_test.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.executescript(SCHEMA_SQL)
        conn.commit()
        
        cursor.execute("PRAGMA table_info(markets)")
        columns = {row[1] for row in cursor.fetchall()}
        
        required = {'id', 'slug', 'condition_id', 'yes_token_id', 'no_token_id'}
        assert required.issubset(columns)
        
        conn.close()


# 允许直接运行
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
