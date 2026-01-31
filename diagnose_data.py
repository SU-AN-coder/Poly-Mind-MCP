"""
深度数据诊断脚本 - 找出数据不变的根本原因
"""
import sqlite3
import os
from datetime import datetime
import json

DB_PATH = "data/polymarket.db"

def diagnose():
    print("=" * 70)
    print("📊 PolyMind MCP 数据诊断报告")
    print("=" * 70)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库不存在: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 检查表结构和数据量
    print("\n[1️⃣ 表结构与数据量]")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  {table_name}: {count} 行")
    
    # 2. 检查交易表的详细信息
    print("\n[2️⃣ trades 表详细分析]")
    
    # 2.1 交易的时间跨度
    cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM trades")
    min_ts, max_ts = cursor.fetchone()
    print(f"  时间跨度: {min_ts} 到 {max_ts}")
    
    # 2.2 交易的唯一值分布
    cursor.execute("SELECT COUNT(DISTINCT maker) FROM trades")
    unique_makers = cursor.fetchone()[0]
    print(f"  唯一 maker: {unique_makers}")
    
    cursor.execute("SELECT COUNT(DISTINCT side) FROM trades")
    unique_sides = cursor.fetchone()[0]
    print(f"  唯一 side: {unique_sides}")
    
    cursor.execute("SELECT COUNT(DISTINCT outcome) FROM trades")
    unique_outcomes = cursor.fetchone()[0]
    print(f"  唯一 outcome: {unique_outcomes}")
    
    # 2.3 价格分布
    cursor.execute("SELECT MIN(price), MAX(price), AVG(price) FROM trades")
    min_price, max_price, avg_price = cursor.fetchone()
    print(f"  价格范围: {min_price} ~ {max_price} (平均: {avg_price})")
    
    # 2.4 金额分布
    cursor.execute("SELECT MIN(maker_amount), MAX(maker_amount) FROM trades")
    min_amt, max_amt = cursor.fetchone()
    print(f"  maker_amount 范围: {min_amt} ~ {max_amt}")
    
    # 2.5 市场关联
    cursor.execute("SELECT COUNT(*) FROM trades WHERE market_id IS NOT NULL")
    with_market = cursor.fetchone()[0]
    total = cursor.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    print(f"  有 market_id: {with_market}/{total} ({with_market/total*100:.1f}%)")
    
    cursor.execute("SELECT COUNT(*) FROM trades WHERE token_id IS NOT NULL")
    with_token = cursor.fetchone()[0]
    print(f"  有 token_id: {with_token}/{total} ({with_token/total*100:.1f}%)")
    
    # 3. 检查市场表
    print("\n[3️⃣ markets 表分析]")
    cursor.execute("SELECT COUNT(*) FROM markets")
    market_count = cursor.fetchone()[0]
    print(f"  总市场数: {market_count}")
    
    cursor.execute("SELECT COUNT(*) FROM markets WHERE title IS NOT NULL")
    with_title = cursor.fetchone()[0]
    print(f"  有 title: {with_title}/{market_count}")
    
    cursor.execute("SELECT COUNT(*) FROM markets WHERE slug IS NOT NULL")
    with_slug = cursor.fetchone()[0]
    print(f"  有 slug: {with_slug}/{market_count}")
    
    # 4. 交易-市场映射情况
    print("\n[4️⃣ 交易-市场映射]")
    
    # 通过 token_id 匹配
    cursor.execute("""
        SELECT COUNT(DISTINCT t.id) FROM trades t
        LEFT JOIN markets m1 ON t.token_id = m1.yes_token_id
        LEFT JOIN markets m2 ON t.token_id = m2.no_token_id
        WHERE m1.id IS NOT NULL OR m2.id IS NOT NULL
    """)
    mapped_by_token = cursor.fetchone()[0]
    print(f"  通过 token_id 映射: {mapped_by_token}/{total} ({mapped_by_token/total*100:.1f}%)")
    
    # 通过 market_id 映射
    cursor.execute("""
        SELECT COUNT(DISTINCT t.id) FROM trades t
        LEFT JOIN markets m ON t.market_id = m.id
        WHERE m.id IS NOT NULL
    """)
    mapped_by_id = cursor.fetchone()[0]
    print(f"  通过 market_id 映射: {mapped_by_id}/{total} ({mapped_by_id/total*100:.1f}%)")
    
    # 5. 数据样本
    print("\n[5️⃣ 数据样本]")
    
    print("\n  最新的 5 条交易:")
    cursor.execute("""
        SELECT t.id, t.tx_hash, t.side, t.price, t.maker_amount, 
               t.market_id, t.token_id, t.timestamp,
               m.slug, m.title
        FROM trades t
        LEFT JOIN markets m ON t.market_id = m.id
        ORDER BY t.id DESC LIMIT 5
    """)
    
    for row in cursor.fetchall():
        trade_id, tx, side, price, amt, mid, tid, ts, mslug, mtitle = row
        print(f"\n    交易 #{trade_id}")
        print(f"      tx: {tx[:16]}...")
        print(f"      side: {side}, price: {price}, amount: {amt}")
        print(f"      market_id: {mid}, token_id: {tid}")
        print(f"      timestamp: {ts}")
        print(f"      market: {mslug} ({mtitle})")
    
    # 6. 统计聚合查询验证
    print("\n[6️⃣ 统计聚合查询验证]")
    
    # 总交易数
    cursor.execute("SELECT COUNT(*) FROM trades")
    total_count = cursor.fetchone()[0]
    print(f"  COUNT(*): {total_count}")
    
    # 总交易量
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
    print(f"  总交易量 (Wei): {total_vol}")
    print(f"  总交易量 (USDC): {total_vol / 1e6 if total_vol > 1e6 else total_vol}")
    
    # 买卖比例
    cursor.execute("""
        SELECT side, COUNT(*) FROM trades GROUP BY side
    """)
    for side, count in cursor.fetchall():
        print(f"  {side}: {count}")
    
    # 7. 检查是否有新数据正在写入
    print("\n[7️⃣ 数据写入检查]")
    
    cursor.execute("SELECT timestamp FROM trades ORDER BY id DESC LIMIT 1")
    latest = cursor.fetchone()
    if latest:
        latest_ts = latest[0]
        print(f"  最新交易时间: {latest_ts}")
        
        try:
            from datetime import datetime
            latest_dt = datetime.fromisoformat(latest_ts.replace('Z', '+00:00'))
            now = datetime.now(latest_dt.tzinfo)
            delta = (now - latest_dt).total_seconds()
            print(f"  距现在: {delta:.0f} 秒前")
        except:
            pass
    
    # 8. API 数据对比
    print("\n[8️⃣ API 响应对比]")
    
    try:
        import requests
        resp = requests.get("http://localhost:8888/stats", timeout=5)
        if resp.status_code == 200:
            api_stats = resp.json()
            print(f"  API total_trades: {api_stats.get('total_trades')}")
            print(f"  API total_volume: {api_stats.get('total_volume')}")
            print(f"  API unique_traders: {api_stats.get('unique_traders')}")
            
            if api_stats.get('total_trades') == total_count:
                print(f"  ✅ API 数据与数据库一致")
            else:
                print(f"  ❌ API 数据与数据库不一致！差异: {api_stats.get('total_trades') - total_count}")
        else:
            print(f"  ❌ API 请求失败: {resp.status_code}")
    except Exception as e:
        print(f"  ❌ 无法连接 API: {e}")
    
    # 9. 问题分析
    print("\n[9️⃣ 问题分析]")
    
    issues = []
    
    if mapped_by_token / total < 0.5:
        issues.append(f"⚠️ token_id 映射率低 ({mapped_by_token/total*100:.1f}%)")
    
    if with_market == 0:
        issues.append(f"⚠️ 交易没有 market_id，无法通过 ID 映射市场")
    
    if with_slug < market_count * 0.5:
        issues.append(f"⚠️ 市场缺少 slug (只有 {with_slug}/{market_count})")
    
    if total_count == 0:
        issues.append("❌ 数据库中没有交易数据")
    
    if not issues:
        print("  ✅ 没有发现明显问题")
    else:
        for issue in issues:
            print(f"  {issue}")
    
    conn.close()
    
    # 10. 建议
    print("\n[🔟 建议]")
    print("  1. 检查数据索引是否成功运行")
    print("  2. 运行: python check_database.py 查看原始数据结构")
    print("  3. 检查 sync_state 表的同步进度")
    print("  4. 确保数据库没有被锁定")
    print("  5. 尝试重新索引: python start.py index --from-block 82230876 --to-block 82231000")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    diagnose()
