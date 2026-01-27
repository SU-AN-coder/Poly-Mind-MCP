"""
PolyMind MCP Server - 标准 MCP 协议实现
使用 JSON-RPC over stdio 传输，符合 Model Context Protocol 规范

支持:
- Claude Desktop
- Cursor
- 其他 MCP 兼容客户端
"""
import sys
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.mcp.tools import PolymarketTools
from src.mcp.profiler import TraderProfiler
from src.mcp.advisor import TradeAdvisor

# 配置日志到 stderr（stdout 用于 JSON-RPC）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


class MCPServer:
    """
    Model Context Protocol Server
    实现 JSON-RPC 2.0 over stdio
    """
    
    def __init__(self):
        self.tools = PolymarketTools()
        self.profiler = TraderProfiler()
        self.advisor = TradeAdvisor()
        
        # MCP 协议信息
        self.protocol_version = "2024-11-05"
        self.server_info = {
            "name": "polymind-mcp",
            "version": "1.0.0"
        }
        self.capabilities = {
            "tools": {},
            "resources": {},
            "prompts": {}
        }
        
        # 工具映射
        self.tool_handlers = {
            "get_market_info": self._handle_get_market_info,
            "search_markets": self._handle_search_markets,
            "analyze_trader": self._handle_analyze_trader,
            "get_trading_advice": self._handle_get_trading_advice,
            "find_arbitrage": self._handle_find_arbitrage,
            "get_smart_money_activity": self._handle_get_smart_money,
            "get_hot_markets": self._handle_get_hot_markets,
            "analyze_market_relationship": self._handle_analyze_relationship,
            "natural_language_query": self._handle_nl_query,
        }
    
    def _write_response(self, response: Dict):
        """写入 JSON-RPC 响应到 stdout"""
        json_str = json.dumps(response, ensure_ascii=False)
        sys.stdout.write(json_str + "\n")
        sys.stdout.flush()
    
    def _create_response(self, id: Any, result: Any) -> Dict:
        """创建 JSON-RPC 成功响应"""
        return {
            "jsonrpc": "2.0",
            "id": id,
            "result": result
        }
    
    def _create_error(self, id: Any, code: int, message: str, data: Any = None) -> Dict:
        """创建 JSON-RPC 错误响应"""
        error = {
            "code": code,
            "message": message
        }
        if data:
            error["data"] = data
        return {
            "jsonrpc": "2.0",
            "id": id,
            "error": error
        }
    
    async def handle_request(self, request: Dict) -> Dict:
        """处理 JSON-RPC 请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")
        
        logger.info(f"收到请求: {method}")
        
        try:
            if method == "initialize":
                return self._handle_initialize(req_id, params)
            elif method == "initialized":
                return None  # 通知消息，不需要响应
            elif method == "tools/list":
                return self._handle_tools_list(req_id)
            elif method == "tools/call":
                return await self._handle_tools_call(req_id, params)
            elif method == "resources/list":
                return self._handle_resources_list(req_id)
            elif method == "prompts/list":
                return self._handle_prompts_list(req_id)
            elif method == "ping":
                return self._create_response(req_id, {})
            else:
                return self._create_error(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            logger.error(f"处理请求失败: {e}")
            return self._create_error(req_id, -32603, str(e))
    
    def _handle_initialize(self, req_id: Any, params: Dict) -> Dict:
        """处理 initialize 请求"""
        logger.info(f"MCP 客户端初始化: {params.get('clientInfo', {})}")
        
        return self._create_response(req_id, {
            "protocolVersion": self.protocol_version,
            "serverInfo": self.server_info,
            "capabilities": self.capabilities
        })
    
    def _handle_tools_list(self, req_id: Any) -> Dict:
        """返回可用工具列表"""
        tools = [
            {
                "name": "get_market_info",
                "description": "获取 Polymarket 市场详细信息，包括当前价格、交易量、流动性等",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "market_slug": {
                            "type": "string",
                            "description": "市场 slug，例如 'will-trump-win-2024'"
                        }
                    },
                    "required": ["market_slug"]
                }
            },
            {
                "name": "search_markets",
                "description": "搜索 Polymarket 市场，支持关键词搜索",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词，例如 'Trump', 'Bitcoin', 'Fed'"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回结果数量限制，默认10",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "analyze_trader",
                "description": "分析交易者地址的行为模式，生成交易画像和语义标签（如'聪明钱'、'巨鲸'、'套利者'）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "以太坊/Polygon 钱包地址"
                        }
                    },
                    "required": ["address"]
                }
            },
            {
                "name": "get_trading_advice",
                "description": "获取特定市场的交易建议，包括套利机会、关联市场分析",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "market_slug": {
                            "type": "string",
                            "description": "市场 slug"
                        },
                        "user_intent": {
                            "type": "string",
                            "description": "用户意图，例如'我看好 Trump 当选'"
                        }
                    },
                    "required": ["market_slug"]
                }
            },
            {
                "name": "find_arbitrage",
                "description": "扫描所有市场，发现 YES+NO 套利机会或跨市场价差套利",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "min_profit": {
                            "type": "number",
                            "description": "最小利润率阈值（百分比），默认1%",
                            "default": 1.0
                        }
                    }
                }
            },
            {
                "name": "get_smart_money_activity",
                "description": "获取聪明钱（高胜率交易者）的最近交易活动",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "market_slug": {
                            "type": "string",
                            "description": "可选，限定特定市场"
                        },
                        "hours": {
                            "type": "integer",
                            "description": "时间范围（小时），默认24",
                            "default": 24
                        }
                    }
                }
            },
            {
                "name": "get_hot_markets",
                "description": "获取当前热门市场，按交易量或价格波动排序",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sort_by": {
                            "type": "string",
                            "enum": ["volume", "volatility", "liquidity"],
                            "description": "排序方式",
                            "default": "volume"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回数量",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "analyze_market_relationship",
                "description": "分析两个市场之间的逻辑关系，检测价格滞后或套利机会。例如分析 'Trump当选' 和 '共和党执政' 的关系",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "market_a": {
                            "type": "string",
                            "description": "第一个市场 slug"
                        },
                        "market_b": {
                            "type": "string",
                            "description": "第二个市场 slug"
                        }
                    },
                    "required": ["market_a", "market_b"]
                }
            },
            {
                "name": "natural_language_query",
                "description": "使用自然语言查询 Polymarket 数据。例如：'帮我找出最近24小时胜率超过60%的聪明钱在Trump市场的操作'",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言查询"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
        
        return self._create_response(req_id, {"tools": tools})
    
    async def _handle_tools_call(self, req_id: Any, params: Dict) -> Dict:
        """处理工具调用"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        logger.info(f"调用工具: {tool_name}, 参数: {arguments}")
        
        handler = self.tool_handlers.get(tool_name)
        if not handler:
            return self._create_error(req_id, -32602, f"Unknown tool: {tool_name}")
        
        try:
            result = await handler(arguments)
            return self._create_response(req_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }
                ]
            })
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return self._create_response(req_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": str(e)}, ensure_ascii=False)
                    }
                ],
                "isError": True
            })
    
    def _handle_resources_list(self, req_id: Any) -> Dict:
        """返回资源列表"""
        return self._create_response(req_id, {"resources": []})
    
    def _handle_prompts_list(self, req_id: Any) -> Dict:
        """返回提示词列表"""
        prompts = [
            {
                "name": "analyze_whale_activity",
                "description": "分析巨鲸在特定市场的活动",
                "arguments": [
                    {"name": "market", "description": "市场名称或关键词", "required": True}
                ]
            },
            {
                "name": "find_trading_opportunity",
                "description": "寻找交易机会和套利空间",
                "arguments": []
            }
        ]
        return self._create_response(req_id, {"prompts": prompts})
    
    # =========================================================================
    # 工具处理函数
    # =========================================================================
    
    async def _handle_get_market_info(self, args: Dict) -> Dict:
        """获取市场信息"""
        market_slug = args.get("market_slug", "")
        return self.tools.get_market_info(market_slug)
    
    async def _handle_search_markets(self, args: Dict) -> Dict:
        """搜索市场"""
        query = args.get("query", "")
        limit = args.get("limit", 10)
        return self.tools.search_markets(query, limit)
    
    async def _handle_analyze_trader(self, args: Dict) -> Dict:
        """分析交易者"""
        address = args.get("address", "")
        return self.tools.analyze_trader(address)
    
    async def _handle_get_trading_advice(self, args: Dict) -> Dict:
        """获取交易建议"""
        market_slug = args.get("market_slug", "")
        user_intent = args.get("user_intent", "")
        return self.tools.get_trading_advice(market_slug, user_intent)
    
    async def _handle_find_arbitrage(self, args: Dict) -> Dict:
        """发现套利机会"""
        min_profit = args.get("min_profit", 1.0)
        return self.tools.find_arbitrage(min_profit)
    
    async def _handle_get_smart_money(self, args: Dict) -> Dict:
        """获取聪明钱活动"""
        market_slug = args.get("market_slug")
        hours = args.get("hours", 24)
        return self.tools.get_smart_money_activity(market_slug, hours)
    
    async def _handle_get_hot_markets(self, args: Dict) -> Dict:
        """获取热门市场"""
        sort_by = args.get("sort_by", "volume")
        limit = args.get("limit", 10)
        return self.tools.get_hot_markets(sort_by, limit)
    
    async def _handle_analyze_relationship(self, args: Dict) -> Dict:
        """分析市场关系"""
        market_a = args.get("market_a", "")
        market_b = args.get("market_b", "")
        
        # 使用 LLM 分析逻辑关系
        return await self._llm_analyze_relationship(market_a, market_b)
    
    async def _handle_nl_query(self, args: Dict) -> Dict:
        """处理自然语言查询"""
        query = args.get("query", "")
        return await self._process_natural_language_query(query)
    
    async def _llm_analyze_relationship(self, market_a: str, market_b: str) -> Dict:
        """使用 LLM 分析两个市场的逻辑关系"""
        import requests
        
        # 获取两个市场的信息
        info_a = self.tools.get_market_info(market_a)
        info_b = self.tools.get_market_info(market_b)
        
        if "error" in info_a or "error" in info_b:
            return {
                "error": "无法获取市场信息",
                "market_a": info_a,
                "market_b": info_b
            }
        
        # 检测价格套利
        cross_arb = self.advisor.detect_cross_market_opportunity(market_a, market_b)
        
        # 使用 LLM 分析逻辑关系
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            return {
                "market_a": info_a,
                "market_b": info_b,
                "arbitrage": cross_arb.__dict__ if cross_arb else None,
                "relationship": "需要 OpenAI API Key 进行深度分析"
            }
        
        prompt = f"""分析以下两个 Polymarket 预测市场之间的逻辑关系：

市场 A: {info_a.get('title', market_a)}
- 当前 YES 价格: {info_a.get('yes_price', 'N/A')}
- 当前 NO 价格: {info_a.get('no_price', 'N/A')}

市场 B: {info_b.get('title', market_b)}
- 当前 YES 价格: {info_b.get('yes_price', 'N/A')}
- 当前 NO 价格: {info_b.get('no_price', 'N/A')}

请分析：
1. 这两个市场之间是否存在逻辑蕴含关系？（如 A 发生则 B 必然发生）
2. 如果存在关系，当前价格是否存在不一致（价格滞后）？
3. 是否存在套利机会？

用 JSON 格式回复：
{{"relationship_type": "包含/互斥/独立/相关", "logical_analysis": "...", "price_anomaly": true/false, "trading_suggestion": "..."}}
"""
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "你是预测市场分析专家，擅长发现市场之间的逻辑关系和套利机会。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                try:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        analysis = json.loads(content[start:end])
                    else:
                        analysis = {"raw_response": content}
                except:
                    analysis = {"raw_response": content}
                
                return {
                    "market_a": info_a,
                    "market_b": info_b,
                    "arbitrage": cross_arb.__dict__ if cross_arb else None,
                    "llm_analysis": analysis
                }
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
        
        return {
            "market_a": info_a,
            "market_b": info_b,
            "arbitrage": cross_arb.__dict__ if cross_arb else None,
            "relationship": "分析失败"
        }
    
    async def _process_natural_language_query(self, query: str) -> Dict:
        """处理自然语言查询，将其转换为工具调用"""
        import requests
        
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            return {"error": "需要 OpenAI API Key 进行自然语言处理"}
        
        # 使用 LLM 理解用户意图并生成工具调用
        prompt = f"""你是 Polymarket 数据分析助手。用户提出了以下查询：

"{query}"

请分析用户意图，并决定应该调用哪些工具。可用工具：
1. search_markets(query) - 搜索市场
2. get_market_info(market_slug) - 获取市场详情
3. analyze_trader(address) - 分析交易者
4. find_arbitrage() - 发现套利机会
5. get_smart_money_activity(market_slug, hours) - 获取聪明钱活动
6. get_hot_markets(sort_by, limit) - 获取热门市场

用 JSON 格式回复你的分析和建议的工具调用序列：
{{"intent": "用户意图", "tool_calls": [{{"tool": "工具名", "args": {{...}}}}], "explanation": "解释"}}
"""
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "你是一个智能数据分析助手，帮助用户查询 Polymarket 预测市场数据。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                try:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        plan = json.loads(content[start:end])
                    else:
                        return {"raw_response": content, "query": query}
                except:
                    return {"raw_response": content, "query": query}
                
                # 执行工具调用
                results = []
                for call in plan.get("tool_calls", []):
                    tool_name = call.get("tool", "")
                    tool_args = call.get("args", {})
                    
                    handler = self.tool_handlers.get(tool_name)
                    if handler:
                        try:
                            result = await handler(tool_args)
                            results.append({
                                "tool": tool_name,
                                "result": result
                            })
                        except Exception as e:
                            results.append({
                                "tool": tool_name,
                                "error": str(e)
                            })
                
                return {
                    "query": query,
                    "intent": plan.get("intent", ""),
                    "explanation": plan.get("explanation", ""),
                    "results": results
                }
                
        except Exception as e:
            logger.error(f"自然语言处理失败: {e}")
            return {"error": str(e), "query": query}
    
    async def run(self):
        """运行 MCP 服务器（stdio 模式）"""
        logger.info("PolyMind MCP Server 启动 (stdio 模式)")
        
        while True:
            try:
                # 从 stdin 读取一行
                line = sys.stdin.readline()
                if not line:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # 解析 JSON-RPC 请求
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    self._write_response(self._create_error(None, -32700, f"Parse error: {e}"))
                    continue
                
                # 处理请求
                response = await self.handle_request(request)
                
                # 发送响应（如果有）
                if response:
                    self._write_response(response)
                    
            except KeyboardInterrupt:
                logger.info("服务器关闭")
                break
            except Exception as e:
                logger.error(f"服务器错误: {e}")


def main():
    """入口函数"""
    server = MCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
