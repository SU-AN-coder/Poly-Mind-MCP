"""
MCP 工具定义
定义可被 AI Agent 调用的工具集
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import requests

from .profiler import TraderProfiler
from .advisor import TradeAdvisor
from src.db.schema import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: Dict
    

class PolymarketTools:
    """Polymarket MCP 工具集"""
    
    def __init__(self):
        self.profiler = TraderProfiler()
        self.advisor = TradeAdvisor()
        self.gamma_base_url = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
        self.db_path = os.getenv("DB_PATH", "polymarket.db")
    
    def get_tool_definitions(self) -> List[Dict]:
        """返回所有工具的定义（OpenAI Function Calling 格式）"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_market_info",
                    "description": "获取 Polymarket 预测市场的详细信息，包括价格、交易量、流动性等",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_slug": {
                                "type": "string",
                                "description": "市场的 slug 标识符，例如 'will-trump-win-2024'"
                            }
                        },
                        "required": ["market_slug"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_markets",
                    "description": "搜索 Polymarket 上的预测市场",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索关键词，例如 'Trump', 'Bitcoin', 'Fed rate'"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量限制",
                                "default": 10
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "analyze_trader",
                    "description": "分析交易者地址的行为模式，生成交易者画像和标签",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "string",
                                "description": "以太坊/Polygon 钱包地址"
                            }
                        },
                        "required": ["address"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_trading_advice",
                    "description": "获取特定市场的交易建议，包括套利机会和关联市场分析",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_slug": {
                                "type": "string",
                                "description": "市场的 slug 标识符"
                            },
                            "user_intent": {
                                "type": "string",
                                "description": "用户的交易意图，例如 '我看好 Trump 获胜'"
                            }
                        },
                        "required": ["market_slug"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_arbitrage",
                    "description": "扫描 Polymarket 上的套利机会",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "扫描市场数量",
                                "default": 20
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_smart_money_activity",
                    "description": "获取聪明钱（高胜率交易者）的最近活动",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_slug": {
                                "type": "string",
                                "description": "可选：限定特定市场"
                            },
                            "min_win_rate": {
                                "type": "number",
                                "description": "最低胜率阈值",
                                "default": 60
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_hot_markets",
                    "description": "获取当前热门/高交易量的市场",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "返回数量",
                                "default": 10
                            },
                            "sort_by": {
                                "type": "string",
                                "description": "排序方式：volume（交易量）、liquidity（流动性）、recent（最新）",
                                "enum": ["volume", "liquidity", "recent"],
                                "default": "volume"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_market_relationship",
                    "description": "分析两个市场之间的逻辑关系（包含、互斥、相关），检测价格滞后和套利机会",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "market_a": {
                                "type": "string",
                                "description": "第一个市场的 slug"
                            },
                            "market_b": {
                                "type": "string",
                                "description": "第二个市场的 slug"
                            }
                        },
                        "required": ["market_a", "market_b"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_smart_alerts",
                    "description": "为关注的市场生成智能提醒，自动检测关联市场价格滞后和套利机会",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "watched_market": {
                                "type": "string",
                                "description": "用户关注的市场 slug"
                            }
                        },
                        "required": ["watched_market"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_trader_timing",
                    "description": "分析交易者的时序模式，检测是否存在新闻敏感型交易行为",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "string",
                                "description": "交易者地址"
                            }
                        },
                        "required": ["address"]
                    }
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """执行工具调用"""
        try:
            if tool_name == "get_market_info":
                return self._get_market_info(arguments.get("market_slug"))
            
            elif tool_name == "search_markets":
                return self._search_markets(
                    arguments.get("query"),
                    arguments.get("limit", 10)
                )
            
            elif tool_name == "analyze_trader":
                return self._analyze_trader(arguments.get("address"))
            
            elif tool_name == "get_trading_advice":
                return self.advisor.get_trading_advice(
                    arguments.get("market_slug"),
                    arguments.get("user_intent")
                )
            
            elif tool_name == "find_arbitrage":
                opportunities = self.advisor.scan_all_arbitrage(arguments.get("limit", 20))
                return {
                    "opportunities": [asdict(o) for o in opportunities],
                    "count": len(opportunities),
                    "timestamp": datetime.now().isoformat()
                }
            
            elif tool_name == "get_smart_money_activity":
                return self._get_smart_money_activity(
                    arguments.get("market_slug"),
                    arguments.get("min_win_rate", 60)
                )
            
            elif tool_name == "get_hot_markets":
                return self._get_hot_markets(
                    arguments.get("limit", 10),
                    arguments.get("sort_by", "volume")
                )
            
            elif tool_name == "analyze_market_relationship":
                return self._analyze_market_relationship(
                    arguments.get("market_a"),
                    arguments.get("market_b")
                )
            
            elif tool_name == "get_smart_alerts":
                alerts = self.advisor.generate_smart_alert(
                    arguments.get("watched_market")
                )
                return {
                    "alerts": alerts,
                    "count": len(alerts),
                    "watched_market": arguments.get("watched_market"),
                    "timestamp": datetime.now().isoformat()
                }
            
            elif tool_name == "analyze_trader_timing":
                return self._analyze_trader_timing(arguments.get("address"))
            
            else:
                return {"error": f"未知工具: {tool_name}"}
                
        except Exception as e:
            logger.error(f"工具执行失败: {tool_name}, 错误: {e}")
            return {"error": str(e)}
    
    def _get_market_info(self, market_slug: str) -> Dict:
        """获取市场信息"""
        try:
            response = requests.get(
                f"{self.gamma_base_url}/markets",
                params={"slug": market_slug},
                timeout=10
            )
            
            if response.status_code == 200:
                markets = response.json()
                if markets:
                    market = markets[0]
                    # 提取关键信息
                    tokens = market.get("tokens", [])
                    yes_price = no_price = 0.5
                    for token in tokens:
                        if token.get("outcome") == "Yes":
                            yes_price = float(token.get("price", 0.5))
                        elif token.get("outcome") == "No":
                            no_price = float(token.get("price", 0.5))
                    
                    return {
                        "slug": market_slug,
                        "title": market.get("question", market_slug),
                        "description": market.get("description", ""),
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "volume": market.get("volume", 0),
                        "liquidity": market.get("liquidity", 0),
                        "end_date": market.get("endDate"),
                        "status": "active" if market.get("active") else "closed",
                        "condition_id": market.get("conditionId"),
                        "event_slug": market.get("eventSlug"),
                        "timestamp": datetime.now().isoformat()
                    }
                return {"error": "市场未找到"}
            return {"error": f"API 错误: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _search_markets(self, query: str, limit: int = 10) -> Dict:
        """搜索市场"""
        try:
            # Gamma API 搜索
            response = requests.get(
                f"{self.gamma_base_url}/markets",
                params={"_limit": limit * 3},  # 获取更多用于过滤
                timeout=10
            )
            
            if response.status_code == 200:
                all_markets = response.json()
                
                # 关键词过滤
                query_lower = query.lower()
                matched = []
                
                for market in all_markets:
                    title = market.get("question", "").lower()
                    slug = market.get("slug", "").lower()
                    
                    if query_lower in title or query_lower in slug:
                        tokens = market.get("tokens", [])
                        yes_price = 0.5
                        for token in tokens:
                            if token.get("outcome") == "Yes":
                                yes_price = float(token.get("price", 0.5))
                        
                        matched.append({
                            "slug": market.get("slug"),
                            "title": market.get("question"),
                            "yes_price": yes_price,
                            "volume": market.get("volume", 0),
                            "active": market.get("active", True)
                        })
                        
                        if len(matched) >= limit:
                            break
                
                return {
                    "query": query,
                    "results": matched,
                    "count": len(matched),
                    "timestamp": datetime.now().isoformat()
                }
            
            return {"error": f"API 错误: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_trader(self, address: str) -> Dict:
        """分析交易者"""
        trades = self._fetch_trades_by_address(address, limit=200)
        profile = self.profiler.analyze_address(address, trades)
        return self.profiler.to_dict(profile)
    
    def _get_smart_money_activity(
        self, 
        market_slug: Optional[str],
        min_win_rate: float
    ) -> Dict:
        """获取聪明钱活动 - 从数据库统计高胜率地址"""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            # 统计每个地址的交易胜率
            # 简化版：统计每个地址的交易次数和平均盈利
            query = """
                SELECT 
                    maker as address,
                    COUNT(*) as trade_count,
                    AVG(price) as avg_price,
                    SUM(size) as total_size,
                    MAX(timestamp) as last_trade
                FROM trades
                GROUP BY maker
                HAVING COUNT(*) >= 5
                ORDER BY total_size DESC
                LIMIT 20
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # 如果指定了市场，筛选该市场的活跃地址
            if market_slug:
                cursor.execute("""
                    SELECT DISTINCT t.maker, t.side, t.outcome, t.price, t.size, t.timestamp
                    FROM trades t
                    JOIN markets m ON t.market_id = m.id
                    WHERE m.slug = ?
                    ORDER BY t.timestamp DESC
                    LIMIT 50
                """, (market_slug,))
                market_trades = cursor.fetchall()
            else:
                market_trades = []
            
            conn.close()
            
            # 构建聪明钱列表
            smart_money = []
            buy_count = 0
            sell_count = 0
            
            for row in rows:
                address = row[0]
                trade_count = row[1]
                avg_price = float(row[2]) if row[2] else 0.5
                total_size = float(row[3]) if row[3] else 0
                last_trade = row[4]
                
                # 估算胜率（简化：基于平均价格）
                estimated_win_rate = min(95, max(30, 50 + (0.5 - avg_price) * 100))
                
                if estimated_win_rate >= min_win_rate:
                    # 获取最近操作
                    recent = self._fetch_trades_by_address(address, limit=1)
                    recent_action = "N/A"
                    if recent:
                        recent_action = f"{recent[0].get('side', '?')} {recent[0].get('outcome', '?')}"
                        if recent[0].get('side') == 'BUY':
                            buy_count += 1
                        else:
                            sell_count += 1
                    
                    smart_money.append({
                        "address": f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address,
                        "full_address": address,
                        "trade_count": trade_count,
                        "win_rate": round(estimated_win_rate, 1),
                        "total_volume": round(total_size, 2),
                        "recent_action": recent_action,
                        "last_active": last_trade
                    })
            
            # 生成摘要
            if buy_count > sell_count:
                summary = f"聪明钱整体偏向买入 ({buy_count}买/{sell_count}卖)"
            elif sell_count > buy_count:
                summary = f"聪明钱整体偏向卖出 ({buy_count}买/{sell_count}卖)"
            else:
                summary = "聪明钱买卖均衡"
            
            return {
                "market_slug": market_slug,
                "min_win_rate": min_win_rate,
                "smart_money_addresses": smart_money[:10],
                "total_found": len(smart_money),
                "summary": summary,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取聪明钱活动失败: {e}")
            return {
                "market_slug": market_slug,
                "min_win_rate": min_win_rate,
                "smart_money_addresses": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _get_hot_markets(self, limit: int, sort_by: str) -> Dict:
        """获取热门市场"""
        try:
            response = requests.get(
                f"{self.gamma_base_url}/markets",
                params={"_limit": limit, "active": True},
                timeout=10
            )
            
            if response.status_code == 200:
                markets = response.json()
                
                # 排序
                if sort_by == "volume":
                    markets.sort(key=lambda x: float(x.get("volume", 0)), reverse=True)
                elif sort_by == "liquidity":
                    markets.sort(key=lambda x: float(x.get("liquidity", 0)), reverse=True)
                
                results = []
                for market in markets[:limit]:
                    tokens = market.get("tokens", [])
                    yes_price = 0.5
                    for token in tokens:
                        if token.get("outcome") == "Yes":
                            yes_price = float(token.get("price", 0.5))
                    
                    results.append({
                        "slug": market.get("slug"),
                        "title": market.get("question"),
                        "yes_price": yes_price,
                        "volume": market.get("volume", 0),
                        "liquidity": market.get("liquidity", 0)
                    })
                
                return {
                    "markets": results,
                    "sort_by": sort_by,
                    "count": len(results),
                    "timestamp": datetime.now().isoformat()
                }
            
            return {"error": f"API 错误: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def _fetch_trades_by_address(self, address: str, limit: int = 200) -> List[Dict]:
        """从数据库获取地址的交易记录"""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT t.tx_hash, t.log_index, t.maker, t.taker, t.side, t.outcome,
                       t.price, t.size, t.timestamp, m.slug
                FROM trades t
                LEFT JOIN markets m ON t.market_id = m.id
                WHERE t.maker = ? OR t.taker = ?
                ORDER BY t.timestamp DESC
                LIMIT ?
                """,
                (address, address, limit)
            )

            rows = cursor.fetchall()
            conn.close()

            trades = []
            for row in rows:
                trades.append({
                    "tx_hash": row[0],
                    "log_index": row[1],
                    "maker": row[2],
                    "taker": row[3],
                    "side": row[4],
                    "outcome": row[5],
                    "price": float(row[6]) if row[6] is not None else 0.0,
                    "size": float(row[7]) if row[7] is not None else 0.0,
                    "timestamp": row[8],
                    "market_slug": row[9] or "unknown"
                })

            return trades
        except Exception as e:
            logger.error(f"获取交易记录失败: {e}")
            return []


    def _analyze_market_relationship(self, market_a: str, market_b: str) -> Dict:
        """分析两个市场之间的关系"""
        # 获取市场信息
        info_a = self._get_market_info(market_a)
        info_b = self._get_market_info(market_b)
        
        if "error" in info_a or "error" in info_b:
            return {
                "error": "无法获取市场信息",
                "market_a": info_a,
                "market_b": info_b
            }
        
        # 检测跨市场套利
        cross_arb = self.advisor.detect_cross_market_opportunity(market_a, market_b)
        
        # 尝试推断关系类型
        relationships = self.advisor._infer_relationships(
            info_a, 
            [{"slug": market_b, "title": info_b.get("title", "")}]
        )
        
        inferred = relationships[0] if relationships else {"inferred_relationship": "未知"}
        
        # 检测价格滞后
        lag_result = self.advisor.detect_price_lag(
            market_a, 
            market_b, 
            inferred.get("inferred_relationship", "相关")
        )
        
        return {
            "market_a": info_a,
            "market_b": info_b,
            "inferred_relationship": inferred.get("inferred_relationship", "未知"),
            "cross_arbitrage": asdict(cross_arb) if cross_arb else None,
            "price_lag": lag_result,
            "timestamp": datetime.now().isoformat()
        }
    
    def _analyze_trader_timing(self, address: str) -> Dict:
        """分析交易者的时序模式"""
        # 获取交易者的交易历史
        trader_info = self._analyze_trader(address)
        
        if "error" in trader_info:
            return trader_info
        
        # 获取原始交易数据进行时序分析
        trades = self._fetch_trades_by_address(address, limit=300)
        timing_analysis = self.profiler.analyze_timing_patterns(trades)
        
        return {
            "address": address,
            "trader_profile": trader_info,
            "timing_analysis": timing_analysis,
            "is_news_sensitive": timing_analysis.get("is_news_sensitive", False),
            "patterns_detected": len(timing_analysis.get("patterns", [])),
            "timestamp": datetime.now().isoformat()
        }


# 包装函数供外部调用
def get_market_info(market_slug: str) -> Dict:
    """获取市场信息的便捷函数"""
    tools = PolymarketTools()
    return tools.execute_tool("get_market_info", {"market_slug": market_slug})

def search_markets(query: str, limit: int = 10) -> Dict:
    """搜索市场的便捷函数"""
    tools = PolymarketTools()
    return tools.execute_tool("search_markets", {"query": query, "limit": limit})

def analyze_trader(address: str) -> Dict:
    """分析交易者的便捷函数"""
    tools = PolymarketTools()
    return tools.execute_tool("analyze_trader", {"address": address})

def get_trading_advice(market_slug: str, user_intent: str = None) -> Dict:
    """获取交易建议的便捷函数"""
    tools = PolymarketTools()
    return tools.execute_tool("get_trading_advice", {"market_slug": market_slug, "user_intent": user_intent})

def find_arbitrage(limit: int = 20) -> Dict:
    """发现套利机会的便捷函数"""
    tools = PolymarketTools()
    return tools.execute_tool("find_arbitrage", {"limit": limit})


# 测试
if __name__ == "__main__":
    tools = PolymarketTools()
    
    print("=" * 60)
    print("MCP 工具测试")
    print("=" * 60)
    
    # 测试工具定义
    print("\n可用工具:")
    for tool in tools.get_tool_definitions():
        print(f"  - {tool['function']['name']}: {tool['function']['description'][:50]}...")
    
    # 测试搜索
    print("\n测试搜索 'trump':")
    result = tools.execute_tool("search_markets", {"query": "trump", "limit": 3})
    print(json.dumps(result, indent=2, ensure_ascii=False))
