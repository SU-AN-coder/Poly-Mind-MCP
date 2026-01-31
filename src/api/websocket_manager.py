"""
WebSocket 连接管理器
支持实时交易推送和频道订阅
"""
import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WebSocketClient:
    """WebSocket 客户端"""
    client_id: str
    subscriptions: Set[str] = field(default_factory=set)
    connected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_activity: str = field(default_factory=lambda: datetime.now().isoformat())


class WebSocketManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.clients: Dict[str, WebSocketClient] = {}
        self.channel_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self.message_queue: asyncio.Queue = None
        self._running = False
        
        self.supported_channels = {
            'trades',
            'large_trades',
            'smart_money',
            'arbitrage',
            'markets',
            'alerts',
        }
    
    def register_client(self, client_id: str) -> WebSocketClient:
        """注册新客户端"""
        client = WebSocketClient(client_id=client_id)
        self.clients[client_id] = client
        logger.info(f"WebSocket 客户端注册: {client_id}")
        return client
    
    def unregister_client(self, client_id: str):
        """注销客户端"""
        if client_id in self.clients:
            client = self.clients[client_id]
            for channel in client.subscriptions:
                self.channel_subscribers[channel].discard(client_id)
            del self.clients[client_id]
            logger.info(f"WebSocket 客户端注销: {client_id}")
    
    def subscribe(self, client_id: str, channel: str, target: Optional[str] = None) -> bool:
        """订阅频道"""
        if client_id not in self.clients:
            return False
        
        full_channel = f"{channel}:{target}" if target else channel
        self.clients[client_id].subscriptions.add(full_channel)
        self.channel_subscribers[full_channel].add(client_id)
        logger.info(f"客户端 {client_id} 订阅频道: {full_channel}")
        return True
    
    def unsubscribe(self, client_id: str, channel: str, target: Optional[str] = None) -> bool:
        """取消订阅"""
        if client_id not in self.clients:
            return False
        
        full_channel = f"{channel}:{target}" if target else channel
        self.clients[client_id].subscriptions.discard(full_channel)
        self.channel_subscribers[full_channel].discard(client_id)
        logger.info(f"客户端 {client_id} 取消订阅: {full_channel}")
        return True
    
    def get_subscribers(self, channel: str, target: Optional[str] = None) -> Set[str]:
        """获取频道订阅者"""
        full_channel = f"{channel}:{target}" if target else channel
        subscribers = self.channel_subscribers.get(full_channel, set()).copy()
        subscribers.update(self.channel_subscribers.get(channel, set()))
        return subscribers
    
    def broadcast_to_channel(self, channel: str, data: Dict, target: Optional[str] = None) -> int:
        """向频道广播消息"""
        subscribers = self.get_subscribers(channel, target)
        message = {
            "channel": channel,
            "target": target,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        return len(subscribers)
    
    def get_stats(self) -> Dict:
        """获取 WebSocket 统计"""
        channel_stats = {}
        for channel in self.supported_channels:
            channel_stats[channel] = len(self.channel_subscribers.get(channel, set()))
        
        return {
            "total_clients": len(self.clients),
            "channels": channel_stats,
            "supported_channels": list(self.supported_channels),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_client_info(self, client_id: str) -> Optional[Dict]:
        """获取客户端信息"""
        if client_id not in self.clients:
            return None
        client = self.clients[client_id]
        return {
            "client_id": client.client_id,
            "subscriptions": list(client.subscriptions),
            "connected_at": client.connected_at,
            "last_activity": client.last_activity
        }


ws_manager = WebSocketManager()


class MessageBuilder:
    """WebSocket 消息构建器"""
    
    @staticmethod
    def new_trade(trade: Dict) -> Dict:
        """构建新交易消息"""
        size = float(trade.get('size', 0) or trade.get('maker_amount', 0) or 0)
        if size > 1000000:
            size = size / 1e6
        
        return {
            "type": "new_trade",
            "trade": {
                "tx_hash": trade.get('tx_hash'),
                "market_slug": trade.get('market_slug'),
                "side": trade.get('side'),
                "outcome": trade.get('outcome'),
                "price": float(trade.get('price', 0)),
                "size": size,
                "maker": trade.get('maker'),
                "timestamp": trade.get('timestamp')
            },
            "is_large": size >= 1000
        }
    
    @staticmethod
    def large_trade_alert(trade: Dict) -> Dict:
        """构建大单提醒"""
        size = float(trade.get('size', 0) or trade.get('maker_amount', 0) or 0)
        if size > 1000000:
            size = size / 1e6
        
        return {
            "type": "large_trade_alert",
            "alert": {
                "level": "high" if size >= 10000 else "medium",
                "message": f"检测到大单: ${size:,.2f} {trade.get('side', 'TRADE')}",
                "trade": trade
            }
        }
    
    @staticmethod
    def smart_money_activity(activity: Dict) -> Dict:
        """构建聪明钱活动消息"""
        return {
            "type": "smart_money_activity",
            "activity": activity
        }
    
    @staticmethod
    def arbitrage_opportunity(opportunity: Dict) -> Dict:
        """构建套利机会消息"""
        return {
            "type": "arbitrage_opportunity",
            "opportunity": opportunity
        }
    
    @staticmethod
    def market_update(market: Dict) -> Dict:
        """构建市场更新消息"""
        return {
            "type": "market_update",
            "market": market
        }
