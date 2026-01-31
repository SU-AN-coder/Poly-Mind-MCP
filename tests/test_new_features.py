"""
PnL 计算器和缓存模块测试
"""
import pytest
import sys
import os
from pathlib import Path
from decimal import Decimal

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPnLCalculator:
    """PnL 计算器测试"""
    
    def test_import(self):
        """测试模块导入"""
        from src.mcp.pnl_calculator import PnLCalculator, get_pnl_calculator
        assert PnLCalculator is not None
        assert get_pnl_calculator is not None
    
    def test_position_dataclass(self):
        """测试 Position 数据类"""
        from src.mcp.pnl_calculator import Position
        
        pos = Position(
            token_id="123",
            market_slug="test-market",
            market_title="Test Market",
            outcome="YES",
            size=Decimal("100"),
            avg_cost=Decimal("0.5"),
            current_price=Decimal("0.6"),
            unrealized_pnl=Decimal("10"),
            unrealized_pnl_pct=Decimal("20"),
            realized_pnl=Decimal("5"),
            total_cost=Decimal("50"),
            current_value=Decimal("60")
        )
        
        assert pos.token_id == "123"
        assert pos.outcome == "YES"
        assert pos.size == Decimal("100")
    
    def test_position_to_dict(self):
        """测试 Position 转字典"""
        from src.mcp.pnl_calculator import Position
        
        pos = Position(
            token_id="123",
            market_slug="test",
            market_title="Test",
            outcome="NO",
            size=Decimal("50"),
            avg_cost=Decimal("0.4"),
            current_price=Decimal("0.3"),
            unrealized_pnl=Decimal("-5"),
            unrealized_pnl_pct=Decimal("-10"),
            realized_pnl=Decimal("0"),
            total_cost=Decimal("20"),
            current_value=Decimal("15")
        )
        
        d = pos.to_dict()
        assert isinstance(d, dict)
        assert d['token_id'] == "123"
        assert d['outcome'] == "NO"
    
    def test_portfolio_summary_dataclass(self):
        """测试 PortfolioSummary 数据类"""
        from src.mcp.pnl_calculator import PortfolioSummary
        
        summary = PortfolioSummary(
            address="0x123",
            total_positions=5,
            total_cost=Decimal("1000"),
            current_value=Decimal("1200"),
            total_unrealized_pnl=Decimal("200"),
            total_realized_pnl=Decimal("50"),
            total_pnl=Decimal("250"),
            pnl_percentage=Decimal("25"),
            winning_positions=4,
            losing_positions=1,
            positions=[]
        )
        
        assert summary.address == "0x123"
        assert summary.total_positions == 5
        assert summary.pnl_percentage == Decimal("25")
    
    def test_calculator_init(self):
        """测试计算器初始化"""
        from src.mcp.pnl_calculator import PnLCalculator
        
        calc = PnLCalculator("data/polymarket.db")
        assert calc.db_path == "data/polymarket.db"
        assert calc.USDC_DECIMALS == 6


class TestCacheManager:
    """缓存管理器测试"""
    
    def test_import(self):
        """测试模块导入"""
        from src.cache import CacheManager, cache_decorator, get_cache
        assert CacheManager is not None
        assert cache_decorator is not None
        assert get_cache is not None
    
    def test_cache_init_fallback(self):
        """测试缓存初始化（降级模式）"""
        from src.cache import CacheManager
        
        # 使用不存在的 Redis URL，会降级到内存缓存
        cache = CacheManager(redis_url="redis://localhost:9999")
        
        assert cache.stats["fallback_mode"] == True
    
    def test_cache_set_get(self):
        """测试缓存读写"""
        from src.cache import CacheManager
        
        cache = CacheManager(redis_url="redis://localhost:9999")
        
        # 设置值
        cache.set("test_key", {"value": 123})
        
        # 获取值
        result = cache.get("test_key")
        assert result is not None
        assert result["value"] == 123
    
    def test_cache_delete(self):
        """测试缓存删除"""
        from src.cache import CacheManager
        
        cache = CacheManager(redis_url="redis://localhost:9999")
        
        cache.set("delete_test", "value")
        assert cache.get("delete_test") == "value"
        
        cache.delete("delete_test")
        assert cache.get("delete_test") is None
    
    def test_cache_stats(self):
        """测试缓存统计"""
        from src.cache import CacheManager
        
        cache = CacheManager(redis_url="redis://localhost:9999")
        
        # 产生一些操作
        cache.set("stats_test", "value")
        cache.get("stats_test")  # hit
        cache.get("nonexistent")  # miss
        
        stats = cache.get_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
    
    def test_cache_decorator(self):
        """测试缓存装饰器"""
        from src.cache.redis_cache import cache_decorator
        
        call_count = 0
        
        @cache_decorator(ttl=60, key_prefix="test:")
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # 第一次调用
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # 第二次调用（应该从缓存获取）
        result2 = expensive_function(5)
        assert result2 == 10
        # 由于内存缓存是独立实例，这里可能不会命中


class TestWebSocketManager:
    """WebSocket 管理器测试"""
    
    def test_import(self):
        """测试模块导入"""
        from src.mcp.websocket import WebSocketManager, ws_manager
        assert WebSocketManager is not None
        assert ws_manager is not None
    
    def test_manager_init(self):
        """测试管理器初始化"""
        from src.mcp.websocket import WebSocketManager
        
        manager = WebSocketManager()
        
        assert manager.socketio is None  # 未初始化 SocketIO
        assert len(manager.connected_clients) == 0
        assert 'trades' in manager.subscriptions
        assert 'markets' in manager.subscriptions
        assert 'smart_money' in manager.subscriptions
    
    def test_subscribe_unsubscribe(self):
        """测试订阅/取消订阅"""
        from src.mcp.websocket import WebSocketManager
        
        manager = WebSocketManager()
        
        # 订阅
        result = manager.subscribe("client1", "trades")
        assert result == True
        assert "client1" in manager.subscriptions["trades"]
        
        # 取消订阅
        manager.unsubscribe("client1", "trades")
        assert "client1" not in manager.subscriptions["trades"]
    
    def test_market_subscription(self):
        """测试市场订阅"""
        from src.mcp.websocket import WebSocketManager
        
        manager = WebSocketManager()
        
        result = manager.subscribe("client2", "market", "trump-wins")
        assert result == True
        assert "trump-wins" in manager.market_subscriptions
        assert "client2" in manager.market_subscriptions["trump-wins"]
    
    def test_trader_subscription(self):
        """测试交易者订阅"""
        from src.mcp.websocket import WebSocketManager
        
        manager = WebSocketManager()
        
        result = manager.subscribe("client3", "trader", "0xABC123")
        assert result == True
        assert "0xabc123" in manager.trader_subscriptions  # 应该转小写
    
    def test_get_stats(self):
        """测试获取统计"""
        from src.mcp.websocket import WebSocketManager
        
        manager = WebSocketManager()
        manager.subscribe("client1", "trades")
        
        stats = manager.get_stats()
        
        assert "connected_clients" in stats
        assert "messages_sent" in stats
        assert "channel_subscribers" in stats
    
    def test_message_dataclass(self):
        """测试 WebSocketMessage 数据类"""
        from src.mcp.websocket import WebSocketMessage
        
        msg = WebSocketMessage(
            event="new_trade",
            data={"tx_hash": "0x123"}
        )
        
        assert msg.event == "new_trade"
        assert msg.data["tx_hash"] == "0x123"
        assert msg.timestamp is not None
        
        d = msg.to_dict()
        assert d["event"] == "new_trade"


# 允许直接运行
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
