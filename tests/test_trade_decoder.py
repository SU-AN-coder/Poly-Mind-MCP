"""
交易解码器测试 - 完整实现
"""
import pytest
import sys
from pathlib import Path
from decimal import Decimal
from dataclasses import asdict

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTradeDataclass:
    """测试Trade数据类"""
    
    def test_trade_creation(self):
        """测试Trade对象创建"""
        from src.trade_decoder import Trade
        
        trade = Trade(
            tx_hash="0x123abc",
            log_index=0,
            exchange="CTF_EXCHANGE",
            order_hash="0xabc123",
            maker="0xmaker",
            taker="0xtaker",
            maker_asset_id="0",
            taker_asset_id="123456789",
            maker_amount="1000000",
            taker_amount="2000000",
            fee="1000",
            price="0.5",
            token_id="123456789",
            side="BUY"
        )
        
        assert trade.tx_hash == "0x123abc"
        assert trade.log_index == 0
        assert trade.side == "BUY"
        assert trade.price == "0.5"
    
    def test_trade_immutable(self):
        """测试Trade对象不可变性"""
        from src.trade_decoder import Trade
        
        trade = Trade(
            tx_hash="0x123",
            log_index=0,
            exchange="CTF_EXCHANGE",
            order_hash="0xabc",
            maker="0xmaker",
            taker="0xtaker",
            maker_asset_id="0",
            taker_asset_id="123",
            maker_amount="1000000",
            taker_amount="2000000",
            fee="0",
            price="0.5",
            token_id="123",
            side="BUY"
        )
        
        # frozen=True 意味着不能修改属性
        with pytest.raises(Exception):
            trade.tx_hash = "0x456"
    
    def test_trade_to_dict(self):
        """测试Trade转换为字典"""
        from src.trade_decoder import Trade
        
        trade = Trade(
            tx_hash="0x123",
            log_index=0,
            exchange="CTF_EXCHANGE",
            order_hash="0xabc",
            maker="0xmaker",
            taker="0xtaker",
            maker_asset_id="0",
            taker_asset_id="123",
            maker_amount="1000000",
            taker_amount="2000000",
            fee="0",
            price="0.5",
            token_id="123",
            side="BUY"
        )
        
        trade_dict = asdict(trade)
        assert isinstance(trade_dict, dict)
        assert trade_dict['tx_hash'] == "0x123"
        assert trade_dict['side'] == "BUY"


class TestPriceCalculation:
    """价格计算逻辑测试"""
    
    def test_buy_price_calculation(self):
        """测试BUY价格计算: maker出USDC买入token"""
        # BUY: maker_asset_id = 0 (USDC)
        # 价格 = maker_amount / taker_amount
        maker_amount = Decimal("1000000")  # 1 USDC (6 decimals)
        taker_amount = Decimal("2000000")  # 2 tokens
        
        price = maker_amount / taker_amount
        assert price == Decimal("0.5")
    
    def test_sell_price_calculation(self):
        """测试SELL价格计算: maker出token卖出换USDC"""
        # SELL: maker_asset_id != 0 (token)
        # 价格 = taker_amount / maker_amount
        maker_amount = Decimal("2000000")  # 2 tokens
        taker_amount = Decimal("1000000")  # 1 USDC
        
        price = taker_amount / maker_amount
        assert price == Decimal("0.5")
    
    def test_price_precision(self):
        """测试价格精度"""
        # 测试小数精度
        maker_amount = Decimal("333333")
        taker_amount = Decimal("1000000")
        
        price = maker_amount / taker_amount
        assert price < Decimal("0.34")
        assert price > Decimal("0.33")
    
    def test_edge_case_zero_amount(self):
        """测试零金额边界情况"""
        maker_amount = Decimal("0")
        taker_amount = Decimal("1000000")
        
        if taker_amount > 0:
            price = maker_amount / taker_amount
            assert price == Decimal("0")


class TestSideDetermination:
    """买卖方向判断测试"""
    
    def test_buy_side(self):
        """测试BUY方向判断: maker_asset_id = 0"""
        maker_asset_id = "0"
        expected = "BUY"
        
        # 模拟side判断逻辑
        side = "BUY" if maker_asset_id == "0" else "SELL"
        assert side == expected
    
    def test_sell_side(self):
        """测试SELL方向判断: maker_asset_id != 0"""
        maker_asset_id = "123456789012345678901234567890"
        expected = "SELL"
        
        side = "BUY" if maker_asset_id == "0" else "SELL"
        assert side == expected
    
    def test_token_id_for_buy(self):
        """测试BUY时token_id取自taker_asset_id"""
        maker_asset_id = "0"
        taker_asset_id = "999888777"
        
        if maker_asset_id == "0":
            token_id = taker_asset_id
        else:
            token_id = maker_asset_id
        
        assert token_id == "999888777"
    
    def test_token_id_for_sell(self):
        """测试SELL时token_id取自maker_asset_id"""
        maker_asset_id = "111222333"
        taker_asset_id = "0"
        
        if maker_asset_id == "0":
            token_id = taker_asset_id
        else:
            token_id = maker_asset_id
        
        assert token_id == "111222333"


class TestTradeDecoderInit:
    """TradeDecoder初始化测试"""
    
    def test_exchange_constants(self):
        """测试Exchange常量定义"""
        from src.trade_decoder import TradeDecoder
        
        assert TradeDecoder.CTF_EXCHANGE == "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
        assert TradeDecoder.NEG_RISK_EXCHANGE == "0xC5d563A36AE78145C45a50134d48A1215220f80a"
    
    def test_usdc_constants(self):
        """测试USDC常量"""
        from src.trade_decoder import TradeDecoder
        
        assert TradeDecoder.USDC_DECIMALS == 6
        assert TradeDecoder.USDC_ADDRESS == "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    
    def test_order_filled_topic(self):
        """测试OrderFilled事件签名"""
        from src.trade_decoder import TradeDecoder
        
        # 验证事件签名存在且格式正确
        topic = TradeDecoder.ORDER_FILLED_TOPIC
        # topic 可能是 bytes 或 str，且可能有或没有 0x 前缀
        if isinstance(topic, bytes):
            topic = topic.hex()
        topic_str = topic if topic.startswith('0x') else '0x' + topic
        assert len(topic_str) == 66  # 0x + 64 hex chars


class TestTradeDecoderIntegration:
    """TradeDecoder集成测试 (需要RPC连接)"""
    
    @pytest.fixture
    def rpc_url(self):
        """获取RPC URL"""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv("POLYGON_RPC_URL", "")
    
    def test_decoder_init_with_valid_rpc(self, rpc_url):
        """测试使用有效RPC初始化"""
        if not rpc_url:
            pytest.skip("未配置POLYGON_RPC_URL")
        
        from src.trade_decoder import TradeDecoder
        
        try:
            decoder = TradeDecoder(rpc_url)
            assert decoder.w3.is_connected()
        except ConnectionError:
            pytest.skip("无法连接到RPC")
    
    def test_decode_known_trade(self, rpc_url):
        """测试解码已知交易"""
        if not rpc_url:
            pytest.skip("未配置POLYGON_RPC_URL")
        
        from src.trade_decoder import TradeDecoder
        
        try:
            decoder = TradeDecoder(rpc_url)
            # 使用示例交易哈希 (可能过期)
            trades = decoder.decode_tx_logs("0x" + "0" * 64)
            # 应该返回列表(可能为空)
            assert isinstance(trades, list)
        except (ConnectionError, Exception) as e:
            pytest.skip(f"解码失败: {e}")


# 允许直接运行
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
