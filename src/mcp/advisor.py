"""
交易顾问模块
提供交易建议、套利扫描和市场关联分析
"""
import os
import logging
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    """套利机会"""
    type: str                    # 套利类型: yes_no_spread, cross_market
    market_slug: str
    market_title: str = ""
    yes_price: float = 0.5
    no_price: float = 0.5
    spread: float = 0.0
    potential_profit: float = 0.0
    confidence: str = "中"
    details: str = ""
    reasoning: str = ""
    timestamp: str = ""


@dataclass
class MarketRelationship:
    """市场关系"""
    market_a: str
    market_b: str
    relationship_type: str       # contains, excludes, correlated, independent
    confidence: float
    description: str
    arbitrage_opportunity: Optional[ArbitrageOpportunity] = None


@dataclass
class TradingAdvice:
    """交易建议"""
    market_slug: str
    market_title: str
    current_yes_price: float
    current_no_price: float
    recommendation: str          # BUY_YES, BUY_NO, HOLD, WAIT
    confidence: str              # 高, 中, 低
    reasoning: str
    related_markets: List[Dict]
    arbitrage_opportunities: List[ArbitrageOpportunity]
    smart_money_signal: str
    risk_warnings: List[str]


class TradeAdvisor:
    """交易顾问"""
    
    def __init__(self):
        self.gamma_base_url = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
        self.market_cache = {}
        self.cache_ttl = 300  # 5分钟缓存
    
    def get_trading_advice(self, market_slug: str, user_intent: Optional[str] = None) -> Dict:
        """获取交易建议"""
        try:
            # 获取市场信息
            market_info = self._fetch_market(market_slug)
            if not market_info:
                return {"error": f"市场 {market_slug} 未找到"}
            
            yes_price = market_info.get("yes_price", 0.5)
            no_price = market_info.get("no_price", 0.5)
            
            # 分析价格信号
            recommendation, reasoning = self._analyze_price_signal(yes_price, no_price, user_intent)
            
            # 查找关联市场
            related = self._find_related_markets(market_slug, market_info.get("title", ""))
            
            # 扫描套利机会
            arb_opportunities = self._scan_market_arbitrage(market_info)
            
            # 生成风险提示
            risk_warnings = self._generate_risk_warnings(market_info, yes_price)
            
            # 判断置信度
            confidence = self._calculate_confidence(market_info, related, arb_opportunities)
            
            advice = TradingAdvice(
                market_slug=market_slug,
                market_title=market_info.get("title", market_slug),
                current_yes_price=yes_price,
                current_no_price=no_price,
                recommendation=recommendation,
                confidence=confidence,
                reasoning=reasoning,
                related_markets=related[:5],
                arbitrage_opportunities=arb_opportunities,
                smart_money_signal="观望",
                risk_warnings=risk_warnings
            )
            
            return self._advice_to_dict(advice)
            
        except Exception as e:
            logger.error(f"获取交易建议失败: {e}")
            return {"error": str(e)}
    
    def _fetch_market(self, market_slug: str) -> Optional[Dict]:
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
                        "volume": float(market.get("volume", 0)),
                        "liquidity": float(market.get("liquidity", 0)),
                        "end_date": market.get("endDate"),
                        "active": market.get("active", True)
                    }
            return None
        except Exception as e:
            logger.error(f"获取市场失败: {e}")
            return None
    
    def _analyze_price_signal(self, yes_price: float, no_price: float, 
                             user_intent: Optional[str]) -> Tuple[str, str]:
        """分析价格信号"""
        spread = yes_price + no_price - 1.0
        
        # 基于用户意图
        if user_intent:
            intent_lower = user_intent.lower()
            if any(word in intent_lower for word in ["看好", "买入", "yes", "会发生", "支持"]):
                if yes_price < 0.4:
                    return "BUY_YES", f"您看好该事件，当前 YES 价格 ${yes_price:.2f} 处于低位，可考虑买入"
                elif yes_price > 0.7:
                    return "HOLD", f"您看好该事件，但 YES 价格已达 ${yes_price:.2f}，建议观望或等待回调"
                else:
                    return "BUY_YES", f"您看好该事件，当前 YES 价格 ${yes_price:.2f}，可适量买入"
            
            if any(word in intent_lower for word in ["看空", "卖出", "no", "不会", "反对"]):
                if no_price < 0.4:
                    return "BUY_NO", f"您看空该事件，当前 NO 价格 ${no_price:.2f} 处于低位，可考虑买入 NO"
                elif no_price > 0.7:
                    return "HOLD", f"您看空该事件，但 NO 价格已达 ${no_price:.2f}，建议观望"
                else:
                    return "BUY_NO", f"您看空该事件，当前 NO 价格 ${no_price:.2f}，可适量买入 NO"
        
        # 无明确意图时的分析
        if spread > 0.05:
            return "ARBITRAGE", f"YES+NO 价格之和为 ${yes_price + no_price:.2f}，存在 {spread*100:.1f}% 的套利空间"
        
        if yes_price < 0.2:
            return "SPECULATIVE_YES", f"YES 价格极低 (${yes_price:.2f})，高风险高回报机会"
        
        if no_price < 0.2:
            return "SPECULATIVE_NO", f"NO 价格极低 (${no_price:.2f})，高风险高回报机会"
        
        return "HOLD", f"价格处于中间区域 (YES=${yes_price:.2f}, NO=${no_price:.2f})，建议观望等待明确信号"
    
    def _find_related_markets(self, market_slug: str, title: str) -> List[Dict]:
        """查找关联市场"""
        try:
            # 提取关键词
            keywords = self._extract_keywords(title)
            if not keywords:
                return []
            
            response = requests.get(
                f"{self.gamma_base_url}/markets",
                params={"_limit": 50, "active": True},
                timeout=10
            )
            
            if response.status_code != 200:
                return []
            
            markets = response.json()
            related = []
            
            for market in markets:
                if market.get("slug") == market_slug:
                    continue
                
                market_title = market.get("question", "").lower()
                match_count = sum(1 for kw in keywords if kw in market_title)
                
                if match_count > 0:
                    tokens = market.get("tokens", [])
                    yes_price = 0.5
                    for token in tokens:
                        if token.get("outcome") == "Yes":
                            yes_price = float(token.get("price", 0.5))
                    
                    # 推断关系
                    relationship = self._infer_relationship(title.lower(), market_title)
                    
                    related.append({
                        "slug": market.get("slug"),
                        "title": market.get("question"),
                        "yes_price": yes_price,
                        "match_score": match_count,
                        "inferred_relationship": relationship,
                        "volume": market.get("volume", 0)
                    })
            
            # 按匹配度排序
            related.sort(key=lambda x: x["match_score"], reverse=True)
            return related[:10]
            
        except Exception as e:
            logger.error(f"查找关联市场失败: {e}")
            return []
    
    def _extract_keywords(self, title: str) -> List[str]:
        """提取关键词"""
        # 移除常见停用词
        stop_words = {"will", "the", "a", "an", "in", "on", "at", "to", "for", "of", "be", "is", "are", "was", "were"}
        
        # 简单分词
        words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
        keywords = [w for w in words if w not in stop_words]
        
        # 保留专有名词（首字母大写）
        proper_nouns = re.findall(r'\b[A-Z][a-zA-Z]+\b', title)
        keywords.extend([n.lower() for n in proper_nouns])
        
        return list(set(keywords))[:5]
    
    def _infer_relationship(self, title_a: str, title_b: str) -> str:
        """推断两个市场的关系"""
        # 包含关系关键词
        if "before" in title_b or "by" in title_b:
            return "包含"
        
        # 互斥关系
        if "or" in title_a and "or" in title_b:
            return "可能互斥"
        
        # 时间相关
        date_pattern = r'\b(202[4-9]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b'
        if re.search(date_pattern, title_a) and re.search(date_pattern, title_b):
            return "时间相关"
        
        return "可能相关"
    
    def _infer_relationships(self, market_info: Dict, related_markets: List[Dict]) -> List[Dict]:
        """推断多个市场的关系"""
        result = []
        title_a = market_info.get("title", "").lower()
        
        for market in related_markets:
            title_b = market.get("title", "").lower()
            relationship = self._infer_relationship(title_a, title_b)
            result.append({
                "slug": market.get("slug"),
                "title": market.get("title"),
                "inferred_relationship": relationship
            })
        
        return result
    
    def _scan_market_arbitrage(self, market_info: Dict) -> List[ArbitrageOpportunity]:
        """扫描市场套利机会"""
        opportunities = []
        
        yes_price = market_info.get("yes_price", 0.5)
        no_price = market_info.get("no_price", 0.5)
        spread = yes_price + no_price - 1.0
        
        # YES + NO 套利
        if spread > 0.02:
            opp = ArbitrageOpportunity(
                type="yes_no_spread",
                market_slug=market_info.get("slug", ""),
                market_title=market_info.get("title", ""),
                yes_price=yes_price,
                no_price=no_price,
                spread=round(spread * 100, 2),
                potential_profit=round(spread * 100, 2),
                confidence="高" if spread > 0.05 else "中",
                details=f"买入 YES (${yes_price:.2f}) + NO (${no_price:.2f}) 总成本 ${yes_price + no_price:.2f}，结算后必得 $1，套利 {spread*100:.1f}%",
                reasoning="YES+NO 价格之和超过1，存在无风险套利",
                timestamp=datetime.now().isoformat()
            )
            opportunities.append(opp)
        
        return opportunities
    
    def _generate_risk_warnings(self, market_info: Dict, yes_price: float) -> List[str]:
        """生成风险提示"""
        warnings = []
        
        # 低流动性警告
        liquidity = market_info.get("liquidity", 0)
        if liquidity < 1000:
            warnings.append("⚠️ 低流动性市场，大额交易可能造成滑点")
        
        # 极端价格警告
        if yes_price < 0.1 or yes_price > 0.9:
            warnings.append("⚠️ 价格处于极端区域，波动风险较大")
        
        # 临近结算警告
        end_date = market_info.get("end_date")
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                if (end - datetime.now(end.tzinfo)).days < 7:
                    warnings.append("⚠️ 市场临近结算，注意时间风险")
            except:
                pass
        
        # 低交易量警告
        volume = market_info.get("volume", 0)
        if volume < 10000:
            warnings.append("⚠️ 交易量较低，市场关注度有限")
        
        return warnings
    
    def _calculate_confidence(self, market_info: Dict, related: List[Dict], 
                             arb_opportunities: List[ArbitrageOpportunity]) -> str:
        """计算建议置信度"""
        score = 0
        
        # 高流动性加分
        if market_info.get("liquidity", 0) > 10000:
            score += 2
        elif market_info.get("liquidity", 0) > 1000:
            score += 1
        
        # 有关联市场加分
        if len(related) > 3:
            score += 1
        
        # 有套利机会加分
        if arb_opportunities:
            score += 2
        
        # 高交易量加分
        if market_info.get("volume", 0) > 100000:
            score += 1
        
        if score >= 4:
            return "高"
        elif score >= 2:
            return "中"
        else:
            return "低"
    
    def _advice_to_dict(self, advice: TradingAdvice) -> Dict:
        """将建议转换为字典"""
        return {
            "market_slug": advice.market_slug,
            "market_title": advice.market_title,
            "current_yes_price": advice.current_yes_price,
            "current_no_price": advice.current_no_price,
            "recommendation": advice.recommendation,
            "confidence": advice.confidence,
            "reasoning": advice.reasoning,
            "related_markets": advice.related_markets,
            "arbitrage_opportunities": [asdict(o) for o in advice.arbitrage_opportunities],
            "smart_money_signal": advice.smart_money_signal,
            "risk_warnings": advice.risk_warnings,
            "timestamp": datetime.now().isoformat()
        }
    
    def scan_all_arbitrage(self, limit: int = 20) -> List[ArbitrageOpportunity]:
        """扫描所有市场的套利机会"""
        opportunities = []
        
        try:
            response = requests.get(
                f"{self.gamma_base_url}/markets",
                params={"_limit": limit * 2, "active": True},
                timeout=15
            )
            
            if response.status_code != 200:
                return opportunities
            
            markets = response.json()
            
            for market in markets[:limit]:
                tokens = market.get("tokens", [])
                yes_price = no_price = 0.5
                
                for token in tokens:
                    if token.get("outcome") == "Yes":
                        yes_price = float(token.get("price", 0.5))
                    elif token.get("outcome") == "No":
                        no_price = float(token.get("price", 0.5))
                
                spread = yes_price + no_price - 1.0
                
                if spread > 0.02:
                    opp = ArbitrageOpportunity(
                        type="yes_no_spread",
                        market_slug=market.get("slug", ""),
                        market_title=market.get("question", ""),
                        yes_price=yes_price,
                        no_price=no_price,
                        spread=round(spread * 100, 2),
                        potential_profit=round(spread * 100, 2),
                        confidence="高" if spread > 0.05 else "中",
                        details=f"YES=${yes_price:.2f} + NO=${no_price:.2f} = ${yes_price+no_price:.2f}",
                        reasoning="价格之和超过1",
                        timestamp=datetime.now().isoformat()
                    )
                    opportunities.append(opp)
            
            # 按利润排序
            opportunities.sort(key=lambda x: x.potential_profit, reverse=True)
            
        except Exception as e:
            logger.error(f"扫描套利失败: {e}")
        
        return opportunities
    
    def detect_cross_market_opportunity(self, market_a: str, market_b: str) -> Optional[ArbitrageOpportunity]:
        """检测跨市场套利机会"""
        info_a = self._fetch_market(market_a)
        info_b = self._fetch_market(market_b)
        
        if not info_a or not info_b:
            return None
        
        # 分析价格关系
        yes_a = info_a.get("yes_price", 0.5)
        yes_b = info_b.get("yes_price", 0.5)
        
        # 如果 A 包含 B，则 P(A) <= P(B)
        # 如果价格异常，可能存在套利
        price_diff = abs(yes_a - yes_b)
        
        if price_diff > 0.1:
            return ArbitrageOpportunity(
                type="cross_market",
                market_slug=f"{market_a} vs {market_b}",
                market_title=f"{info_a.get('title', '')} vs {info_b.get('title', '')}",
                yes_price=yes_a,
                no_price=yes_b,
                spread=round(price_diff * 100, 2),
                potential_profit=round(price_diff * 50, 2),
                confidence="低",
                details=f"市场A YES=${yes_a:.2f}, 市场B YES=${yes_b:.2f}",
                reasoning="两个相关市场价格差异较大，可能存在套利机会，但需人工验证逻辑关系",
                timestamp=datetime.now().isoformat()
            )
        
        return None
    
    def detect_price_lag(self, market_a: str, market_b: str, relationship: str) -> Dict:
        """检测价格滞后"""
        info_a = self._fetch_market(market_a)
        info_b = self._fetch_market(market_b)
        
        if not info_a or not info_b:
            return {"detected": False, "reason": "无法获取市场信息"}
        
        yes_a = info_a.get("yes_price", 0.5)
        yes_b = info_b.get("yes_price", 0.5)
        
        # 基于关系类型判断价格合理性
        if relationship == "包含":
            # A 包含 B 意味着 P(A) <= P(B)
            if yes_a > yes_b + 0.05:
                return {
                    "detected": True,
                    "type": "包含关系价格异常",
                    "expected": f"P(A) <= P(B)",
                    "actual": f"P(A)={yes_a:.2f} > P(B)={yes_b:.2f}",
                    "opportunity": "买入 B 卖出 A"
                }
        
        elif relationship == "可能互斥":
            # 互斥意味着 P(A) + P(B) <= 1
            if yes_a + yes_b > 1.05:
                return {
                    "detected": True,
                    "type": "互斥关系价格异常",
                    "expected": f"P(A) + P(B) <= 1",
                    "actual": f"P(A)+P(B)={yes_a + yes_b:.2f}",
                    "opportunity": "同时买入两者的 NO"
                }
        
        return {"detected": False, "reason": "未检测到明显价格滞后"}
    
    def generate_smart_alert(self, watched_market: str) -> List[Dict]:
        """为关注的市场生成智能提醒"""
        alerts = []
        
        market_info = self._fetch_market(watched_market)
        if not market_info:
            return [{"type": "error", "message": f"无法获取市场 {watched_market}"}]
        
        # 检查 YES+NO 套利
        yes_price = market_info.get("yes_price", 0.5)
        no_price = market_info.get("no_price", 0.5)
        spread = yes_price + no_price - 1.0
        
        if spread > 0.02:
            alerts.append({
                "type": "arbitrage",
                "severity": "high" if spread > 0.05 else "medium",
                "title": "发现套利机会",
                "message": f"YES+NO 价差达到 {spread*100:.1f}%，可考虑套利",
                "action": f"同时买入 YES (${yes_price:.2f}) 和 NO (${no_price:.2f})"
            })
        
        # 查找关联市场
        related = self._find_related_markets(watched_market, market_info.get("title", ""))
        
        for rel in related[:3]:
            rel_info = self._fetch_market(rel["slug"])
            if rel_info:
                lag = self.detect_price_lag(watched_market, rel["slug"], rel.get("inferred_relationship", "相关"))
                if lag.get("detected"):
                    alerts.append({
                        "type": "price_lag",
                        "severity": "medium",
                        "title": f"与 {rel['slug']} 存在价格滞后",
                        "message": lag.get("actual", ""),
                        "action": lag.get("opportunity", "观察")
                    })
        
        # 极端价格提醒
        if yes_price < 0.1:
            alerts.append({
                "type": "extreme_price",
                "severity": "low",
                "title": "YES 价格极低",
                "message": f"当前 YES 价格仅 ${yes_price:.2f}，可能是投机机会",
                "action": "评估事件发生可能性"
            })
        elif yes_price > 0.9:
            alerts.append({
                "type": "extreme_price",
                "severity": "low",
                "title": "YES 价格极高",
                "message": f"当前 YES 价格达 ${yes_price:.2f}，市场高度确定",
                "action": "注意是否有意外风险"
            })
        
        return alerts


# 测试
if __name__ == "__main__":
    advisor = TradeAdvisor()
    
    print("=" * 60)
    print("扫描套利机会:")
    print("=" * 60)
    
    opportunities = advisor.scan_all_arbitrage(limit=10)
    for opp in opportunities[:5]:
        print(f"  {opp.market_slug}: {opp.potential_profit}% ({opp.details})")
    
    print("\n" + "=" * 60)
    print("测试交易建议:")
    print("=" * 60)
    
    import json
    advice = advisor.get_trading_advice("will-trump-win-2024", "我看好 Trump")
    print(json.dumps(advice, indent=2, ensure_ascii=False))

