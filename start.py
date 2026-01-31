"""
PolyMind MCP 统一启动脚本
"""
import argparse
import os
import sys
import json

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def import_demo_data():
    """导入演示数据"""
    from src.db.schema import get_connection
    
    demo_file = "data/fixtures/demo_trades.json"
    if not os.path.exists(demo_file):
        print(f"   ⚠️ 演示数据文件不存在: {demo_file}")
        return
    
    with open(demo_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 导入市场
    markets = data.get('markets', [])
    for m in markets:
        cursor.execute("""
            INSERT OR IGNORE INTO markets 
            (condition_id, slug, question, description, yes_token_id, no_token_id, 
             volume, liquidity, yes_price, no_price, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m.get('condition_id'), m.get('slug'), m.get('question'),
            m.get('description'), m.get('yes_token_id'), m.get('no_token_id'),
            m.get('volume', 0), m.get('liquidity', 0),
            m.get('yes_price', 0.5), m.get('no_price', 0.5),
            m.get('active', 1)
        ))
    
    # 导入交易
    trades = data.get('trades', [])
    for t in trades:
        cursor.execute("""
            INSERT OR IGNORE INTO trades 
            (tx_hash, maker, taker, side, outcome, price, 
             maker_amount, taker_amount, block_number, timestamp, market_slug)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t.get('tx_hash'), t.get('maker'), t.get('taker'),
            t.get('side'), t.get('outcome'), t.get('price'),
            t.get('maker_amount'), t.get('taker_amount'),
            t.get('block_number'), t.get('timestamp'), t.get('market_slug')
        ))
    
    conn.commit()
    conn.close()
    print(f"   ✅ 导入完成: {len(markets)} 个市场, {len(trades)} 条交易")


def verify_data():
    """验证数据"""
    from src.db.schema import get_connection
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n📊 数据库统计:")
    print("=" * 40)
    
    cursor.execute("SELECT COUNT(*) FROM trades")
    trade_count = cursor.fetchone()[0]
    print(f"  交易数: {trade_count}")
    
    cursor.execute("SELECT COUNT(*) FROM markets")
    print(f"  市场数: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(DISTINCT maker) FROM trades")
    print(f"  交易者数: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT SUM(CAST(maker_amount AS REAL)) / 1e6 FROM trades")
    vol = cursor.fetchone()[0] or 0
    print(f"  总交易量: ${vol:,.2f}")
    
    try:
        cursor.execute("SELECT last_block FROM indexer_state WHERE id = 1")
        row = cursor.fetchone()
        print(f"  最后索引区块: {row[0] if row else 'N/A'}")
    except:
        print(f"  最后索引区块: N/A")
    
    conn.close()
    
    print("=" * 40)
    if trade_count >= 100:
        print("✅ 数据验证通过！满足黑客松要求 (≥100 条交易)")
    else:
        print(f"❌ 数据不足！还需要 {100 - trade_count} 条交易记录")


def cmd_index(args):
    """运行索引器"""
    from src.indexer.run import main as run_indexer
    sys.argv = ['run.py', '--from-block', str(args.from_block)]
    if args.to_block:
        sys.argv.extend(['--to-block', str(args.to_block)])
    if args.continuous:
        sys.argv.append('--continuous')
    run_indexer()


def cmd_sync_markets(args):
    """同步市场数据"""
    from src.indexer.gamma import GammaClient
    client = GammaClient()
    count = client.sync_markets_to_db(limit=args.limit)
    print(f"✅ 同步完成: {count} 个市场")


def cmd_api(args):
    """启动 API 服务器"""
    from src.mcp.server import create_app
    app = create_app()
    print(f"🚀 启动 API 服务器: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


def cmd_verify(args):
    """验证数据"""
    verify_data()


def cmd_demo(args):
    """演示模式"""
    print("=" * 60)
    print("🚀 PolyMind MCP 演示模式启动")
    print("=" * 60)
    print()
    
    # [1/4] 初始化数据库
    print("📦 [1/4] 初始化数据库...")
    from src.db.schema import init_db, get_connection
    init_db()
    
    # [2/4] 检查/导入数据
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trades")
    trade_count = cursor.fetchone()[0]
    conn.close()
    
    if trade_count >= 100:
        print(f"\n✅ [2/4] 数据库已有 {trade_count} 条交易，跳过导入")
    else:
        print("\n📥 [2/4] 导入演示数据...")
        import_demo_data()
    
    # [3/4] 验证数据
    print("\n🔍 [3/4] 验证数据...")
    verify_data()
    
    # [4/4] 启动服务器
    print("\n🌐 [4/4] 启动 API 服务器...")
    print(f"   服务地址: http://localhost:{args.port}")
    print(f"   前端看板: http://localhost:3000 (需另行启动)")
    print(f"   健康检查: http://localhost:{args.port}/health")
    print()
    print("   按 Ctrl+C 停止服务")
    print("=" * 60)
    
    from src.mcp.server import create_app
    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


def cmd_all(args):
    """运行所有服务"""
    print("🚀 启动 PolyMind MCP 全部服务...")
    
    # 同步市场
    print("\n[1/3] 同步市场数据...")
    from src.indexer.gamma import GammaClient
    try:
        client = GammaClient()
        count = client.sync_markets_to_db(limit=100)
        print(f"   ✅ 同步完成: {count} 个市场")
    except Exception as e:
        print(f"   ⚠️ 同步失败: {e}")
    
    # 验证数据
    print("\n[2/3] 验证数据...")
    verify_data()
    
    # 启动 API
    print("\n[3/3] 启动 API 服务器...")
    cmd_api(args)


def main():
    parser = argparse.ArgumentParser(
        description="PolyMind MCP 统一启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python start.py demo                    # 🌟 推荐：一键演示模式
  python start.py api                     # 启动 API 服务器
  python start.py index --from-block 66000000
  python start.py sync-markets
  python start.py verify
  python start.py all
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # demo 命令 (推荐)
    demo_parser = subparsers.add_parser("demo", help="🌟 一键演示模式（评审者推荐）")
    demo_parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    demo_parser.add_argument("--port", type=int, default=8888, help="API 端口")
    demo_parser.add_argument("--debug", action="store_true", help="调试模式")
    demo_parser.set_defaults(func=cmd_demo)
    
    # index 命令
    index_parser = subparsers.add_parser("index", help="运行链上索引器")
    index_parser.add_argument("--from-block", type=int, default=66000000, help="起始区块")
    index_parser.add_argument("--to-block", type=int, default=None, help="结束区块")
    index_parser.add_argument("--continuous", action="store_true", help="持续模式")
    index_parser.set_defaults(func=cmd_index)
    
    # sync-markets 命令
    sync_parser = subparsers.add_parser("sync-markets", help="同步 Gamma API 市场数据")
    sync_parser.add_argument("--limit", type=int, default=500, help="同步数量限制")
    sync_parser.set_defaults(func=cmd_sync_markets)
    
    # api 命令
    api_parser = subparsers.add_parser("api", help="启动 HTTP API 服务器")
    api_parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    api_parser.add_argument("--port", type=int, default=8888, help="监听端口")
    api_parser.add_argument("--debug", action="store_true", help="调试模式")
    api_parser.set_defaults(func=cmd_api)
    
    # verify 命令
    verify_parser = subparsers.add_parser("verify", help="验证数据")
    verify_parser.set_defaults(func=cmd_verify)
    
    # all 命令
    all_parser = subparsers.add_parser("all", help="启动所有服务")
    all_parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    all_parser.add_argument("--port", type=int, default=8888, help="监听端口")
    all_parser.add_argument("--debug", action="store_true", help="调试模式")
    all_parser.set_defaults(func=cmd_all)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        print("\n💡 快速开始: python start.py demo")
        sys.exit(0)
    
    args.func(args)


if __name__ == "__main__":
    main()
