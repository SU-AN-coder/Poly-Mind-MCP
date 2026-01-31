"""
数据库检查脚本 - 诊断数据问题
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.getenv("DB_PATH", "data/polymarket.db")

def main():
    print("=" * 60)
    print("数据库诊断工具")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        return
    
    print(f"✅ 数据库文件: {DB_PATH}")
    print(f"   大小: {os.path.getsize(DB_PATH) / 1024:.2f} KB")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 检查表
    print("\n📋 数据库表:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   • {table}: {count} 行")
    
    # 2. 检查 trades 表结构
    print("\n📊 trades 表结构:")
    cursor.execute("PRAGMA table_info(trades)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"   • {col[1]} ({col[2]})")
    
    # 3. 检查样本数据
    print("\n🔍 trades 样本数据 (前5条):")
    cursor.execute("SELECT * FROM trades LIMIT 5")
    rows = cursor.fetchall()
    col_names = [col[1] for col in columns]
    
    for i, row in enumerate(rows):
        print(f"\n   --- 记录 {i+1} ---")
        for j, val in enumerate(row):
            if j < len(col_names):
                print(f"   {col_names[j]}: {val}")
    
    # 4. 检查金额数据
    print("\n💰 金额分析:")
    amount_col = 'maker_amount' if 'maker_amount' in [c[1] for c in columns] else 'amount'
    
    cursor.execute(f"SELECT MIN(CAST({amount_col} AS REAL)), MAX(CAST({amount_col} AS REAL)), AVG(CAST({amount_col} AS REAL)) FROM trades")
    min_amt, max_amt, avg_amt = cursor.fetchone()
    print(f"   最小金额: {min_amt}")
    print(f"   最大金额: {max_amt}")
    print(f"   平均金额: {avg_amt}")
    
    # 判断单位
    if max_amt and max_amt > 1e9:
        print("   📌 金额单位: Wei (需要除以 1e6)")
        print(f"   转换后范围: ${min_amt/1e6:.2f} - ${max_amt/1e6:.2f}")
    else:
        print("   📌 金额单位: 已经是 USDC")
    
    # 5. 检查 side 字段
    print("\n📈 side 字段分析:")
    cursor.execute("SELECT DISTINCT side FROM trades")
    sides = [row[0] for row in cursor.fetchall()]
    print(f"   唯一值: {sides}")
    
    for side in sides:
        cursor.execute(f"SELECT COUNT(*) FROM trades WHERE side = ?", (side,))
        count = cursor.fetchone()[0]
        print(f"   • '{side}': {count} 条")
    
    # 6. 检查 markets 表
    print("\n🏪 markets 表:")
    cursor.execute("PRAGMA table_info(markets)")
    market_cols = cursor.fetchall()
    for col in market_cols:
        print(f"   • {col[1]} ({col[2]})")
    
    cursor.execute("SELECT * FROM markets LIMIT 3")
    market_rows = cursor.fetchall()
    market_col_names = [col[1] for col in market_cols]
    
    for i, row in enumerate(market_rows):
        print(f"\n   --- 市场 {i+1} ---")
        for j, val in enumerate(row):
            if j < len(market_col_names):
                val_str = str(val)[:50] + "..." if len(str(val)) > 50 else val
                print(f"   {market_col_names[j]}: {val_str}")
    
    conn.close()
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
