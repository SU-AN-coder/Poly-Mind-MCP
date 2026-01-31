"""
交易者画像分析模块
分析交易者的行为模式、风格和表现
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TraderStats:
    """交易者统计数据"""
    total_trades: int = 0
    buy_count: int = 0
    sell_count: int = 0
    total_volume: float = 0.0
    avg_size: float = 0.0
    win_rate: float = 0.0
    avg_price: float = 0.5
    unique_markets: int = 0
    first_trade_date: str = ""
    last_trade_date: str = ""
    active_days: int = 0


@dataclass
class TraderProfile:
    """交易者画像"""
    address: str
    stats: TraderStats = field(default_factory=TraderStats)
    labels: List[str] = field(default_factory=list)
    trading_style: str = "未知"
    risk_level: str = "中等"
    market_focus: List[str] = field(default_factory=list)
    time_patterns: Dict = field(default_factory=dict)
    analysis_summary: str = ""
    confidence_score: float = 0.0


class TraderProfiler:
    """交易者画像分析器"""
    
    def __init__(self):
        self.label_thresholds = {
            "whale": 10000,           # 交易量超过 $10,000
            "active": 50,             # 交易次数超过 50
            "sniper": 0.85,           # 平均价格低于 0.15 或高于 0.85
            "diversified": 5,         # 参与市场数量超过 5
            "high_frequency": 10,     # 日均交易超过 10
        }
    
    def analyze_address(self, address: str, trades: List[Dict]) -> TraderProfile:
        """分析地址的交易行为"""
        if not trades:
            return TraderProfile(
                address=address,
                analysis_summary="暂无交易数据"
            )
        
        # 计算基础统计
        stats = self._calculate_stats(trades)
        
        # 生成标签
        labels = self._generate_labels(stats, trades)
        
        # 判断交易风格
        trading_style = self._determine_style(stats, trades)
        
        # 评估风险等级
        risk_level = self._assess_risk(stats, trades)
        
        # 分析市场偏好
        market_focus = self._analyze_market_focus(trades)
        
        # 分析时间模式
        time_patterns = self.analyze_timing_patterns(trades)
        
        # 生成分析摘要
        summary = self._generate_summary(stats, labels, trading_style, risk_level)
        
        # 计算置信度
        confidence = min(1.0, len(trades) / 100)
        
        return TraderProfile(
            address=address,
            stats=stats,
            labels=labels,
            trading_style=trading_style,
            risk_level=risk_level,
            market_focus=market_focus[:5],
            time_patterns=time_patterns,
            analysis_summary=summary,
            confidence_score=round(confidence, 2)
        )
    
    def _calculate_stats(self, trades: List[Dict]) -> TraderStats:
        """计算交易统计数据"""
        if not trades:
            return TraderStats()
        
        buy_count = sum(1 for t in trades if t.get("side") == "BUY")
        sell_count = len(trades) - buy_count
        
        # 计算交易量
        volumes = []
        prices = []
        markets = set()
        timestamps = []
        
        for t in trades:
            size = float(t.get("size", 0) or t.get("maker_amount", 0) or 0)
            if isinstance(t.get("maker_amount"), (int, float)) and t.get("maker_amount", 0) > 1000:
                size = float(t.get("maker_amount", 0)) / 1e6
            volumes.append(size)
            
            price = float(t.get("price", 0.5) or 0.5)
            prices.append(price)
            
            market = t.get("market_slug", "unknown")
            if market:
                markets.add(market)
            
            ts = t.get("timestamp", "")
            if ts:
                timestamps.append(ts)
        
        total_volume = sum(volumes)
        avg_size = total_volume / len(trades) if trades else 0
        avg_price = statistics.mean(prices) if prices else 0.5
        
        # 估算胜率（简化：买入低价/卖出高价视为潜在盈利）
        potential_wins = sum(1 for t in trades 
            if (t.get("side") == "BUY" and float(t.get("price", 0.5) or 0.5) < 0.4) or
               (t.get("side") == "SELL" and float(t.get("price", 0.5) or 0.5) > 0.6))
        win_rate = (potential_wins / len(trades) * 100) if trades else 0
        
        # 计算活跃天数
        first_trade = min(timestamps) if timestamps else ""
        last_trade = max(timestamps) if timestamps else ""
        active_days = self._calculate_active_days(timestamps)
        
        return TraderStats(
            total_trades=len(trades),
            buy_count=buy_count,
            sell_count=sell_count,
            total_volume=round(total_volume, 2),
            avg_size=round(avg_size, 2),
            win_rate=round(win_rate, 1),
            avg_price=round(avg_price, 4),
            unique_markets=len(markets),
            first_trade_date=first_trade,
            last_trade_date=last_trade,
            active_days=active_days
        )
    
    def _calculate_active_days(self, timestamps: List[str]) -> int:
        """计算活跃天数"""
        if not timestamps:
            return 0
        
        dates = set()
        for ts in timestamps:
            try:
                if 'T' in ts:
                    date = ts.split('T')[0]
                else:
                    date = ts[:10]
                dates.add(date)
            except:
                continue
        return len(dates)
    
    def _generate_labels(self, stats: TraderStats, trades: List[Dict]) -> List[str]:
        """生成交易者标签"""
        labels = []
        
        # 鲸鱼标签
        if stats.total_volume >= self.label_thresholds["whale"]:
            labels.append("🐋 鲸鱼")
        
        # 活跃交易者
        if stats.total_trades >= self.label_thresholds["active"]:
            labels.append("⚡ 活跃交易者")
        
        # 狙击手（擅长低买高卖）
        if stats.avg_price < 0.15 or stats.avg_price > 0.85:
            labels.append("🎯 狙击手")
        
        # 分散投资者
        if stats.unique_markets >= self.label_thresholds["diversified"]:
            labels.append("📊 分散投资")
        
        # 高频交易者
        if stats.active_days > 0:
            daily_avg = stats.total_trades / stats.active_days
            if daily_avg >= self.label_thresholds["high_frequency"]:
                labels.append("🚀 高频交易")
        
        # 买入倾向
        if stats.buy_count > stats.sell_count * 2:
            labels.append("📈 买入倾向")
        elif stats.sell_count > stats.buy_count * 2:
            labels.append("📉 卖出倾向")
        
        # 大单交易者
        if stats.avg_size > 1000:
            labels.append("💰 大单交易")
        
        # 新手
        if stats.total_trades < 5:
            labels.append("🌱 新手")
        
        # 高胜率
        if stats.win_rate > 60 and stats.total_trades >= 10:
            labels.append("🏆 高胜率")
        
        return labels
    
    def _determine_style(self, stats: TraderStats, trades: List[Dict]) -> str:
        """判断交易风格"""
        if stats.total_trades < 3:
            return "数据不足"
        
        # 高频 + 小单 = 刮头皮
        if stats.active_days > 0:
            daily_avg = stats.total_trades / stats.active_days
            if daily_avg > 5 and stats.avg_size < 100:
                return "刮头皮型"
        
        # 大单 + 低频 = 价值投资
        if stats.avg_size > 500 and stats.total_trades < 20:
            return "价值投资型"
        
        # 集中 + 高胜率 = 专注型
        if stats.unique_markets <= 3 and stats.win_rate > 55:
            return "专注型"
        
        # 分散 = 分散投资型
        if stats.unique_markets > 5:
            return "分散投资型"
        
        # 买卖均衡 = 套利型
        buy_ratio = stats.buy_count / stats.total_trades if stats.total_trades > 0 else 0.5
        if 0.4 <= buy_ratio <= 0.6:
            return "套利型"
        
        return "混合型"
    
    def _assess_risk(self, stats: TraderStats, trades: List[Dict]) -> str:
        """评估风险等级"""
        risk_score = 0
        
        # 大单增加风险
        if stats.avg_size > 1000:
            risk_score += 2
        elif stats.avg_size > 500:
            risk_score += 1
        
        # 集中投资增加风险
        if stats.unique_markets <= 2:
            risk_score += 2
        elif stats.unique_markets <= 4:
            risk_score += 1
        
        # 极端价格交易增加风险
        if stats.avg_price < 0.1 or stats.avg_price > 0.9:
            risk_score += 2
        
        # 高频交易增加风险
        if stats.active_days > 0 and stats.total_trades / stats.active_days > 10:
            risk_score += 1
        
        if risk_score >= 5:
            return "高风险"
        elif risk_score >= 3:
            return "中高风险"
        elif risk_score >= 1:
            return "中等风险"
        else:
            return "低风险"
    
    def _analyze_market_focus(self, trades: List[Dict]) -> List[str]:
        """分析市场偏好"""
        market_counts = defaultdict(int)
        for t in trades:
            market = t.get("market_slug", "unknown")
            if market and market != "unknown":
                market_counts[market] += 1
        
        # 按交易次数排序
        sorted_markets = sorted(market_counts.items(), key=lambda x: x[1], reverse=True)
        return [m[0] for m in sorted_markets[:5]]
    
    def analyze_timing_patterns(self, trades: List[Dict]) -> Dict:
        """分析交易时序模式"""
        if not trades:
            return {"patterns": [], "is_news_sensitive": False}
        
        hourly_counts = defaultdict(int)
        daily_counts = defaultdict(int)
        intervals = []
        
        prev_time = None
        for t in trades:
            ts = t.get("timestamp", "")
            if not ts:
                continue
            
            try:
                if 'T' in ts:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S')
                
                hourly_counts[dt.hour] += 1
                daily_counts[dt.strftime('%A')] += 1
                
                if prev_time:
                    interval = (dt - prev_time).total_seconds()
                    if interval > 0:
                        intervals.append(interval)
                prev_time = dt
            except:
                continue
        
        patterns = []
        is_news_sensitive = False
        
        # 分析高峰时段
        if hourly_counts:
            peak_hour = max(hourly_counts, key=hourly_counts.get)
            patterns.append(f"交易高峰: {peak_hour}:00")
            
            # 新闻敏感型：交易集中在美国交易时段
            us_hours = sum(hourly_counts.get(h, 0) for h in range(14, 22))
            total_trades = sum(hourly_counts.values())
            if total_trades > 0 and us_hours / total_trades > 0.6:
                is_news_sensitive = True
                patterns.append("交易集中在美国时段")
        
        # 分析交易间隔
        if intervals:
            avg_interval = statistics.mean(intervals)
            if avg_interval < 300:  # 小于5分钟
                patterns.append("高频交易模式")
            elif avg_interval > 86400:  # 大于1天
                patterns.append("长线交易模式")
        
        # 分析活跃日
        if daily_counts:
            peak_day = max(daily_counts, key=daily_counts.get)
            patterns.append(f"最活跃: {peak_day}")
        
        return {
            "patterns": patterns,
            "is_news_sensitive": is_news_sensitive,
            "hourly_distribution": dict(hourly_counts),
            "daily_distribution": dict(daily_counts),
            "avg_interval_seconds": round(statistics.mean(intervals), 2) if intervals else 0
        }
    
    def _generate_summary(self, stats: TraderStats, labels: List[str], 
                         trading_style: str, risk_level: str) -> str:
        """生成分析摘要"""
        parts = []
        
        # 交易规模描述
        if stats.total_volume > 10000:
            parts.append(f"大额交易者，总交易量 ${stats.total_volume:,.2f}")
        elif stats.total_volume > 1000:
            parts.append(f"中等规模交易者，总交易量 ${stats.total_volume:,.2f}")
        else:
            parts.append(f"小额交易者，总交易量 ${stats.total_volume:,.2f}")
        
        # 交易风格
        parts.append(f"交易风格为{trading_style}")
        
        # 风险等级
        parts.append(f"风险等级{risk_level}")
        
        # 胜率
        if stats.total_trades >= 10:
            if stats.win_rate > 60:
                parts.append(f"潜在胜率较高({stats.win_rate:.1f}%)")
            elif stats.win_rate < 40:
                parts.append(f"潜在胜率偏低({stats.win_rate:.1f}%)")
        
        # 市场分散度
        if stats.unique_markets > 5:
            parts.append(f"在{stats.unique_markets}个市场分散投资")
        elif stats.unique_markets == 1:
            parts.append("专注于单一市场")
        
        return "，".join(parts) + "。"
    
    def to_dict(self, profile: TraderProfile) -> Dict:
        """将 Profile 转换为字典"""
        return {
            "address": profile.address,
            "stats": asdict(profile.stats),
            "labels": profile.labels,
            "trading_style": profile.trading_style,
            "risk_level": profile.risk_level,
            "market_focus": profile.market_focus,
            "time_patterns": profile.time_patterns,
            "analysis_summary": profile.analysis_summary,
            "confidence_score": profile.confidence_score,
            "timestamp": datetime.now().isoformat()
        }


# 测试
if __name__ == "__main__":
    profiler = TraderProfiler()
    
    # 模拟交易数据
    mock_trades = [
        {"side": "BUY", "price": 0.35, "size": 500, "market_slug": "trump-2024", "timestamp": "2024-01-15T10:30:00Z"},
        {"side": "BUY", "price": 0.42, "size": 300, "market_slug": "trump-2024", "timestamp": "2024-01-15T14:20:00Z"},
        {"side": "SELL", "price": 0.65, "size": 400, "market_slug": "trump-2024", "timestamp": "2024-01-16T09:15:00Z"},
        {"side": "BUY", "price": 0.28, "size": 600, "market_slug": "bitcoin-100k", "timestamp": "2024-01-17T16:45:00Z"},
        {"side": "BUY", "price": 0.22, "size": 800, "market_slug": "fed-rate-cut", "timestamp": "2024-01-18T11:00:00Z"},
    ]
    
    profile = profiler.analyze_address("0x1234567890abcdef", mock_trades)
    result = profiler.to_dict(profile)
    
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
