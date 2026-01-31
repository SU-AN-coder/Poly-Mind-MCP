"""
WebSocket 实时推送服务
使用 Flask-SocketIO 实现交易和市场数据的实时推送
"""
import os
import json
import logging
import threading
import time
from typing import Dict, Set, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class WebSocketMessage:
    """WebSocket 消息结构"""
    event: str
    data: Any
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "data": self.data,
            "timestamp": self.timestamp
        }


class WebSocketManager:
    """
    WebSocket 连接管理器
    
    功能:
    - 管理客户端连接
    - 频道订阅（交易流、市场、交易者）
    - 广播消息
    - 心跳检测
    """
    
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.connected_clients: Set[str] = set()
        self.subscriptions: Dict[str, Set[str]] = {
            'trades': set(),       # 订阅所有交易
            'markets': set(),      # 订阅市场更新
            'smart_money': set(),  # 订阅聪明钱动态
        }
        self.market_subscriptions: Dict[str, Set[str]] = {}  # market_slug -> client_ids
        self.trader_subscriptions: Dict[str, Set[str]] = {}  # address -> client_ids
        self._lock = threading.Lock()
        self.stats = {
            "total_connections": 0,
            "messages_sent": 0,
            "start_time": datetime.now().isoformat()
        }
    
    def init_app(self, socketio):
        """初始化 SocketIO"""
        self.socketio = socketio
        self._register_handlers()
        logger.info("✓ WebSocket 管理器已初始化")
    
    def _register_handlers(self):
        """注册 SocketIO 事件处理器"""
        if not self.socketio:
            return
        
        @self.socketio.on('connect')
        def handle_connect():
            from flask import request
            client_id = request.sid
            with self._lock:
                self.connected_clients.add(client_id)
                self.stats["total_connections"] += 1
            logger.info(f"客户端连接: {client_id}")
            self.socketio.emit('connected', {
                'client_id': client_id,
                'message': 'Welcome to PolyMind MCP WebSocket'
            }, to=client_id)
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            from flask import request
            client_id = request.sid
            self._remove_client(client_id)
            logger.info(f"客户端断开: {client_id}")
        
        @self.socketio.on('subscribe')
        def handle_subscribe(data):
            from flask import request
            client_id = request.sid
            channel = data.get('channel')
            target = data.get('target')  # market_slug 或 address
            
            success = self.subscribe(client_id, channel, target)
            self.socketio.emit('subscribed', {
                'channel': channel,
                'target': target,
                'success': success
            }, to=client_id)
        
        @self.socketio.on('unsubscribe')
        def handle_unsubscribe(data):
            from flask import request
            client_id = request.sid
            channel = data.get('channel')
            target = data.get('target')
            
            self.unsubscribe(client_id, channel, target)
            self.socketio.emit('unsubscribed', {
                'channel': channel,
                'target': target
            }, to=client_id)
        
        @self.socketio.on('ping')
        def handle_ping():
            from flask import request
            self.socketio.emit('pong', {
                'timestamp': datetime.now().isoformat()
            }, to=request.sid)
    
    def _remove_client(self, client_id: str):
        """移除客户端及其所有订阅"""
        with self._lock:
            self.connected_clients.discard(client_id)
            
            # 从所有频道移除
            for channel_clients in self.subscriptions.values():
                channel_clients.discard(client_id)
            
            # 从市场订阅移除
            for market_clients in self.market_subscriptions.values():
                market_clients.discard(client_id)
            
            # 从交易者订阅移除
            for trader_clients in self.trader_subscriptions.values():
                trader_clients.discard(client_id)
    
    def subscribe(
        self,
        client_id: str,
        channel: str,
        target: str = None
    ) -> bool:
        """
        订阅频道
        
        Args:
            client_id: 客户端 ID
            channel: 频道名称 (trades, markets, smart_money, market, trader)
            target: 目标标识 (market_slug 或 address)
        """
        with self._lock:
            if channel in self.subscriptions:
                self.subscriptions[channel].add(client_id)
                logger.debug(f"客户端 {client_id} 订阅 {channel}")
                return True
            
            elif channel == 'market' and target:
                if target not in self.market_subscriptions:
                    self.market_subscriptions[target] = set()
                self.market_subscriptions[target].add(client_id)
                logger.debug(f"客户端 {client_id} 订阅市场 {target}")
                return True
            
            elif channel == 'trader' and target:
                target = target.lower()
                if target not in self.trader_subscriptions:
                    self.trader_subscriptions[target] = set()
                self.trader_subscriptions[target].add(client_id)
                logger.debug(f"客户端 {client_id} 订阅交易者 {target}")
                return True
            
            return False
    
    def unsubscribe(
        self,
        client_id: str,
        channel: str,
        target: str = None
    ):
        """取消订阅"""
        with self._lock:
            if channel in self.subscriptions:
                self.subscriptions[channel].discard(client_id)
            elif channel == 'market' and target:
                if target in self.market_subscriptions:
                    self.market_subscriptions[target].discard(client_id)
            elif channel == 'trader' and target:
                target = target.lower()
                if target in self.trader_subscriptions:
                    self.trader_subscriptions[target].discard(client_id)
    
    def broadcast_trade(self, trade: Dict):
        """
        广播新交易
        
        发送到:
        - trades 频道的所有订阅者
        - 相关市场的订阅者
        - 相关交易者的订阅者
        """
        if not self.socketio:
            return
        
        message = WebSocketMessage(event='new_trade', data=trade)
        msg_dict = message.to_dict()
        
        # 发送到 trades 频道
        for client_id in list(self.subscriptions.get('trades', [])):
            try:
                self.socketio.emit('new_trade', msg_dict, to=client_id)
                self.stats["messages_sent"] += 1
            except Exception as e:
                logger.error(f"发送交易消息失败: {e}")
        
        # 发送到市场订阅者
        market_slug = trade.get('market_slug')
        if market_slug and market_slug in self.market_subscriptions:
            for client_id in list(self.market_subscriptions[market_slug]):
                try:
                    self.socketio.emit('market_trade', msg_dict, to=client_id)
                    self.stats["messages_sent"] += 1
                except Exception as e:
                    logger.error(f"发送市场交易消息失败: {e}")
        
        # 发送到交易者订阅者
        for address_field in ['maker', 'taker']:
            address = trade.get(address_field, '').lower()
            if address and address in self.trader_subscriptions:
                for client_id in list(self.trader_subscriptions[address]):
                    try:
                        self.socketio.emit('trader_activity', msg_dict, to=client_id)
                        self.stats["messages_sent"] += 1
                    except Exception as e:
                        logger.error(f"发送交易者活动消息失败: {e}")
    
    def broadcast_market_update(self, market_slug: str, data: Dict):
        """广播市场更新"""
        if not self.socketio:
            return
        
        message = WebSocketMessage(event='market_update', data=data)
        msg_dict = message.to_dict()
        
        # 发送到 markets 频道
        for client_id in list(self.subscriptions.get('markets', [])):
            try:
                self.socketio.emit('market_update', msg_dict, to=client_id)
                self.stats["messages_sent"] += 1
            except Exception as e:
                logger.error(f"发送市场更新失败: {e}")
        
        # 发送到特定市场订阅者
        if market_slug in self.market_subscriptions:
            for client_id in list(self.market_subscriptions[market_slug]):
                try:
                    self.socketio.emit('market_update', msg_dict, to=client_id)
                    self.stats["messages_sent"] += 1
                except Exception as e:
                    logger.error(f"发送市场更新失败: {e}")
    
    def broadcast_smart_money(self, activity: Dict):
        """广播聪明钱活动"""
        if not self.socketio:
            return
        
        message = WebSocketMessage(event='smart_money_activity', data=activity)
        msg_dict = message.to_dict()
        
        for client_id in list(self.subscriptions.get('smart_money', [])):
            try:
                self.socketio.emit('smart_money_activity', msg_dict, to=client_id)
                self.stats["messages_sent"] += 1
            except Exception as e:
                logger.error(f"发送聪明钱活动失败: {e}")
    
    def broadcast_all(self, event: str, data: Any):
        """向所有连接的客户端广播"""
        if not self.socketio:
            return
        
        message = WebSocketMessage(event=event, data=data)
        self.socketio.emit(event, message.to_dict())
        self.stats["messages_sent"] += 1
    
    def get_stats(self) -> Dict:
        """获取 WebSocket 统计"""
        return {
            **self.stats,
            "connected_clients": len(self.connected_clients),
            "channel_subscribers": {
                channel: len(clients)
                for channel, clients in self.subscriptions.items()
            },
            "market_subscribers": len(self.market_subscriptions),
            "trader_subscribers": len(self.trader_subscriptions)
        }


# 全局实例
ws_manager = WebSocketManager()


def init_websocket(app, **kwargs):
    """
    初始化 WebSocket 服务
    
    Args:
        app: Flask 应用
        **kwargs: SocketIO 配置参数
    """
    try:
        from flask_socketio import SocketIO
        
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode='threading',  # 使用线程模式
            logger=False,
            engineio_logger=False,
            **kwargs
        )
        
        ws_manager.init_app(socketio)
        
        logger.info("✓ WebSocket 服务已初始化")
        return socketio
        
    except ImportError:
        logger.warning("flask-socketio 未安装，WebSocket 功能不可用")
        return None
    except Exception as e:
        logger.error(f"WebSocket 初始化失败: {e}")
        return None


class TradeStreamSimulator:
    """
    交易流模拟器（用于测试）
    模拟实时交易数据推送
    """
    
    def __init__(self, ws_manager: WebSocketManager, db_path: str = None):
        self.ws_manager = ws_manager
        self.db_path = db_path or os.getenv(
            "DB_PATH",
            "data/polymarket.db"
        )
        self.running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self, interval: float = 2.0):
        """启动模拟器"""
        if self.running:
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._run, args=(interval,))
        self._thread.daemon = True
        self._thread.start()
        logger.info(f"交易流模拟器已启动 (间隔: {interval}s)")
    
    def stop(self):
        """停止模拟器"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("交易流模拟器已停止")
    
    def _run(self, interval: float):
        """运行模拟"""
        import sqlite3
        import random
        
        while self.running:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 随机获取一条最近交易
                cursor.execute("""
                    SELECT t.*, m.slug as market_slug, m.title as market_title
                    FROM trades t
                    LEFT JOIN markets m ON (
                        t.token_id = m.yes_token_id OR t.token_id = m.no_token_id
                    )
                    ORDER BY RANDOM()
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    trade = dict(row)
                    trade['timestamp'] = datetime.now().isoformat()
                    trade['simulated'] = True
                    
                    # 广播交易
                    self.ws_manager.broadcast_trade(trade)
                
            except Exception as e:
                logger.error(f"模拟交易流失败: {e}")
            
            time.sleep(interval)
