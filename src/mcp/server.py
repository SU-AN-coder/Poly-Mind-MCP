"""
PolyMind MCP Server
HTTP API 服务，供 AI Agent 调用
增强版：包含监控指标、请求日志和 NL 查询模板
"""
import os
import re
import json
import logging
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime
from functools import wraps
from collections import deque

from flask import Flask, request, jsonify
from flask_cors import CORS

from .tools import PolymarketTools

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# 监控指标类
# =============================================================================
class RequestMetrics:
    """请求监控指标"""
    
    def __init__(self, max_logs: int = 1000):
        self.total_requests = 0
        self.success_count = 0
        self.error_count = 0
        self.latencies: List[float] = []
        self.start_time = datetime.now()
        self.logs: deque = deque(maxlen=max_logs)
        self._lock = threading.Lock()
    
    def record_request(self, endpoint: str, method: str, status: int, 
                       latency_ms: float, error: Optional[str] = None):
        """记录一次请求"""
        with self._lock:
            self.total_requests += 1
            if status < 400:
                self.success_count += 1
            else:
                self.error_count += 1
            self.latencies.append(latency_ms)
            # 只保留最近 10000 条延迟记录
            if len(self.latencies) > 10000:
                self.latencies = self.latencies[-10000:]
            
            self.logs.append({
                "timestamp": datetime.now().isoformat(),
                "endpoint": endpoint,
                "method": method,
                "status": status,
                "latency_ms": round(latency_ms, 2),
                "error": error
            })
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取统计指标"""
        with self._lock:
            uptime = (datetime.now() - self.start_time).total_seconds()
            avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
            p95_latency = sorted(self.latencies)[int(len(self.latencies) * 0.95)] if len(self.latencies) > 20 else avg_latency
            
            return {
                "total_requests": self.total_requests,
                "success_count": self.success_count,
                "error_count": self.error_count,
                "success_rate": self.success_count / self.total_requests if self.total_requests > 0 else 1.0,
                "avg_latency_ms": round(avg_latency, 2),
                "p95_latency_ms": round(p95_latency, 2),
                "uptime_seconds": round(uptime, 0),
                "requests_per_minute": round(self.total_requests / (uptime / 60), 2) if uptime > 0 else 0
            }
    
    def get_logs(self, limit: int = 100) -> List[Dict]:
        """获取最近的请求日志"""
        with self._lock:
            return list(self.logs)[-limit:]


# =============================================================================
# NL 查询模板
# =============================================================================
NL_QUERY_TEMPLATES = [
    {
        "pattern": r"分析交易者\s*(0x[a-fA-F0-9]+)",
        "tool": "analyze_trader",
        "extract": lambda m: {"address": m.group(1)},
        "description": "分析交易者策略"
    },
    {
        "pattern": r"搜索.*?(?:关于|about)?\s*(.+?)\s*(?:的)?市场",
        "tool": "search_markets",
        "extract": lambda m: {"query": m.group(1).strip(), "limit": 10},
        "description": "搜索市场"
    },
    {
        "pattern": r"(?:查找|寻找|获取).*?套利",
        "tool": "find_arbitrage",
        "extract": lambda m: {"limit": 20},
        "description": "查找套利机会"
    },
    {
        "pattern": r"(?:查看|获取).*?(.+?)\s*(?:市场)?.*?聪明钱",
        "tool": "get_smart_money_activity",
        "extract": lambda m: {"market_slug": m.group(1).strip(), "min_win_rate": 55},
        "description": "获取聪明钱活动"
    },
    {
        "pattern": r"(?:获取|查看).*?热门.*?(\d+)?.*?市场",
        "tool": "get_hot_markets",
        "extract": lambda m: {"limit": int(m.group(1)) if m.group(1) else 10, "sort_by": "volume"},
        "description": "获取热门市场"
    },
]


def match_nl_query(query: str) -> Optional[Dict]:
    """匹配自然语言查询模板"""
    for template in NL_QUERY_TEMPLATES:
        match = re.search(template["pattern"], query, re.IGNORECASE)
        if match:
            return {
                "matched_template": template["description"],
                "tool": template["tool"],
                "arguments": template["extract"](match)
            }
    return None


# 全局监控实例
metrics = RequestMetrics()


def create_app() -> Flask:
    """创建 Flask 应用"""
    app = Flask(__name__)
    CORS(app)  # 允许跨域
    
    # 初始化工具
    tools = PolymarketTools()
    
    # =========================================================================
    # 健康检查
    # =========================================================================
    @app.route("/", methods=["GET"])
    def index():
        """API 首页"""
        return jsonify({
            "service": "PolyMind MCP Server",
            "version": "1.0.0",
            "description": "AI-powered Polymarket data interface",
            "endpoints": {
                "/tools": "GET - 获取可用工具列表",
                "/tools/call": "POST - 调用工具",
                "/markets/search": "GET - 搜索市场",
                "/markets/<slug>": "GET - 获取市场详情",
                "/markets/<slug>/advice": "GET - 获取交易建议",
                "/arbitrage": "GET - 扫描套利机会",
                "/trader/<address>": "GET - 分析交易者",
                "/hot": "GET - 热门市场",
                "/stats": "GET - 仪表盘统计",
                "/trades/recent": "GET - 最近交易"
            },
            "quick_start": "python start.py demo",
            "timestamp": datetime.now().isoformat()
        })
    
    @app.route("/health", methods=["GET"])
    def health():
        """增强版健康检查 - 包含数据状态"""
        try:
            from src.db.schema import get_connection
            import os
            
            db_path = os.getenv("DB_PATH", "data/polymarket.db")
            
            # 检查数据库文件是否存在
            if not os.path.exists(db_path):
                return jsonify({
                    "status": "warning",
                    "message": "数据库不存在，请运行: python start.py demo",
                    "data_ready": False,
                    "trade_count": 0,
                    "market_count": 0,
                    "suggestion": "运行 python start.py demo 导入演示数据",
                    "timestamp": datetime.now().isoformat()
                })
            
            conn = get_connection(db_path)
            cursor = conn.cursor()
            
            # 获取统计数据
            cursor.execute("SELECT COUNT(*) FROM trades")
            trade_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM markets")
            market_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT maker) FROM trades")
            trader_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT last_block FROM indexer_state WHERE id = 1")
            row = cursor.fetchone()
            last_block = row[0] if row else 0
            
            conn.close()
            
            data_ready = trade_count >= 100
            
            return jsonify({
                "status": "healthy" if data_ready else "warning",
                "message": "系统正常，数据就绪" if data_ready else f"数据不足，还需 {100 - trade_count} 条交易",
                "data_ready": data_ready,
                "trade_count": trade_count,
                "market_count": market_count,
                "trader_count": trader_count,
                "last_indexed_block": last_block,
                "min_required_trades": 100,
                "suggestion": None if data_ready else "运行: python start.py demo",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e),
                "data_ready": False,
                "suggestion": "检查数据库配置",
                "timestamp": datetime.now().isoformat()
            }), 500

    # =========================================================================
    # MCP 标准接口
    # =========================================================================
    @app.route("/tools", methods=["GET"])
    def list_tools():
        """
        列出所有可用工具
        符合 MCP 协议的工具发现接口
        """
        return jsonify({
            "tools": tools.get_tool_definitions(),
            "count": len(tools.get_tool_definitions()),
            "protocol": "MCP/1.0"
        })
    
    @app.route("/tools/call", methods=["POST"])
    def call_tool():
        """
        调用工具
        MCP 标准工具调用接口
        
        Request Body:
        {
            "name": "tool_name",
            "arguments": {...}
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "请求体不能为空"}), 400
            
            tool_name = data.get("name")
            arguments = data.get("arguments", {})
            
            if not tool_name:
                return jsonify({"error": "缺少工具名称"}), 400
            
            logger.info(f"调用工具: {tool_name}, 参数: {arguments}")
            
            result = tools.execute_tool(tool_name, arguments)
            
            return jsonify({
                "tool": tool_name,
                "result": result,
                "success": "error" not in result,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"工具调用失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    # =========================================================================
    # 便捷 REST API（直接访问，无需 MCP 协议）
    # =========================================================================
    @app.route("/markets/search", methods=["GET"])
    def search_markets():
        """搜索市场"""
        query = request.args.get("q", "")
        limit = int(request.args.get("limit", 10))
        
        if not query:
            return jsonify({"error": "缺少搜索关键词 ?q=..."}), 400
        
        result = tools.execute_tool("search_markets", {
            "query": query,
            "limit": limit
        })
        return jsonify(result)
    
    @app.route("/markets/<slug>", methods=["GET"])
    def get_market(slug: str):
        """获取市场详情"""
        result = tools.execute_tool("get_market_info", {"market_slug": slug})
        return jsonify(result)
    
    @app.route("/markets/<slug>/advice", methods=["GET"])
    def get_market_advice(slug: str):
        """获取交易建议"""
        user_intent = request.args.get("intent", "")
        result = tools.execute_tool("get_trading_advice", {
            "market_slug": slug,
            "user_intent": user_intent
        })
        return jsonify(result)
    
    @app.route("/arbitrage", methods=["GET"])
    def find_arbitrage():
        """扫描套利机会"""
        limit = int(request.args.get("limit", 20))
        result = tools.execute_tool("find_arbitrage", {"limit": limit})
        return jsonify(result)
    
    @app.route("/trader/<address>", methods=["GET"])
    def analyze_trader(address: str):
        """分析交易者"""
        result = tools.execute_tool("analyze_trader", {"address": address})
        return jsonify(result)
    
    @app.route("/hot", methods=["GET"])
    def get_hot_markets():
        """获取热门市场"""
        limit = int(request.args.get("limit", 10))
        sort_by = request.args.get("sort", "volume")
        result = tools.execute_tool("get_hot_markets", {
            "limit": limit,
            "sort_by": sort_by
        })
        return jsonify(result)
    
    @app.route("/smart-money", methods=["GET"])
    def get_smart_money():
        """获取聪明钱活动"""
        market_slug = request.args.get("market")
        min_win_rate = float(request.args.get("min_win_rate", 60))
        result = tools.execute_tool("get_smart_money_activity", {
            "market_slug": market_slug,
            "min_win_rate": min_win_rate
        })
        return jsonify(result)
    
    # =========================================================================
    # 监控与日志接口
    # =========================================================================
    @app.route("/metrics", methods=["GET"])
    def get_metrics():
        """获取系统监控指标"""
        return jsonify(metrics.get_metrics())
    
    @app.route("/logs", methods=["GET"])
    def get_logs():
        """获取请求日志"""
        limit = int(request.args.get("limit", 100))
        return jsonify({"logs": metrics.get_logs(limit)})
    
    # =========================================================================
    # 自然语言查询接口
    # =========================================================================
    @app.route("/nl-query", methods=["POST"])
    def nl_query():
        """
        自然语言查询接口
        自动匹配模板并执行相应工具
        """
        start_time = time.time()
        try:
            data = request.get_json()
            query = data.get("query", "")
            
            if not query:
                return jsonify({"error": "缺少查询内容"}), 400
            
            # 尝试匹配模板
            match_result = match_nl_query(query)
            
            if match_result:
                # 匹配成功，执行对应工具
                result = tools.execute_tool(match_result["tool"], match_result["arguments"])
                latency = (time.time() - start_time) * 1000
                metrics.record_request("/nl-query", "POST", 200, latency)
                
                return jsonify({
                    "matched_template": match_result["matched_template"],
                    "tool": match_result["tool"],
                    "arguments": match_result["arguments"],
                    "result": result
                })
            else:
                # 未匹配到模板
                latency = (time.time() - start_time) * 1000
                metrics.record_request("/nl-query", "POST", 200, latency)
                
                return jsonify({
                    "matched_template": None,
                    "message": "未匹配到预设模板，请尝试更具体的查询",
                    "available_templates": [t["description"] for t in NL_QUERY_TEMPLATES]
                })
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            metrics.record_request("/nl-query", "POST", 500, latency, str(e))
            logger.error(f"NL 查询失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    # =========================================================================
    # 交易者时序分析接口
    # =========================================================================
    @app.route("/trader/<address>/timing", methods=["GET"])
    def get_trader_timing(address: str):
        """获取交易者时序分析"""
        start_time = time.time()
        try:
            result = tools.execute_tool("analyze_trader_timing", {"address": address})
            latency = (time.time() - start_time) * 1000
            metrics.record_request(f"/trader/{address}/timing", "GET", 200, latency)
            return jsonify(result)
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            metrics.record_request(f"/trader/{address}/timing", "GET", 500, latency, str(e))
            return jsonify({"error": str(e)}), 500
    
    # =========================================================================
    # 仪表盘数据接口（真实数据）
    # =========================================================================
    @app.route("/stats", methods=["GET"])
    def get_dashboard_stats():
        """获取仪表盘统计数据（真实数据库数据）"""
        try:
            from src.db.schema import get_connection
            db_path = os.getenv("DB_PATH", "data/polymarket.db")
            conn = get_connection(db_path)
            cursor = conn.cursor()
            
            # 获取交易统计
            cursor.execute("SELECT COUNT(*) as total_trades FROM trades")
            total_trades = cursor.fetchone()[0] or 0
            
            # 获取唯一交易者数量
            cursor.execute("SELECT COUNT(DISTINCT maker) as unique_traders FROM trades")
            unique_traders = cursor.fetchone()[0] or 0
            
            # 获取市场数量
            cursor.execute("SELECT COUNT(*) as total_markets FROM markets")
            total_markets = cursor.fetchone()[0] or 0
            
            # 获取总交易量估算 (基于 maker_amount + taker_amount)
            cursor.execute("""
                SELECT SUM(CAST(maker_amount AS REAL) + CAST(taker_amount AS REAL)) / 1e6 as volume
                FROM trades
            """)
            result = cursor.fetchone()
            total_volume = result[0] if result and result[0] else 0
            
            # 获取聪明钱数量 (胜率 > 55%)
            cursor.execute("""
                SELECT COUNT(*) FROM trader_profiles WHERE win_rate > 55
            """)
            smart_money_count = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return jsonify({
                "total_trades": total_trades,
                "unique_traders": unique_traders,
                "total_markets": total_markets,
                "total_volume": round(total_volume, 2),
                "smart_money_count": smart_money_count,
                "avg_win_rate": 0.58,  # 可根据实际数据计算
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"获取统计数据失败: {e}")
            return jsonify({
                "total_trades": 0,
                "unique_traders": 0,
                "total_markets": 0,
                "total_volume": 0,
                "smart_money_count": 0,
                "avg_win_rate": 0.58,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    @app.route("/trades/recent", methods=["GET"])
    def get_recent_trades():
        """获取最近的真实交易数据"""
        try:
            limit = int(request.args.get("limit", 20))
            from src.db.schema import get_connection
            db_path = os.getenv("DB_PATH", "data/polymarket.db")
            conn = get_connection(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    t.tx_hash,
                    t.maker,
                    t.taker,
                    t.side,
                    t.maker_amount,
                    t.taker_amount,
                    t.block_number,
                    t.timestamp,
                    m.slug as market_slug,
                    m.question as market_title
                FROM trades t
                LEFT JOIN markets m ON t.market_slug = m.slug
                ORDER BY t.block_number DESC
                LIMIT ?
            """, (limit,))
            
            trades = []
            for row in cursor.fetchall():
                # 计算价格 (简化计算)
                maker_amount = float(row[4] or 0) / 1e6
                taker_amount = float(row[5] or 0) / 1e6
                price = taker_amount / maker_amount if maker_amount > 0 else 0
                
                trades.append({
                    "tx_hash": row[0],
                    "maker": row[1],
                    "taker": row[2],
                    "side": row[3] or "BUY",
                    "maker_amount": maker_amount,
                    "taker_amount": taker_amount,
                    "price": round(price, 4),
                    "size": round(maker_amount, 2),
                    "block_number": row[6],
                    "timestamp": row[7],
                    "market_slug": row[8],
                    "market_title": row[9]
                })
            
            conn.close()
            
            return jsonify({
                "trades": trades,
                "count": len(trades),
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"获取交易数据失败: {e}")
            return jsonify({
                "trades": [],
                "count": 0,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    # =========================================================================
    # PnL（盈亏）计算接口
    # =========================================================================
    @app.route("/trader/<address>/pnl", methods=["GET"])
    def get_trader_pnl(address: str):
        """获取交易者持仓盈亏"""
        try:
            from src.mcp.pnl_calculator import get_pnl_calculator
            calculator = get_pnl_calculator()
            portfolio = calculator.calculate_portfolio_pnl(address)
            return jsonify({"success": True, "portfolio": portfolio.to_dict()})
        except ImportError:
            # PnL 模块未安装，返回占位数据
            return jsonify({
                "success": True,
                "portfolio": {
                    "address": address,
                    "total_invested": 0,
                    "total_current_value": 0,
                    "unrealized_pnl": 0,
                    "realized_pnl": 0,
                    "positions": [],
                    "message": "PnL 计算模块未启用"
                },
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/trader/<address>/positions", methods=["GET"])
    def get_trader_positions(address: str):
        """获取交易者持仓列表"""
        try:
            from src.mcp.pnl_calculator import get_pnl_calculator
            
            include_closed = request.args.get("include_closed", "false").lower() == "true"
            calculator = get_pnl_calculator()
            positions = calculator.get_trader_positions(address, include_closed)
            
            return jsonify({
                "success": True,
                "address": address,
                "positions": positions,
                "count": len(positions),
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/leaderboard/pnl", methods=["GET"])
    def get_pnl_leaderboard():
        """获取盈亏排行榜"""
        try:
            from src.mcp.pnl_calculator import get_pnl_calculator
            
            market_slug = request.args.get("market")
            limit = int(request.args.get("limit", 20))
            
            calculator = get_pnl_calculator()
            leaderboard = calculator.get_market_pnl_leaderboard(market_slug, limit)
            
            return jsonify({
                "success": True,
                "market": market_slug or "all",
                "leaderboard": leaderboard,
                "count": len(leaderboard),
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"获取排行榜失败: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # =========================================================================
    # 缓存管理接口
    # =========================================================================
    @app.route("/cache/stats", methods=["GET"])
    def get_cache_stats():
        """获取缓存统计信息"""
        try:
            from src.cache import get_cache
            cache = get_cache()
            return jsonify({"success": True, "stats": cache.get_stats()})
        except ImportError:
            return jsonify({
                "success": True,
                "stats": {
                    "enabled": False,
                    "message": "缓存模块未安装"
                }
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    @app.route("/cache/flush", methods=["POST"])
    def flush_cache():
        """清空缓存"""
        try:
            from src.cache import get_cache
            cache = get_cache()
            cache.flush()
            return jsonify({
                "success": True,
                "message": "缓存已清空",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    # =========================================================================
    # WebSocket 状态接口
    # =========================================================================
    @app.route("/ws/stats", methods=["GET"])
    def get_ws_stats():
        """获取 WebSocket 连接统计"""
        try:
            from src.mcp.websocket import ws_manager
            return jsonify({"success": True, "stats": ws_manager.get_stats()})
        except ImportError:
            return jsonify({
                "success": True,
                "stats": {
                    "enabled": False,
                    "connections": 0,
                    "message": "WebSocket 未启用，需安装 flask-socketio"
                }
            })
    
    # =========================================================================
    # 请求监控中间件
    # =========================================================================
    @app.before_request
    def before_request():
        """记录请求开始时间"""
        request.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        """记录请求指标"""
        if hasattr(request, 'start_time'):
            latency = (time.time() - request.start_time) * 1000
            # 排除监控相关接口，避免循环
            if request.path not in ['/metrics', '/logs', '/health']:
                error = None
                if response.status_code >= 400:
                    try:
                        error = response.get_json().get('error')
                    except:
                        error = 'Unknown error'
                metrics.record_request(request.path, request.method, response.status_code, latency, error)
        return response
    
    # =========================================================================
    # OpenAI Function Calling 兼容接口
    # =========================================================================
    @app.route("/openai/functions", methods=["GET"])
    def get_openai_functions():
        """
        返回 OpenAI Function Calling 格式的函数定义
        可直接用于 ChatGPT/GPT-4 的 function calling
        """
        return jsonify({
            "functions": tools.get_tool_definitions(),
            "usage": "将这些函数定义传递给 OpenAI API 的 tools 参数"
        })
    
    @app.route("/openai/execute", methods=["POST"])
    def execute_openai_function():
        """
        执行 OpenAI Function Call 返回的函数调用
        
        Request Body (来自 OpenAI 的 tool_calls):
        {
            "id": "call_xxx",
            "type": "function",
            "function": {
                "name": "get_market_info",
                "arguments": "{\"market_slug\": \"trump-wins\"}"
            }
        }
        """
        try:
            data = request.get_json()
            
            # 支持单个或批量调用
            if isinstance(data, list):
                results = []
                for call in data:
                    func = call.get("function", {})
                    name = func.get("name")
                    args = json.loads(func.get("arguments", "{}"))
                    result = tools.execute_tool(name, args)
                    results.append({
                        "tool_call_id": call.get("id"),
                        "result": result
                    })
                return jsonify({"results": results})
            else:
                func = data.get("function", {})
                name = func.get("name")
                args = json.loads(func.get("arguments", "{}"))
                result = tools.execute_tool(name, args)
                return jsonify({
                    "tool_call_id": data.get("id"),
                    "result": result
                })
                
        except Exception as e:
            logger.error(f"OpenAI 函数执行失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    # =========================================================================
    # 错误处理
    # =========================================================================
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "接口不存在", "path": request.path}), 404
    
    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "服务器内部错误"}), 500
    
    return app


class MCPServer:
    """MCP Server 封装类（支持 WebSocket）"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8888):  # 改为 8888
        self.host = host
        self.port = port
        self.app = create_app()
        self.socketio = None
    
    def init_websocket(self):
        """初始化 WebSocket 支持"""
        try:
            from src.mcp.websocket import init_websocket
            self.socketio = init_websocket(self.app)
            logger.info("✓ WebSocket 已启用")
            return self.socketio
        except ImportError:
            logger.warning("flask-socketio 未安装，WebSocket 不可用")
            return None
        except Exception as e:
            logger.error(f"WebSocket 初始化失败: {e}")
            return None
    
    def run(self, debug: bool = False, use_websocket: bool = True):
        """启动服务器"""
        logger.info(f"Starting PolyMind MCP Server on {self.host}:{self.port}")
        
        if use_websocket:
            self.init_websocket()
        
        if self.socketio:
            # 使用 SocketIO 运行（支持 WebSocket）
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=debug,
                allow_unsafe_werkzeug=True
            )
        else:
            # 普通 Flask 运行
            self.app.run(host=self.host, port=self.port, debug=debug)


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="PolyMind MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址")
    parser.add_argument("--port", type=int, default=8888, help="端口号")  # 改为 8888
    parser.add_argument("--debug", action="store_true", help="调试模式")
    
    args = parser.parse_args()
    
    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()
    
    server = MCPServer(host=args.host, port=args.port)
    server.run(debug=args.debug)


if __name__ == "__main__":
    main()
