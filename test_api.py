"""
快速 API 测试脚本
"""
import requests
import json

API_BASE = "http://localhost:8888"

def test_endpoint(name, endpoint, expected_key=None):
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        data = resp.json()
        
        if resp.status_code == 200:
            if expected_key and expected_key in data:
                value = data[expected_key]
                if isinstance(value, list):
                    print(f"✅ {name}: {len(value)} 条记录")
                elif isinstance(value, (int, float)):
                    print(f"✅ {name}: {value}")
                else:
                    print(f"✅ {name}: {value}")
            else:
                print(f"✅ {name}: OK")
        else:
            print(f"❌ {name}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"❌ {name}: {e}")

def main():
    print("=" * 50)
    print("PolyMind MCP API 测试")
    print("=" * 50)
    
    test_endpoint("健康检查", "/health", "status")
    test_endpoint("统计数据", "/stats", "total_trades")
    test_endpoint("最近交易", "/trades/recent?limit=5", "trades")
    test_endpoint("大单交易", "/trades/large?limit=5&min_size=100", "trades")
    test_endpoint("市场情绪", "/sentiment", "sentiment_index")
    test_endpoint("热门市场", "/hot?limit=5", "markets")
    test_endpoint("聪明钱", "/smart-money", "smart_money_addresses")
    test_endpoint("套利机会", "/arbitrage?limit=5", "opportunities")
    test_endpoint("WebSocket 状态", "/ws/stats", "total_clients")
    
    print("=" * 50)
    
    try:
        stats = requests.get(f"{API_BASE}/stats", timeout=5).json()
        print(f"\n📊 数据库统计:")
        print(f"   交易数: {stats.get('total_trades', 0)}")
        print(f"   交易者: {stats.get('unique_traders', 0)}")
        print(f"   交易量: ${stats.get('total_volume', 0):,.2f}")
        print(f"   市场数: {stats.get('total_markets', 0)}")
        print(f"   大单数: {stats.get('large_trades_count', 0)}")
    except Exception as e:
        print(f"获取统计失败: {e}")
    
    try:
        trades = requests.get(f"{API_BASE}/trades/recent?limit=3", timeout=5).json()
        print(f"\n📈 最近交易样本:")
        for t in trades.get('trades', [])[:3]:
            side = t.get('side', '?')
            size = t.get('size', 0)
            price = t.get('price', 0)
            market = t.get('market_slug', 'unknown')[:30]
            print(f"   {side:4} ${size:>10.2f} @ ${price:.4f} | {market}")
    except Exception as e:
        print(f"获取交易失败: {e}")
    
    print()

if __name__ == "__main__":
    main()
