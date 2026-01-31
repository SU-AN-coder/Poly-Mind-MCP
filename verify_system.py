"""
系统验证脚本
验证所有模块和 API 是否正常工作
"""
import os
import sys
import json
import time
import requests
from datetime import datetime

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

API_BASE = "http://localhost:8888"

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_result(name, success, detail=""):
    status = "✅ 通过" if success else "❌ 失败"
    print(f"  {status} | {name}")
    if detail:
        print(f"         └─ {detail}")

def check_module_imports():
    """检查模块导入"""
    print_header("1. 模块导入检查")
    
    modules = [
        ("src.db.schema", "数据库 Schema"),
        ("src.mcp.tools", "MCP 工具"),
        ("src.mcp.profiler", "交易者画像"),
        ("src.mcp.advisor", "交易顾问"),
        ("src.api.server", "API 服务器"),
        ("src.api.websocket_manager", "WebSocket 管理器"),
    ]
    
    all_passed = True
    for module_path, name in modules:
        try:
            __import__(module_path)
            print_result(name, True)
        except Exception as e:
            print_result(name, False, str(e)[:50])
            all_passed = False
    
    return all_passed

def check_database():
    """检查数据库"""
    print_header("2. 数据库检查")
    
    try:
        from src.db.schema import get_connection
        db_path = os.getenv("DB_PATH", "data/polymarket.db")
        
        if not os.path.exists(db_path):
            print_result("数据库文件", False, f"不存在: {db_path}")
            return False
        
        print_result("数据库文件", True, db_path)
        
        conn = get_connection(db_path)
        cursor = conn.cursor()
        
        # 检查表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print_result("数据库表", True, f"{len(tables)} 个表: {', '.join(tables[:5])}")
        
        # 检查交易数
        cursor.execute("SELECT COUNT(*) FROM trades")
        trade_count = cursor.fetchone()[0]
        print_result("交易记录", trade_count > 0, f"{trade_count} 条")
        
        # 检查市场数
        cursor.execute("SELECT COUNT(*) FROM markets")
        market_count = cursor.fetchone()[0]
        print_result("市场记录", market_count > 0, f"{market_count} 个")
        
        conn.close()
        return trade_count > 0
        
    except Exception as e:
        print_result("数据库连接", False, str(e))
        return False

def check_mcp_tools():
    """检查 MCP 工具"""
    print_header("3. MCP 工具检查")
    
    try:
        from src.mcp.tools import PolymarketTools
        
        tools = PolymarketTools()
        definitions = tools.get_tool_definitions()
        print_result("工具定义", True, f"{len(definitions)} 个工具")
        
        # 测试搜索工具
        result = tools.execute_tool("search_markets", {"query": "trump", "limit": 3})
        has_results = "results" in result or "error" not in result
        print_result("搜索工具", has_results, f"返回 {len(result.get('results', []))} 个结果")
        
        # 测试聪明钱工具
        result = tools.execute_tool("get_smart_money_activity", {"min_win_rate": 50})
        has_data = "smart_money_addresses" in result
        print_result("聪明钱工具", has_data, f"找到 {len(result.get('smart_money_addresses', []))} 个地址")
        
        return True
        
    except Exception as e:
        print_result("MCP 工具", False, str(e))
        return False

def check_api_server():
    """检查 API 服务器"""
    print_header("4. API 服务器检查")
    
    try:
        # 健康检查
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code == 200:
            print_result("健康检查 /health", True)
        else:
            print_result("健康检查 /health", False, f"状态码: {resp.status_code}")
            return False
        
        # 统计数据
        resp = requests.get(f"{API_BASE}/stats", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_result("统计数据 /stats", True, f"交易数: {data.get('total_trades', 0)}")
        else:
            print_result("统计数据 /stats", False)
        
        # 最近交易
        resp = requests.get(f"{API_BASE}/trades/recent?limit=5", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_result("最近交易 /trades/recent", True, f"返回 {len(data.get('trades', []))} 条")
        else:
            print_result("最近交易 /trades/recent", False)
        
        # 大单交易
        resp = requests.get(f"{API_BASE}/trades/large?limit=5", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_result("大单交易 /trades/large", True, f"返回 {len(data.get('trades', []))} 条")
        else:
            print_result("大单交易 /trades/large", False)
        
        # 市场情绪
        resp = requests.get(f"{API_BASE}/sentiment", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_result("市场情绪 /sentiment", True, f"情绪指数: {data.get('sentiment_index', 0)}")
        else:
            print_result("市场情绪 /sentiment", False)
        
        # 热门市场
        resp = requests.get(f"{API_BASE}/hot?limit=5", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print_result("热门市场 /hot", True, f"返回 {len(data.get('markets', []))} 个")
        else:
            print_result("热门市场 /hot", False)
        
        # 聪明钱
        resp = requests.get(f"{API_BASE}/smart-money", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_result("聪明钱 /smart-money", True, f"找到 {len(data.get('smart_money_addresses', []))} 个")
        else:
            print_result("聪明钱 /smart-money", False)
        
        # WebSocket 状态
        resp = requests.get(f"{API_BASE}/ws/stats", timeout=5)
        if resp.status_code == 200:
            print_result("WebSocket /ws/stats", True)
        else:
            print_result("WebSocket /ws/stats", False)
        
        # API 文档
        resp = requests.get(f"{API_BASE}/api-docs", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_result("API 文档 /api-docs", True, f"{len(data.get('paths', {}))} 个端点")
        else:
            print_result("API 文档 /api-docs", False)
        
        return True
        
    except requests.exceptions.ConnectionError:
        print_result("API 连接", False, "无法连接到服务器，请先运行: python run_api_server.py")
        return False
    except Exception as e:
        print_result("API 检查", False, str(e))
        return False

def check_frontend():
    """检查前端文件"""
    print_header("5. 前端文件检查")
    
    frontend_path = "frontend/index.html"
    if os.path.exists(frontend_path):
        size = os.path.getsize(frontend_path)
        print_result("index.html", True, f"{size/1024:.1f} KB")
        
        # 检查关键内容
        with open(frontend_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ("React 组件", "ReactDOM.createRoot" in content),
            ("API 集成", "API_BASE" in content),
            ("大单监控面板", "LargeTradesPanel" in content),
            ("市场情绪组件", "SentimentGauge" in content),
            ("Chart.js", "chart.js" in content.lower()),
        ]
        
        for name, passed in checks:
            print_result(name, passed)
        
        return True
    else:
        print_result("index.html", False, "文件不存在")
        return False

def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║           PolyMind MCP 系统验证工具 v2.0                   ║
║                                                            ║
║  验证所有模块、API 和前端是否正常工作                      ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    results = {
        "模块导入": check_module_imports(),
        "数据库": check_database(),
        "MCP 工具": check_mcp_tools(),
        "API 服务器": check_api_server(),
        "前端文件": check_frontend(),
    }
    
    print_header("验证结果汇总")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        print_result(name, success)
    
    print(f"\n  总计: {passed}/{total} 通过")
    
    if passed == total:
        print("""
╔════════════════════════════════════════════════════════════╗
║  ✅ 所有验证通过！系统已准备就绪。                         ║
║                                                            ║
║  启动服务:                                                 ║
║    python run_api_server.py                                ║
║                                                            ║
║  打开前端:                                                 ║
║    浏览器打开 frontend/index.html                          ║
╚════════════════════════════════════════════════════════════╝
        """)
    else:
        print("""
╔════════════════════════════════════════════════════════════╗
║  ⚠️  部分验证未通过，请检查上述错误。                      ║
║                                                            ║
║  常见问题:                                                 ║
║    1. 数据库为空 → 运行 python start.py index              ║
║    2. API 未启动 → 运行 python run_api_server.py           ║
║    3. 缺少依赖 → 运行 pip install -r requirements.txt      ║
╚════════════════════════════════════════════════════════════╝
        """)
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
