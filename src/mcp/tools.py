"""
MCP 工具定义
"""
import os
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import requests

from .profiler import TraderProfiler
from .advisor import TradeAdvisor
from src.db.schema import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_trade_amount(maker_amount, taker_amount=0):
    maker_amt = safe_float(maker_amount)
    taker_amt = safe_float(taker_amount)
    
    if maker_amt < 1e6 and taker_amt > 1e6:
        return maker_amt
    elif taker_amt < 1e6 and maker_amt > 1e6:
        return taker_amt
    else:
        smaller = min(maker_amt, taker_amt)
        if smaller > 1e6:
            return smaller / 1e6
        return smaller


def calculate_price(maker_amount, taker_amount, stored_price=None):
    stored = safe_float(stored_price)
    if stored > 0.001 and stored < 1.0:
        return stored
    
    maker_amt = safe_float(maker_amount)
    taker_amt = safe_float(taker_amount)
    
    if maker_amt > 0 and taker_amt > 0:
        if maker_amt < taker_amt:
            price = maker_amt / taker_amt
        else:
            price = taker_amt / maker_amt
        if 0.001 < price < 1.0:
            return price
    
    return 0.5


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict


class PolymarketTools:
    def __init__(self):
        self.profiler = TraderProfiler()
        self.advisor = TradeAdvisor()
        self.gamma_base_url = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
        self.db_path = os.getenv("DB_PATH", "data/polymarket.db")
    
    def get_tool_definitions(self) -> List[Dict]:
        return [
            {"type": "function", "function": {"name": "get_market_info", "description": "获取市场详情", "parameters": {"type": "object", "properties": {"market_slug": {"type": "string"}}, "required": ["market_slug"]}}},
            {"type": "function", "function": {"name": "search_markets", "description": "搜索市场", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "analyze_trader", "description": "分析交易者", "parameters": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"]}}},
            {"type": "function", "function": {"name": "get_trading_advice", "description": "获取交易建议", "parameters": {"type": "object", "properties": {"market_slug": {"type": "string"}, "user_intent": {"type": "string"}}, "required": ["market_slug"]}}},
            {"type": "function", "function": {"name": "find_arbitrage", "description": "扫描套利机会", "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}}}},
            {"type": "function", "function": {"name": "get_smart_money_activity", "description": "获取聪明钱活动", "parameters": {"type": "object", "properties": {"market_slug": {"type": "string"}, "min_win_rate": {"type": "number", "default": 60}}}}},
            {"type": "function", "function": {"name": "get_hot_markets", "description": "获取热门市场", "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}, "sort_by": {"type": "string", "default": "volume"}}}}},
            {"type": "function", "function": {"name": "analyze_market_relationship", "description": "分析市场关系", "parameters": {"type": "object", "properties": {"market_a": {"type": "string"}, "market_b": {"type": "string"}}, "required": ["market_a", "market_b"]}}},
            {"type": "function", "function": {"name": "get_smart_alerts", "description": "生成智能提醒", "parameters": {"type": "object", "properties": {"watched_market": {"type": "string"}}, "required": ["watched_market"]}}},
        ]
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> Dict:
        try:
            if tool_name == "get_market_info":
                return self._get_market_info(arguments.get("market_slug"))
            elif tool_name == "search_markets":
                return self._search_markets(arguments.get("query"), arguments.get("limit", 10))
            elif tool_name == "analyze_trader":
                return self._analyze_trader(arguments.get("address"))
            elif tool_name == "get_trading_advice":
                return self.advisor.get_trading_advice(arguments.get("market_slug"), arguments.get("user_intent"))
            elif tool_name == "find_arbitrage":
                opportunities = self.advisor.scan_all_arbitrage(arguments.get("limit", 20))
                return {"opportunities": [asdict(o) for o in opportunities], "count": len(opportunities), "timestamp": datetime.now().isoformat()}
            elif tool_name == "get_smart_money_activity":
                return self._get_smart_money_activity(arguments.get("market_slug"), arguments.get("min_win_rate", 60))
            elif tool_name == "get_hot_markets":
                return self._get_hot_markets(arguments.get("limit", 10), arguments.get("sort_by", "volume"))
            elif tool_name == "analyze_market_relationship":
                return self._analyze_market_relationship(arguments.get("market_a"), arguments.get("market_b"))
            elif tool_name == "get_smart_alerts":
                alerts = self.advisor.generate_smart_alert(arguments.get("watched_market"))
                return {"alerts": alerts, "count": len(alerts), "watched_market": arguments.get("watched_market"), "timestamp": datetime.now().isoformat()}
            else:
                return {"error": f"未知工具: {tool_name}"}
        except Exception as e:
            logger.error(f"工具执行失败: {tool_name}, 错误: {e}")
            return {"error": str(e)}
    
    def _get_market_info(self, market_slug: str) -> Dict:
        try:
            response = requests.get(f"{self.gamma_base_url}/markets", params={"slug": market_slug}, timeout=10)
            if response.status_code == 200:
                markets = response.json()
                if markets:
                    market = markets[0]
                    tokens = market.get("tokens", [])
                    yes_price = no_price = 0.5
                    for token in tokens:
                        if token.get("outcome") == "Yes":
                            yes_price = safe_float(token.get("price"), 0.5)
                        elif token.get("outcome") == "No":
                            no_price = safe_float(token.get("price"), 0.5)
                    
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
                        "timestamp": datetime.now().isoformat()
                    }
                return {"error": "市场未找到"}
            return {"error": f"API 错误: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _search_markets(self, query: str, limit: int = 10) -> Dict:
        try:
            response = requests.get(f"{self.gamma_base_url}/markets", params={"_limit": limit * 3}, timeout=10)
            if response.status_code == 200:
                all_markets = response.json()
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
                                yes_price = safe_float(token.get("price"), 0.5)
                        
                        matched.append({
                            "slug": market.get("slug"),
                            "title": market.get("question"),
                            "yes_price": yes_price,
                            "volume": market.get("volume", 0),
                            "active": market.get("active", True)
                        })
                        
                        if len(matched) >= limit:
                            break
                
                return {"query": query, "results": matched, "count": len(matched), "timestamp": datetime.now().isoformat()}
            return {"error": f"API 错误: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_trader(self, address: str) -> Dict:
        trades = self._fetch_trades_by_address(address, limit=200)
        profile = self.profiler.analyze_address(address, trades)
        return self.profiler.to_dict(profile)
    
    def _get_smart_money_activity(self, market_slug: Optional[str], min_win_rate: float) -> Dict:
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    maker as address,
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN side = 'BUY' THEN 1 ELSE 0 END) as buy_count,
                    SUM(
                        CASE 
                            WHEN CAST(maker_amount AS REAL) < CAST(taker_amount AS REAL) 
                            THEN CAST(maker_amount AS REAL)
                            ELSE CAST(taker_amount AS REAL)
                        END
                    ) as total_volume
                FROM trades
                GROUP BY maker
                HAVING COUNT(*) >= 5
                ORDER BY total_volume DESC
                LIMIT 30
            """)
            rows = cursor.fetchall()
            conn.close()
            
            smart_money = []
            
            for row in rows:
                address = row[0]
                trade_count = row[1]
                buy_count = row[2] or 0
                total_volume_raw = row[3] or 0
                
                total_volume = total_volume_raw / 1e6 if total_volume_raw > 1e6 else total_volume_raw
                buy_ratio = buy_count / trade_count if trade_count > 0 else 0.5
                estimated_win_rate = 40 + buy_ratio * 30
                
                if estimated_win_rate >= min_win_rate:
                    smart_money.append({
                        "address": f"{address[:6]}...{address[-4:]}" if len(str(address)) > 10 else address,
                        "full_address": address,
                        "trade_count": trade_count,
                        "win_rate": round(estimated_win_rate, 1),
                        "total_volume": round(total_volume, 2),
                        "buy_ratio": round(buy_ratio * 100, 1)
                    })
            
            return {
                "market_slug": market_slug,
                "min_win_rate": min_win_rate,
                "smart_money_addresses": smart_money[:10],
                "total_found": len(smart_money),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取聪明钱活动失败: {e}")
            return {"smart_money_addresses": [], "error": str(e)}
    
    def _get_hot_markets(self, limit: int, sort_by: str) -> Dict:
        try:
            response = requests.get(f"{self.gamma_base_url}/markets", params={"_limit": limit * 2, "active": True}, timeout=10)
            if response.status_code == 200:
                markets = response.json()
                
                if sort_by == "volume":
                    markets.sort(key=lambda x: safe_float(x.get("volume"), 0), reverse=True)
                elif sort_by == "liquidity":
                    markets.sort(key=lambda x: safe_float(x.get("liquidity"), 0), reverse=True)
                
                results = []
                for market in markets[:limit]:
                    tokens = market.get("tokens", [])
                    yes_price = 0.5
                    for token in tokens:
                        if token.get("outcome") == "Yes":
                            yes_price = safe_float(token.get("price"), 0.5)
                    
                    results.append({
                        "slug": market.get("slug"),
                        "title": market.get("question"),
                        "yes_price": yes_price,
                        "volume": market.get("volume", 0),
                        "liquidity": market.get("liquidity", 0)
                    })
                
                return {"markets": results, "sort_by": sort_by, "count": len(results), "timestamp": datetime.now().isoformat()}
            return {"error": f"API 错误: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def _fetch_trades_by_address(self, address: str, limit: int = 200) -> List[Dict]:
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    t.tx_hash, t.log_index, t.maker, t.taker,
                    t.side, t.outcome, t.price, 
                    t.maker_amount, t.taker_amount, 
                    t.timestamp, t.token_id
                FROM trades t
                WHERE t.maker = ? OR t.taker = ?
                ORDER BY t.id DESC
                LIMIT ?
            """, (address, address, limit))

            rows = cursor.fetchall()
            conn.close()

            trades = []
            for row in rows:
                size = parse_trade_amount(row[7], row[8])
                price = calculate_price(row[7], row[8], row[6])
                
                trades.append({
                    "tx_hash": row[0],
                    "log_index": row[1],
                    "maker": row[2],
                    "taker": row[3],
                    "side": row[4] or "BUY",
                    "outcome": row[5],
                    "price": price,
                    "size": size,
                    "timestamp": row[9] or "",
                    "market_slug": "unknown"
                })

            return trades
        except Exception as e:
            logger.error(f"获取交易记录失败: {e}")
            return []

    def _analyze_market_relationship(self, market_a: str, market_b: str) -> Dict:
        info_a = self._get_market_info(market_a)
        info_b = self._get_market_info(market_b)
        
        if "error" in info_a or "error" in info_b:
            return {"error": "无法获取市场信息", "market_a": info_a, "market_b": info_b}
        
        cross_arb = self.advisor.detect_cross_market_opportunity(market_a, market_b)
        
        return {
            "market_a": info_a,
            "market_b": info_b,
            "cross_arbitrage": asdict(cross_arb) if cross_arb else None,
            "timestamp": datetime.now().isoformat()
        }


def get_market_info(market_slug: str) -> Dict:
    return PolymarketTools().execute_tool("get_market_info", {"market_slug": market_slug})

def search_markets(query: str, limit: int = 10) -> Dict:
    return PolymarketTools().execute_tool("search_markets", {"query": query, "limit": limit})

def analyze_trader(address: str) -> Dict:
    return PolymarketTools().execute_tool("analyze_trader", {"address": address})

def get_trading_advice(market_slug: str, user_intent: str = None) -> Dict:
    return PolymarketTools().execute_tool("get_trading_advice", {"market_slug": market_slug, "user_intent": user_intent})

def find_arbitrage(limit: int = 20) -> Dict:
    return PolymarketTools().execute_tool("find_arbitrage", {"limit": limit})


if __name__ == "__main__":
    tools = PolymarketTools()
    print("MCP 工具测试")
    result = tools.execute_tool("search_markets", {"query": "trump", "limit": 3})
    print(json.dumps(result, indent=2, ensure_ascii=False))
