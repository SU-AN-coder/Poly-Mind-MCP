"""
智能画像引擎 (The Profiler)
利用 LLM 对地址行为进行语义化贴标
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from decimal import Decimal
import requests

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TraderProfile:
    """交易者画像"""
    address: str
    total_trades: int
    total_volume_usd: float
    win_rate: float
    avg_position_size: float
    favorite_markets: List[str]
    trading_style: str  # 策略类型标签
    risk_level: str     # 风险偏好
    labels: List[str]   # 语义化标签
    analysis_summary: str  # LLM 生成的分析总结
    last_active: str
    created_at: str


@dataclass
class TradeRecord:
    """交易记录"""
    tx_hash: str
    timestamp: str
    market_slug: str
    side: str  # BUY/SELL
    outcome: str  # YES/NO
    price: float
    size: float
    pnl: Optional[float] = None


class TraderProfiler:
    """交易者画像分析器"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.gamma_base_url = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
        
        if not self.openai_api_key:
            logger.warning("未配置 OpenAI API Key，将使用规则引擎进行分析")
    
    def analyze_address(self, address: str, trades: List[Dict]) -> TraderProfile:
        """
        分析地址的交易行为，生成画像
        
        Args:
            address: 钱包地址
            trades: 该地址的交易列表
        
        Returns:
            TraderProfile: 交易者画像
        """
        if not trades:
            return self._empty_profile(address)
        
        # 基础统计
        stats = self._calculate_stats(trades)
        
        # 使用 LLM 生成语义标签
        if self.openai_api_key:
            labels, style, summary = self._llm_analyze(address, trades, stats)
        else:
            labels, style, summary = self._rule_based_analyze(trades, stats)
        
        return TraderProfile(
            address=address,
            total_trades=stats["total_trades"],
            total_volume_usd=stats["total_volume"],
            win_rate=stats["win_rate"],
            avg_position_size=stats["avg_size"],
            favorite_markets=stats["top_markets"],
            trading_style=style,
            risk_level=stats["risk_level"],
            labels=labels,
            analysis_summary=summary,
            last_active=stats["last_active"],
            created_at=datetime.now().isoformat()
        )
    
    def _calculate_stats(self, trades: List[Dict]) -> Dict:
        """计算基础统计数据"""
        total_volume = 0
        wins = 0
        sizes = []
        market_counts = {}
        timestamps = []
        
        for trade in trades:
            size = float(trade.get("size", 0))
            price = float(trade.get("price", 0))
            volume = size * price
            total_volume += volume
            sizes.append(size)
            
            # 统计市场
            market = trade.get("market_slug", "unknown")
            market_counts[market] = market_counts.get(market, 0) + 1
            
            # 时间戳
            if trade.get("timestamp"):
                timestamps.append(trade["timestamp"])
            
            # 简化胜率计算（实际需要结算数据）
            if trade.get("pnl", 0) > 0:
                wins += 1
        
        total_trades = len(trades)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        avg_size = sum(sizes) / len(sizes) if sizes else 0
        
        # 风险评估
        if avg_size > 1000:
            risk_level = "高风险巨鲸"
        elif avg_size > 100:
            risk_level = "中等风险"
        else:
            risk_level = "保守型"
        
        # 最常交易的市场
        top_markets = sorted(market_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_markets = [m[0] for m in top_markets]
        
        return {
            "total_trades": total_trades,
            "total_volume": round(total_volume, 2),
            "win_rate": round(win_rate, 2),
            "avg_size": round(avg_size, 2),
            "risk_level": risk_level,
            "top_markets": top_markets,
            "last_active": max(timestamps) if timestamps else "unknown"
        }
    
    def _llm_analyze(self, address: str, trades: List[Dict], stats: Dict) -> tuple:
        """使用 LLM 分析交易行为"""
        # 准备交易摘要
        trade_summary = self._prepare_trade_summary(trades[:50])  # 最多50条
        
        prompt = f"""分析以下 Polymarket 预测市场交易者的行为模式，生成交易者画像。

## 交易者地址
{address}

## 交易统计
- 总交易次数: {stats['total_trades']}
- 总交易量: ${stats['total_volume']:,.2f}
- 胜率: {stats['win_rate']}%
- 平均仓位: ${stats['avg_size']:,.2f}
- 最活跃市场: {', '.join(stats['top_markets'][:3])}

## 最近交易记录
{trade_summary}

## 请输出以下内容（JSON格式）：
1. labels: 2-4个语义化标签，例如：
   - "政策敏感型巨鲸" (总是在重大新闻前下单)
   - "稳健套利者" (专门吃 Yes+No 价差)
   - "情绪反向风向标" (经常逆势操作)
   - "高频交易者" (短时间大量交易)
   - "聪明钱" (胜率显著高于平均)
   
2. trading_style: 一句话总结交易风格

3. summary: 2-3句话的详细分析

请用JSON格式回复：
{{"labels": [...], "trading_style": "...", "summary": "..."}}
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
                        {"role": "system", "content": "你是一个专业的加密货币交易分析师，擅长分析预测市场交易者的行为模式。请用中文回复。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                # 解析 JSON
                try:
                    # 提取 JSON 部分
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        result = json.loads(content[start:end])
                        return (
                            result.get("labels", ["普通交易者"]),
                            result.get("trading_style", "未知风格"),
                            result.get("summary", "分析数据不足")
                        )
                except json.JSONDecodeError:
                    logger.warning("LLM 返回格式解析失败，使用规则引擎")
            else:
                logger.warning(f"OpenAI API 错误: {response.status_code}")
                
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
        
        # 降级到规则引擎
        return self._rule_based_analyze(trades, stats)
    
    def _rule_based_analyze(self, trades: List[Dict], stats: Dict) -> tuple:
        """基于规则的分析（LLM 不可用时的降级方案）"""
        labels = []
        
        # 根据统计数据生成标签
        if stats["total_volume"] > 100000:
            labels.append("巨鲸玩家")
        elif stats["total_volume"] > 10000:
            labels.append("大户")
        
        if stats["win_rate"] > 60:
            labels.append("聪明钱")
        elif stats["win_rate"] < 40:
            labels.append("情绪反向风向标")
        
        if stats["total_trades"] > 100:
            labels.append("高频交易者")
        elif stats["total_trades"] < 10:
            labels.append("低频观望者")
        
        if stats["avg_size"] > 1000:
            labels.append("大仓位玩家")
        
        if not labels:
            labels = ["普通交易者"]
        
        style = f"{stats['risk_level']}，偏好{stats['top_markets'][0] if stats['top_markets'] else '多元化'}市场"
        summary = f"该地址共进行{stats['total_trades']}笔交易，总交易量${stats['total_volume']:,.2f}，胜率{stats['win_rate']}%。"
        
        return labels, style, summary
    
    def _prepare_trade_summary(self, trades: List[Dict]) -> str:
        """准备交易摘要供 LLM 分析"""
        lines = []
        for t in trades[:20]:  # 最多20条
            line = f"- {t.get('timestamp', 'N/A')}: {t.get('side', '?')} {t.get('outcome', '?')} @ ${t.get('price', 0):.2f}, 数量: {t.get('size', 0):.2f}"
            if t.get('market_slug'):
                line += f" ({t['market_slug'][:30]})"
            lines.append(line)
        return "\n".join(lines) if lines else "无交易记录"
    
    def _empty_profile(self, address: str) -> TraderProfile:
        """返回空画像"""
        return TraderProfile(
            address=address,
            total_trades=0,
            total_volume_usd=0,
            win_rate=0,
            avg_position_size=0,
            favorite_markets=[],
            trading_style="无交易记录",
            risk_level="未知",
            labels=["新地址"],
            analysis_summary="该地址暂无交易记录",
            last_active="never",
            created_at=datetime.now().isoformat()
        )
    
    def analyze_timing_patterns(self, trades: List[Dict]) -> Dict:
        """
        分析交易时序模式
        检测是否在重大事件前后有异常交易行为
        
        Args:
            trades: 交易列表
        
        Returns:
            时序模式分析结果
        """
        if not trades:
            return {"patterns": [], "is_news_sensitive": False}
        
        patterns = []
        
        # 1. 分析交易时间分布
        hour_distribution = {}
        weekday_distribution = {}
        
        for trade in trades:
            try:
                ts = trade.get("timestamp", "")
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    dt = ts
                
                hour = dt.hour
                weekday = dt.weekday()
                
                hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
                weekday_distribution[weekday] = weekday_distribution.get(weekday, 0) + 1
            except:
                continue
        
        # 2. 检测集中交易时段
        if hour_distribution:
            peak_hour = max(hour_distribution, key=hour_distribution.get)
            peak_ratio = hour_distribution[peak_hour] / len(trades)
            
            if peak_ratio > 0.3:  # 30%以上交易集中在某小时
                if 9 <= peak_hour <= 17:
                    patterns.append({
                        "type": "trading_hours",
                        "description": f"主要在工作时间 ({peak_hour}:00) 交易",
                        "confidence": "高" if peak_ratio > 0.5 else "中"
                    })
                elif peak_hour < 6 or peak_hour > 22:
                    patterns.append({
                        "type": "off_hours",
                        "description": f"偏好非工作时间 ({peak_hour}:00) 交易，可能关注其他时区事件",
                        "confidence": "高" if peak_ratio > 0.5 else "中"
                    })
        
        # 3. 分析交易间隔（检测快速反应能力）
        if len(trades) >= 2:
            intervals = []
            sorted_trades = sorted(trades, key=lambda x: x.get("timestamp", ""))
            
            for i in range(1, len(sorted_trades)):
                try:
                    t1 = sorted_trades[i-1].get("timestamp", "")
                    t2 = sorted_trades[i].get("timestamp", "")
                    
                    dt1 = datetime.fromisoformat(t1.replace("Z", "+00:00")) if isinstance(t1, str) else t1
                    dt2 = datetime.fromisoformat(t2.replace("Z", "+00:00")) if isinstance(t2, str) else t2
                    
                    interval = (dt2 - dt1).total_seconds() / 60  # 分钟
                    intervals.append(interval)
                except:
                    continue
            
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                quick_trades = sum(1 for i in intervals if i < 5)  # 5分钟内
                
                if quick_trades / len(intervals) > 0.2:
                    patterns.append({
                        "type": "fast_reaction",
                        "description": f"{quick_trades}笔交易在5分钟内连续发生，可能对新闻快速反应",
                        "confidence": "高",
                        "is_news_sensitive": True
                    })
        
        # 4. 分析特定市场的交易密度（检测事件敏感性）
        market_trades = {}
        for trade in trades:
            market = trade.get("market_slug", "unknown")
            if market not in market_trades:
                market_trades[market] = []
            market_trades[market].append(trade)
        
        for market, mtrades in market_trades.items():
            if len(mtrades) >= 3:
                # 检测是否在短时间内大量交易同一市场
                try:
                    sorted_mt = sorted(mtrades, key=lambda x: x.get("timestamp", ""))
                    first = datetime.fromisoformat(sorted_mt[0].get("timestamp", "").replace("Z", "+00:00"))
                    last = datetime.fromisoformat(sorted_mt[-1].get("timestamp", "").replace("Z", "+00:00"))
                    
                    duration = (last - first).total_seconds() / 60  # 分钟
                    
                    if duration < 30 and len(mtrades) >= 3:
                        patterns.append({
                            "type": "market_burst",
                            "description": f"在 {market[:30]} 市场30分钟内进行{len(mtrades)}笔交易，可能知道内幕信息",
                            "market": market,
                            "confidence": "高",
                            "is_news_sensitive": True
                        })
                except:
                    continue
        
        # 判断是否是新闻敏感型
        is_news_sensitive = any(p.get("is_news_sensitive", False) for p in patterns)
        
        return {
            "patterns": patterns,
            "is_news_sensitive": is_news_sensitive,
            "hour_distribution": hour_distribution,
            "weekday_distribution": weekday_distribution,
            "analysis_time": datetime.now().isoformat()
        }
    
    def detect_news_front_running(
        self, 
        trades: List[Dict], 
        news_events: List[Dict] = None
    ) -> List[Dict]:
        """
        检测是否存在新闻前线行为（在重大新闻发布前下单）
        
        Args:
            trades: 交易列表
            news_events: 已知的新闻事件列表 [{"time": "...", "title": "...", "market": "..."}]
        
        Returns:
            可疑的前线交易列表
        """
        suspicious = []
        
        if not news_events:
            # 没有新闻数据，使用启发式检测
            # 检测在大幅价格变动前的交易
            return suspicious
        
        for trade in trades:
            try:
                trade_time = datetime.fromisoformat(trade.get("timestamp", "").replace("Z", "+00:00"))
                market = trade.get("market_slug", "")
                
                for event in news_events:
                    event_time = datetime.fromisoformat(event.get("time", "").replace("Z", "+00:00"))
                    event_market = event.get("market", "")
                    
                    # 检测是否在新闻发布前5-30分钟内交易
                    if market == event_market or event_market in market:
                        time_diff = (event_time - trade_time).total_seconds() / 60
                        
                        if 5 <= time_diff <= 30:
                            suspicious.append({
                                "trade": trade,
                                "event": event,
                                "time_before_news": f"{time_diff:.0f} 分钟",
                                "suspicion_level": "高" if time_diff < 10 else "中",
                                "reasoning": f"在 '{event.get('title', '新闻')}' 发布前 {time_diff:.0f} 分钟下单"
                            })
            except:
                continue
        
        return suspicious
    
    def get_smart_money_addresses(self, min_win_rate: float = 60, min_trades: int = 10) -> List[str]:
        """
        获取聪明钱地址列表
        
        Args:
            min_win_rate: 最低胜率
            min_trades: 最少交易次数
        
        Returns:
            符合条件的地址列表
        """
        # 这里需要从数据库查询
        # 暂时返回示例数据
        return [
            "0x1234...5678",
            "0xabcd...efgh"
        ]
    
    def to_dict(self, profile: TraderProfile) -> Dict:
        """将画像转换为字典"""
        return asdict(profile)


# 测试代码
if __name__ == "__main__":
    profiler = TraderProfiler()
    
    # 模拟交易数据
    mock_trades = [
        {
            "tx_hash": "0x123",
            "timestamp": "2026-01-25T10:00:00",
            "market_slug": "trump-wins-2024",
            "side": "BUY",
            "outcome": "YES",
            "price": 0.65,
            "size": 1000,
            "pnl": 350
        },
        {
            "tx_hash": "0x456",
            "timestamp": "2026-01-26T14:00:00",
            "market_slug": "fed-rate-decision",
            "side": "SELL",
            "outcome": "NO",
            "price": 0.35,
            "size": 500,
            "pnl": -175
        }
    ]
    
    profile = profiler.analyze_address("0xTestAddress", mock_trades)
    print(json.dumps(profiler.to_dict(profile), indent=2, ensure_ascii=False))
    
    # 测试时序分析
    print("\n时序模式分析:")
    timing = profiler.analyze_timing_patterns(mock_trades)
    print(json.dumps(timing, indent=2, ensure_ascii=False))
