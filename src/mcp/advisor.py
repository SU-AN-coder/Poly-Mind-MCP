"""
意图交易建议 (Smart Assistant)
检测关联市场价格差异，推荐套利机会
"""
import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MarketOpportunity:
    """市场机会"""
    market_slug: str
    market_title: str
    current_price_yes: float
    current_price_no: float
    opportunity_type: str  # arbitrage, momentum, contrarian
    expected_return: float
    risk_level: str
    reasoning: str
    related_markets: List[str]
    timestamp: str


@dataclass
class ArbitrageOpportunity:
    """套利机会"""
    market_a_slug: str
    market_b_slug: str
    market_a_title: str
    market_b_title: str
    price_gap: float
    direction: str  # "A高估" or "B高估"
    potential_profit: float
    confidence: str
    reasoning: str
    timestamp: str


class TradeAdvisor:
    """交易建议引擎"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.gamma_base_url = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
    
    def get_market_price(self, market_slug: str) -> Optional[Dict]:
        """获取市场当前价格"""
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
                    # 从 tokens 获取价格
                    tokens = market.get("tokens", [])
                    yes_price = 0.5
                    no_price = 0.5
                    for token in tokens:
                        if token.get("outcome") == "Yes":
                            yes_price = float(token.get("price", 0.5))
                        elif token.get("outcome") == "No":
                            no_price = float(token.get("price", 0.5))
                    
                    return {
                        "slug": market_slug,
                        "title": market.get("question", market_slug),
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "volume": market.get("volume", 0),
                        "liquidity": market.get("liquidity", 0)
                    }
        except Exception as e:
            logger.error(f"获取市场价格失败: {e}")
        return None
    
    def detect_yes_no_arbitrage(self, market_slug: str) -> Optional[ArbitrageOpportunity]:
        """
        检测 YES + NO 价格套利机会
        如果 YES + NO < 1，存在套利空间
        """
        market = self.get_market_price(market_slug)
        if not market:
            return None
        
        total = market["yes_price"] + market["no_price"]
        
        if total < 0.98:  # 2% 以上的套利空间
            profit = (1 - total) * 100
            return ArbitrageOpportunity(
                market_a_slug=f"{market_slug}-yes",
                market_b_slug=f"{market_slug}-no",
                market_a_title=f"{market['title']} - YES",
                market_b_title=f"{market['title']} - NO",
                price_gap=round(1 - total, 4),
                direction="双向买入",
                potential_profit=round(profit, 2),
                confidence="高" if profit > 3 else "中",
                reasoning=f"YES({market['yes_price']:.2f}) + NO({market['no_price']:.2f}) = {total:.2f} < 1.00，买入两边可无风险获利{profit:.2f}%",
                timestamp=datetime.now().isoformat()
            )
        elif total > 1.02:  # 价格偏高
            return ArbitrageOpportunity(
                market_a_slug=f"{market_slug}-yes",
                market_b_slug=f"{market_slug}-no",
                market_a_title=f"{market['title']} - YES",
                market_b_title=f"{market['title']} - NO",
                price_gap=round(total - 1, 4),
                direction="价格偏高",
                potential_profit=0,
                confidence="低",
                reasoning=f"YES({market['yes_price']:.2f}) + NO({market['no_price']:.2f}) = {total:.2f} > 1.00，不建议买入",
                timestamp=datetime.now().isoformat()
            )
        
        return None
    
    def find_related_markets(self, market_slug: str, limit: int = 5) -> List[Dict]:
        """查找关联市场"""
        try:
            # 获取当前市场信息
            response = requests.get(
                f"{self.gamma_base_url}/markets",
                params={"slug": market_slug},
                timeout=10
            )
            
            if response.status_code != 200:
                return []
            
            markets = response.json()
            if not markets:
                return []
            
            current_market = markets[0]
            event_slug = current_market.get("eventSlug", "")
            
            # 查找同事件的其他市场
            if event_slug:
                response = requests.get(
                    f"{self.gamma_base_url}/events/{event_slug}",
                    timeout=10
                )
                if response.status_code == 200:
                    event = response.json()
                    related = []
                    for m in event.get("markets", [])[:limit]:
                        if m.get("slug") != market_slug:
                            related.append({
                                "slug": m.get("slug"),
                                "title": m.get("question", m.get("slug")),
                                "relationship": "同事件市场"
                            })
                    return related
            
            # 如果没有事件关联，搜索相似关键词
            keywords = market_slug.split("-")[:3]
            search_term = " ".join(keywords)
            
            response = requests.get(
                f"{self.gamma_base_url}/markets",
                params={"_limit": limit * 2},
                timeout=10
            )
            
            if response.status_code == 200:
                all_markets = response.json()
                related = []
                for m in all_markets:
                    if m.get("slug") != market_slug:
                        # 简单关键词匹配
                        title = m.get("question", "").lower()
                        if any(kw.lower() in title for kw in keywords):
                            related.append({
                                "slug": m.get("slug"),
                                "title": m.get("question", m.get("slug")),
                                "relationship": "关键词相关"
                            })
                            if len(related) >= limit:
                                break
                return related
                
        except Exception as e:
            logger.error(f"查找关联市场失败: {e}")
        
        return []
    
    def detect_cross_market_opportunity(
        self, 
        market_a_slug: str, 
        market_b_slug: str
    ) -> Optional[ArbitrageOpportunity]:
        """
        检测跨市场套利机会
        例如：如果 "Trump 当选" 为 YES，则 "共和党执政" 也应该高
        """
        market_a = self.get_market_price(market_a_slug)
        market_b = self.get_market_price(market_b_slug)
        
        if not market_a or not market_b:
            return None
        
        # 简单相关性检测（实际应用中需要更复杂的逻辑）
        price_diff = abs(market_a["yes_price"] - market_b["yes_price"])
        
        if price_diff > 0.05:  # 5% 以上价差
            higher = market_a if market_a["yes_price"] > market_b["yes_price"] else market_b
            lower = market_b if market_a["yes_price"] > market_b["yes_price"] else market_a
            
            return ArbitrageOpportunity(
                market_a_slug=higher["slug"],
                market_b_slug=lower["slug"],
                market_a_title=higher["title"],
                market_b_title=lower["title"],
                price_gap=round(price_diff, 4),
                direction=f"{higher['slug']} 可能高估",
                potential_profit=round(price_diff * 50, 2),  # 估算
                confidence="中",
                reasoning=f"关联市场存在 {price_diff*100:.1f}% 价差，{lower['title']} 可能存在价格滞后",
                timestamp=datetime.now().isoformat()
            )
        
        return None
    
    def get_trading_advice(
        self, 
        market_slug: str,
        user_context: Optional[str] = None
    ) -> Dict:
        """
        获取交易建议
        
        Args:
            market_slug: 市场 slug
            user_context: 用户额外上下文（如"我看好 Trump"）
        
        Returns:
            交易建议
        """
        result = {
            "market": None,
            "arbitrage": None,
            "related_markets": [],
            "advice": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # 获取市场信息
        market = self.get_market_price(market_slug)
        if market:
            result["market"] = market
        else:
            result["advice"].append({
                "type": "error",
                "message": f"未找到市场: {market_slug}"
            })
            return result
        
        # 检测 YES/NO 套利
        arb = self.detect_yes_no_arbitrage(market_slug)
        if arb:
            result["arbitrage"] = asdict(arb)
            if arb.potential_profit > 0:
                result["advice"].append({
                    "type": "arbitrage",
                    "priority": "高",
                    "message": arb.reasoning
                })
        
        # 查找关联市场
        related = self.find_related_markets(market_slug)
        result["related_markets"] = related
        
        # 检测关联市场价差
        for rel in related[:3]:
            cross_arb = self.detect_cross_market_opportunity(market_slug, rel["slug"])
            if cross_arb and cross_arb.price_gap > 0.03:
                result["advice"].append({
                    "type": "cross_market",
                    "priority": "中",
                    "message": cross_arb.reasoning,
                    "related_market": rel["slug"]
                })
        
        # 基于价格的简单建议
        if market["yes_price"] < 0.2:
            result["advice"].append({
                "type": "value",
                "priority": "低",
                "message": f"YES 价格较低 ({market['yes_price']:.2f})，如果有利好消息可能快速上涨"
            })
        elif market["yes_price"] > 0.8:
            result["advice"].append({
                "type": "caution",
                "priority": "中",
                "message": f"YES 价格较高 ({market['yes_price']:.2f})，上涨空间有限，注意风险"
            })
        
        # 如果有 LLM，使用 LLM 生成更智能的建议
        if self.openai_api_key and user_context:
            llm_advice = self._get_llm_advice(market, related, user_context)
            if llm_advice:
                result["advice"].append({
                    "type": "ai_analysis",
                    "priority": "高",
                    "message": llm_advice
                })
        
        return result
    
    def _get_llm_advice(
        self, 
        market: Dict, 
        related: List[Dict],
        user_context: str
    ) -> Optional[str]:
        """使用 LLM 生成交易建议"""
        prompt = f"""作为 Polymarket 预测市场分析师，根据以下信息提供简洁的交易建议。

## 目标市场
- 标题: {market['title']}
- YES 价格: ${market['yes_price']:.2f}
- NO 价格: ${market['no_price']:.2f}
- 交易量: ${market.get('volume', 0):,.0f}

## 关联市场
{json.dumps(related[:3], indent=2, ensure_ascii=False) if related else "无"}

## 用户意图
{user_context}

请用2-3句话给出具体、可操作的交易建议。考虑：
1. 当前价格是否合理
2. 关联市场是否有套利机会
3. 用户意图与市场走势是否匹配
"""
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "你是专业的预测市场分析师，提供简洁、实用的交易建议。用中文回复。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 200
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM 建议生成失败: {e}")
        
        return None
    
    def scan_all_arbitrage(self, limit: int = 20) -> List[ArbitrageOpportunity]:
        """扫描所有市场的套利机会"""
        opportunities = []
        
        try:
            response = requests.get(
                f"{self.gamma_base_url}/markets",
                params={"_limit": limit, "active": True},
                timeout=15
            )
            
            if response.status_code == 200:
                markets = response.json()
                for market in markets:
                    slug = market.get("slug")
                    if slug:
                        arb = self.detect_yes_no_arbitrage(slug)
                        if arb and arb.potential_profit > 0:
                            opportunities.append(arb)
        except Exception as e:
            logger.error(f"扫描套利机会失败: {e}")
        
        # 按收益排序
        opportunities.sort(key=lambda x: x.potential_profit, reverse=True)
        return opportunities
    
    def detect_price_lag(
        self, 
        primary_market: str, 
        dependent_market: str,
        relationship: str = "包含"
    ) -> Optional[Dict]:
        """
        检测价格滞后
        当主市场价格变化时，检测从属市场是否存在滞后
        
        Args:
            primary_market: 主市场 slug (如 "trump-wins")
            dependent_market: 从属市场 slug (如 "republican-controls-white-house")
            relationship: 关系类型 ("包含", "互斥", "正相关", "负相关")
        
        Returns:
            价格滞后分析结果
        """
        primary = self.get_market_price(primary_market)
        dependent = self.get_market_price(dependent_market)
        
        if not primary or not dependent:
            return None
        
        result = {
            "primary_market": primary,
            "dependent_market": dependent,
            "relationship": relationship,
            "lag_detected": False,
            "opportunity": None,
            "reasoning": ""
        }
        
        # 根据关系类型计算预期价格
        if relationship == "包含":
            # A 发生 → B 必发生，所以 P(B) >= P(A)
            expected_min = primary["yes_price"]
            actual = dependent["yes_price"]
            
            if actual < expected_min - 0.03:  # 3% 阈值
                lag = expected_min - actual
                result["lag_detected"] = True
                result["opportunity"] = {
                    "action": f"买入 {dependent_market} YES",
                    "expected_profit": f"{lag * 100:.1f}%",
                    "confidence": "高" if lag > 0.05 else "中"
                }
                result["reasoning"] = (
                    f"逻辑蕴含关系：如果 '{primary['title']}' 发生 (当前 {primary['yes_price']:.0%})，"
                    f"则 '{dependent['title']}' 必然发生。但后者仅 {actual:.0%}，存在 {lag*100:.1f}% 价格滞后。"
                )
        
        elif relationship == "互斥":
            # A 和 B 不能同时发生，P(A) + P(B) <= 1
            total = primary["yes_price"] + dependent["yes_price"]
            if total > 1.05:  # 5% 超额
                result["lag_detected"] = True
                result["opportunity"] = {
                    "action": f"做空高估的一方",
                    "expected_profit": f"{(total - 1) * 100:.1f}%",
                    "confidence": "中"
                }
                result["reasoning"] = (
                    f"互斥关系：'{primary['title']}' 和 '{dependent['title']}' 不能同时发生，"
                    f"但两者 YES 价格之和为 {total:.0%}，超过 100%，存在套利空间。"
                )
        
        elif relationship == "正相关":
            # 正相关市场应该价格接近
            diff = abs(primary["yes_price"] - dependent["yes_price"])
            if diff > 0.1:  # 10% 差异
                lower = primary if primary["yes_price"] < dependent["yes_price"] else dependent
                result["lag_detected"] = True
                result["opportunity"] = {
                    "action": f"买入 {lower['slug']} YES",
                    "expected_profit": f"{diff * 100:.1f}%",
                    "confidence": "中"
                }
                result["reasoning"] = (
                    f"正相关市场存在 {diff*100:.1f}% 价差，'{lower['title']}' 可能被低估。"
                )
        
        return result
    
    def generate_smart_alert(
        self, 
        watched_market: str
    ) -> List[Dict]:
        """
        为关注的市场生成智能提醒
        检测关联市场的价格滞后，自动推送机会
        
        Args:
            watched_market: 用户关注的市场 slug
        
        Returns:
            提醒列表
        """
        alerts = []
        
        # 获取关注市场信息
        market = self.get_market_price(watched_market)
        if not market:
            return alerts
        
        # 查找关联市场
        related = self.find_related_markets(watched_market, limit=10)
        
        # 使用 LLM 推断关系类型（如果可用）
        relationships = self._infer_relationships(market, related)
        
        for rel in relationships:
            lag_result = self.detect_price_lag(
                watched_market, 
                rel["slug"], 
                rel.get("inferred_relationship", "相关")
            )
            
            if lag_result and lag_result.get("lag_detected"):
                alerts.append({
                    "type": "price_lag",
                    "priority": "高" if lag_result["opportunity"]["confidence"] == "高" else "中",
                    "watched_market": market["title"],
                    "related_market": rel.get("title", rel["slug"]),
                    "opportunity": lag_result["opportunity"],
                    "reasoning": lag_result["reasoning"],
                    "timestamp": datetime.now().isoformat()
                })
        
        # 检查 YES/NO 套利
        arb = self.detect_yes_no_arbitrage(watched_market)
        if arb and arb.potential_profit > 1:
            alerts.append({
                "type": "yes_no_arbitrage",
                "priority": "高",
                "watched_market": market["title"],
                "opportunity": {
                    "action": "买入 YES + NO",
                    "expected_profit": f"{arb.potential_profit:.1f}%"
                },
                "reasoning": arb.reasoning,
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts
    
    def _infer_relationships(
        self, 
        primary_market: Dict, 
        related_markets: List[Dict]
    ) -> List[Dict]:
        """使用 LLM 推断市场之间的逻辑关系"""
        if not self.openai_api_key or not related_markets:
            # 没有 API Key，返回默认相关性
            return [{"slug": m["slug"], "title": m.get("title", ""), "inferred_relationship": "相关"} for m in related_markets]
        
        prompt = f"""分析以下预测市场之间的逻辑关系。

主市场: {primary_market['title']}

关联市场:
{json.dumps([{"slug": m["slug"], "title": m.get("title", "")} for m in related_markets], indent=2, ensure_ascii=False)}

对于每个关联市场，判断它与主市场的关系类型：
- "包含": 主市场发生 → 关联市场必发生
- "被包含": 关联市场发生 → 主市场必发生
- "互斥": 两者不能同时发生
- "正相关": 两者大概率同向变动
- "负相关": 两者大概率反向变动
- "独立": 无明显关系

用 JSON 数组回复：
[{{"slug": "...", "relationship": "包含/互斥/正相关/..."}}]
"""
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "你是逻辑分析专家，擅长分析事件之间的因果和逻辑关系。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                try:
                    start = content.find("[")
                    end = content.rfind("]") + 1
                    if start >= 0 and end > start:
                        relationships = json.loads(content[start:end])
                        # 合并结果
                        result = []
                        for m in related_markets:
                            rel = next((r for r in relationships if r["slug"] == m["slug"]), None)
                            result.append({
                                "slug": m["slug"],
                                "title": m.get("title", ""),
                                "inferred_relationship": rel.get("relationship", "相关") if rel else "相关"
                            })
                        return result
                except:
                    pass
        except Exception as e:
            logger.error(f"LLM 关系推断失败: {e}")
        
        return [{"slug": m["slug"], "title": m.get("title", ""), "inferred_relationship": "相关"} for m in related_markets]


# 测试代码
if __name__ == "__main__":
    advisor = TradeAdvisor()
    
    # 测试获取交易建议
    print("=" * 60)
    print("交易建议测试")
    print("=" * 60)
    
    result = advisor.get_trading_advice(
        "will-there-be-another-us-government-shutdown-by-january-31",
        user_context="我认为政府不会关门"
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))

