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
                "/hot": "GET - 热门市场"
            },
            "timestamp": datetime.now().isoformat()
        })
    
    @app.route("/health", methods=["GET"])
    def health():
        """健康检查"""
        return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})
    
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
    """MCP Server 封装类"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = create_app()
    
    def run(self, debug: bool = False):
        """启动服务器"""
        logger.info(f"Starting PolyMind MCP Server on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=debug)


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="PolyMind MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址")
    parser.add_argument("--port", type=int, default=8080, help="端口号")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    
    args = parser.parse_args()
    
    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()
    
    server = MCPServer(host=args.host, port=args.port)
    server.run(debug=args.debug)


if __name__ == "__main__":
    main()
