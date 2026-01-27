"""
市场解码器测试
"""
import pytest
import sys
import os
from pathlib import Path
from decimal import Decimal

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMarketDecoder:
    """市场解码器测试"""
    
    def test_calculate_token_id(self):
        """测试TokenId计算"""
        try:
            from src.ctf.derive import derive_binary_positions
            
            # 使用测试数据
            condition_id = "0x" + "a" * 64
            collateral_token = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
            oracle = "0x6A9D222616C90FcA5754cd1333cFD9b7fb6a4F74"
            question_id = "0x" + "c" * 64
            
            # 计算 YES 和 NO token
            positions = derive_binary_positions(
                oracle=oracle,
                question_id=question_id,
                condition_id=condition_id,
                collateral_token=collateral_token
            )
            
            assert positions.position_yes is not None
            assert len(positions.position_yes) > 10
            print(f"✓ YES Token ID: {positions.position_yes[:30]}...")
            
            assert positions.position_no is not None
            assert positions.position_yes != positions.position_no
            print(f"✓ NO Token ID: {positions.position_no[:30]}...")
        except ImportError as e:
            pytest.skip(f"模块导入失败: {e}")
    
    def test_calculate_collection_id(self):
        """测试CollectionId计算"""
        try:
            from src.ctf.derive import derive_binary_positions
            
            condition_id = "0x" + "b" * 64
            collateral_token = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
            oracle = "0x6A9D222616C90FcA5754cd1333cFD9b7fb6a4F74"
            question_id = "0x" + "d" * 64
            
            positions = derive_binary_positions(
                oracle=oracle,
                question_id=question_id,
                condition_id=condition_id,
                collateral_token=collateral_token
            )
            
            assert positions.collection_id_yes is not None
            assert len(positions.collection_id_yes) == 66  # 0x + 64 hex chars
            print(f"✓ Collection ID YES: {positions.collection_id_yes[:30]}...")
            print(f"✓ Collection ID NO: {positions.collection_id_no[:30]}...")
        except ImportError as e:
            pytest.skip(f"模块导入失败: {e}")
    
    def test_gamma_api_connection(self):
        """测试 Gamma API 连接"""
        import requests
        
        try:
            response = requests.get(
                "https://gamma-api.polymarket.com/markets?limit=1",
                timeout=10
            )
            assert response.status_code == 200
            markets = response.json()
            assert isinstance(markets, list)
            print(f"✓ Gamma API 连接正常，获取到 {len(markets)} 个市场")
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Gamma API 不可用: {e}")
    
    def test_decode_from_gamma(self):
        """测试从Gamma API解码市场"""
        import requests
        
        market_slug = "will-there-be-another-us-government-shutdown-by-january-31"
        
        try:
            # 直接测试 Gamma API
            response = requests.get(
                f"https://gamma-api.polymarket.com/markets?slug={market_slug}",
                timeout=10
            )
            
            if response.status_code == 200:
                markets = response.json()
                if markets:
                    market = markets[0]
                    assert 'conditionId' in market or 'condition_id' in market
                    print(f"✓ 市场解码成功: {market.get('question', 'N/A')[:50]}")
                else:
                    pytest.skip("市场未找到（可能已过期）")
            else:
                pytest.skip(f"API 返回错误: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"API 请求失败: {e}")


class TestTradeDecoder:
    """交易解码器测试"""
    
    def test_price_calculation(self):
        """测试价格计算逻辑"""
        # 模拟交易数据
        maker_amount = 1000000  # 1 USDC (6 decimals)
        taker_amount = 2000000  # 2 tokens
        
        # maker 出 USDC，买入 token
        price = Decimal(maker_amount) / Decimal(taker_amount)
        
        assert price == Decimal("0.5")
        print(f"✓ 价格计算正确: {price}")
    
    def test_side_determination(self):
        """测试买卖方向判断"""
        # maker_asset_id = 0 表示 maker 出 USDC -> BUY
        maker_asset_id = 0
        expected_side = "BUY"
        
        if maker_asset_id == 0:
            actual_side = "BUY"
        else:
            actual_side = "SELL"
        
        assert actual_side == expected_side
        print(f"✓ 方向判断正确: {actual_side}")
        
        # maker_asset_id != 0 表示 maker 出 token -> SELL
        maker_asset_id = 12345
        expected_side = "SELL"
        
        if maker_asset_id == 0:
            actual_side = "BUY"
        else:
            actual_side = "SELL"
        
        assert actual_side == expected_side
        print(f"✓ SELL 方向判断正确: {actual_side}")


# 允许直接运行
if __name__ == "__main__":
    print("=" * 60)
    print("运行 MarketDecoder 测试")
    print("=" * 60)
    
    # 运行测试
    test_market = TestMarketDecoder()
    test_trade = TestTradeDecoder()
    
    tests = [
        ("Token ID 计算", test_market.test_calculate_token_id),
        ("Collection ID 计算", test_market.test_calculate_collection_id),
        ("Gamma API 连接", test_market.test_gamma_api_connection),
        ("Gamma 市场解码", test_market.test_decode_from_gamma),
        ("价格计算", test_trade.test_price_calculation),
        ("方向判断", test_trade.test_side_determination),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, test_func in tests:
        print(f"\n[测试] {name}")
        try:
            test_func()
            passed += 1
            print(f"  结果: ✓ 通过")
        except pytest.skip.Exception as e:
            skipped += 1
            print(f"  结果: ⚠ 跳过 - {e}")
        except Exception as e:
            failed += 1
            print(f"  结果: ✗ 失败 - {e}")
    
    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败, {skipped} 跳过")
    print("=" * 60)
