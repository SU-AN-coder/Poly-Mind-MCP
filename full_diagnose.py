"""
完整诊断脚本 - 找出数据显示问题
"""
import sqlite3
import os
import sys

DB_PATH = "data/polymarket.db"

def main():
    print("=" * 70)
    print("🔍 完整数据诊断")
    print("=" * 70)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库不存在: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 检查 /stats 应返回的数据
    print("\n[1] /stats 端点验证:")
    
    cursor.execute("SELECT COUNT(*) FROM trades")
    total_trades = cursor.fetchone()[0]
    print(f"  ✅ total_trades: {total_trades}")
    
    cursor.execute("SELECT COUNT(DISTINCT maker) FROM trades")
    unique_traders = cursor.fetchone()[0]
    print(f"  ✅ unique_traders: {unique_traders}")
    
    cursor.execute("""
        SELECT SUM(
            CASE 
                WHEN CAST(maker_amount AS REAL) < CAST(taker_amount AS REAL) 
                THEN CAST(maker_amount AS REAL)
                ELSE CAST(taker_amount AS REAL)
            END
        ) FROM trades
    """)
    total_vol = cursor.fetchone()[0] or 0
    total_vol_usdc = total_vol / 1e6 if total_vol > 1e6 else total_vol
    print(f"  ✅ total_volume: ${total_vol_usdc:,.2f}")
    
    cursor.execute("SELECT COUNT(*) FROM markets")
    markets = cursor.fetchone()[0]
    print(f"  ✅ total_markets: {markets}")
    
    cursor.execute("""
        SELECT COUNT(*) FROM trades 
        WHERE (
            CASE 
                WHEN CAST(maker_amount AS REAL) < CAST(taker_amount AS REAL) 
                THEN CAST(maker_amount AS REAL) / 1e6
                ELSE CAST(taker_amount AS REAL) / 1e6
            END
        ) >= 1000
    """)
    large_trades = cursor.fetchone()[0]
    print(f"  ✅ large_trades_count: {large_trades}")
    
    # 2. 检查 /trades/recent 应返回的数据
    print("\n[2] /trades/recent 端点验证:")
    
    cursor.execute("""
        SELECT 
            t.tx_hash, t.maker, t.taker, t.side, t.outcome,
            t.price, t.maker_amount, t.taker_amount, t.timestamp
        FROM trades t
        ORDER BY t.id DESC
        LIMIT 1
    """)
    
    row = cursor.fetchone()
    if row:
        print(f"  最新交易:")
        print(f"    tx_hash: {row[0][:20]}...")
        print(f"    side: {row[3]}")
        print(f"    price: {row[5]}")
        maker_amt = float(row[6] or 0)
        taker_amt = float(row[7] or 0)
        
        if maker_amt < 1e6 and taker_amt > 1e6:
            size = maker_amt
        elif taker_amt < 1e6 and maker_amt > 1e6:
            size = taker_amt
        else:
            smaller = min(maker_amt, taker_amt)
            size = smaller / 1e6 if smaller > 1e6 else smaller
        
        print(f"    size (USDC): ${size:,.2f}")
        print(f"    ✅ 数据格式正确")
    else:
        print(f"  ❌ 没有交易数据!")
    
    # 3. 检查 /trades/large 应返回的数据
    print("\n[3] /trades/large 端点验证:")
    
    cursor.execute("""
        SELECT COUNT(*) FROM trades
        WHERE (
            CASE 
                WHEN CAST(maker_amount AS REAL) < CAST(taker_amount AS REAL) 
                THEN CAST(maker_amount AS REAL)
                ELSE CAST(taker_amount AS REAL)
            END
        ) >= 1000
    """)
    large_count = cursor.fetchone()[0]
    print(f"  大单数量 (>=1000): {large_count}")
    
    if large_count > 0:
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN CAST(maker_amount AS REAL) < CAST(taker_amount AS REAL) 
                    THEN CAST(maker_amount AS REAL)
                    ELSE CAST(taker_amount AS REAL)
                END as size
            FROM trades
            ORDER BY 
                CASE 
                    WHEN CAST(maker_amount AS REAL) < CAST(taker_amount AS REAL) 
                    THEN CAST(maker_amount AS REAL)
                    ELSE CAST(taker_amount AS REAL)
                END DESC
            LIMIT 1
        """)
        largest = cursor.fetchone()
        if largest:
            largest_size = largest[0] / 1e6 if largest[0] > 1e6 else largest[0]
            print(f"  最大交易: ${largest_size:,.2f}")
            print(f"  ✅ 数据可用")
    else:
        print(f"  ⚠️ 没有大单交易")
    
    # 4. 检查 /sentiment 应返回的数据
    print("\n[4] /sentiment 端点验证:")
    
    cursor.execute("SELECT side, COUNT(*) FROM trades GROUP BY side")
    for side, count in cursor.fetchall():
        print(f"  {side}: {count} 条")
    
    cursor.execute("""
        SELECT side, 
               SUM(
                   CASE 
                       WHEN CAST(maker_amount AS REAL) < CAST(taker_amount AS REAL) 
                       THEN CAST(maker_amount AS REAL)
                       ELSE CAST(taker_amount AS REAL)
                   END
               ) as vol
        FROM trades
        GROUP BY side
    """)
    
    for side, vol in cursor.fetchall():
        vol_usdc = vol / 1e6 if vol and vol > 1e6 else vol or 0
        print(f"  {side} 交易量: ${vol_usdc:,.2f}")
    
    print(f"  ✅ 情绪数据可用")
    
    # 5. 检查前端能否访问 API
    print("\n[5] 前端 API 访问检查:")
    
    try:
        import requests
        
        endpoints = [
            ("/health", "健康检查"),
            ("/stats", "统计数据"),
            ("/trades/recent?limit=5", "最近交易"),
            ("/trades/large?limit=5", "大单交易"),
            ("/sentiment", "市场情绪")
        ]
        
        for endpoint, name in endpoints:
            try:
                resp = requests.get(f"http://localhost:8888{endpoint}", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"  ✅ {name}: 200 OK, {len(str(data))} bytes")
                else:
                    print(f"  ❌ {name}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"  ❌ {name}: {type(e).__name__}")
    except ImportError:
        print("  ⚠️ 需要 requests 库来测试 API")
    
    conn.close()
    
    # 6. 总结
    print("\n" + "=" * 70)
    print("📋 总结:")
    print(f"  总交易数: {total_trades}")
    print(f"  唯一交易者: {unique_traders}")
    print(f"  总交易量: ${total_vol_usdc:,.2f}")
    print(f"  市场数: {markets}")
    print(f"  大单数: {large_trades}")
    
    if total_trades > 0 and unique_traders > 0:
        print("\n✅ 数据库中有充分的数据")
        print("✅ API 应该能返回正确的数据")
        print("✅ 前端应该能正常显示")
        print("\n可能的问题:")
        print("  1. 前端 JS 代码有 bug")
        print("  2. API 返回格式与前端期望不符")
        print("  3. 浏览器缓存问题 (Ctrl+F5 强制刷新)")
    else:
        print("\n❌ 数据不足")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
