"""
持仓 PnL（盈亏）计算模块
计算交易者在各市场的持仓和盈亏
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, asdict
from datetime import datetime
import sqlite3
import os

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """持仓数据"""
    token_id: str
    market_slug: str
    market_title: str
    outcome: str  # YES / NO
    size: Decimal  # 持仓数量
    avg_cost: Decimal  # 平均成本
    current_price: Decimal  # 当前价格
    unrealized_pnl: Decimal  # 未实现盈亏
    unrealized_pnl_pct: Decimal  # 未实现盈亏百分比
    realized_pnl: Decimal  # 已实现盈亏
    total_cost: Decimal  # 总成本
    current_value: Decimal  # 当前价值
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "token_id": self.token_id,
            "market_slug": self.market_slug,
            "market_title": self.market_title,
            "outcome": self.outcome,
            "size": str(self.size),
            "avg_cost": str(self.avg_cost),
            "current_price": str(self.current_price),
            "unrealized_pnl": str(self.unrealized_pnl),
            "unrealized_pnl_pct": f"{self.unrealized_pnl_pct:.2f}%",
            "realized_pnl": str(self.realized_pnl),
            "total_cost": str(self.total_cost),
            "current_value": str(self.current_value)
        }


@dataclass
class PortfolioSummary:
    """投资组合摘要"""
    address: str
    total_positions: int
    total_cost: Decimal
    current_value: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    total_pnl: Decimal
    pnl_percentage: Decimal
    winning_positions: int
    losing_positions: int
    positions: List[Position]
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "address": self.address,
            "total_positions": self.total_positions,
            "total_cost": str(self.total_cost),
            "current_value": str(self.current_value),
            "total_unrealized_pnl": str(self.total_unrealized_pnl),
            "total_realized_pnl": str(self.total_realized_pnl),
            "total_pnl": str(self.total_pnl),
            "pnl_percentage": f"{self.pnl_percentage:.2f}%",
            "winning_positions": self.winning_positions,
            "losing_positions": self.losing_positions,
            "positions": [p.to_dict() for p in self.positions]
        }


class PnLCalculator:
    """
    持仓盈亏计算器
    
    功能:
    - 计算单个交易者的持仓
    - 计算未实现和已实现盈亏
    - 支持多市场聚合
    """
    
    USDC_DECIMALS = 6
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv(
            "DB_PATH",
            os.path.join(os.path.dirname(__file__), "../../data/polymarket.db")
        )
    
    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_trader_positions(
        self,
        address: str,
        include_closed: bool = False
    ) -> List[Dict]:
        """
        获取交易者的所有持仓
        
        通过聚合买入和卖出交易计算净持仓
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            address = address.lower()
            
            # 获取所有相关交易
            # maker 或 taker 为该地址的交易
            cursor.execute("""
                SELECT 
                    t.token_id,
                    t.side,
                    t.maker,
                    t.taker,
                    t.maker_amount,
                    t.taker_amount,
                    t.price,
                    t.timestamp,
                    m.slug as market_slug,
                    m.title as market_title,
                    m.yes_token_id,
                    m.no_token_id
                FROM trades t
                LEFT JOIN markets m ON (
                    t.token_id = m.yes_token_id OR t.token_id = m.no_token_id
                )
                WHERE LOWER(t.maker) = ? OR LOWER(t.taker) = ?
                ORDER BY t.timestamp ASC, t.id ASC
            """, (address, address))
            
            trades = cursor.fetchall()
            
            # 按 token_id 聚合持仓
            positions_map: Dict[str, Dict] = {}
            
            for trade in trades:
                token_id = trade['token_id']
                if not token_id:
                    continue
                
                # 确定用户在这笔交易中的角色和方向
                is_maker = trade['maker'].lower() == address
                trade_side = trade['side']  # 原始交易方向
                
                # 解析金额
                try:
                    maker_amount = Decimal(trade['maker_amount'] or '0')
                    taker_amount = Decimal(trade['taker_amount'] or '0')
                except:
                    continue
                
                # 计算价格和数量
                if trade_side == 'BUY':
                    # 原交易是买入：maker 出 USDC 买 token
                    if is_maker:
                        # 用户是 maker，买入 token
                        size = taker_amount / Decimal(10 ** self.USDC_DECIMALS)
                        cost = maker_amount / Decimal(10 ** self.USDC_DECIMALS)
                        user_side = 'BUY'
                    else:
                        # 用户是 taker，卖出 token
                        size = taker_amount / Decimal(10 ** self.USDC_DECIMALS)
                        cost = maker_amount / Decimal(10 ** self.USDC_DECIMALS)
                        user_side = 'SELL'
                else:
                    # 原交易是卖出：maker 出 token 卖
                    if is_maker:
                        # 用户是 maker，卖出 token
                        size = maker_amount / Decimal(10 ** self.USDC_DECIMALS)
                        cost = taker_amount / Decimal(10 ** self.USDC_DECIMALS)
                        user_side = 'SELL'
                    else:
                        # 用户是 taker，买入 token
                        size = maker_amount / Decimal(10 ** self.USDC_DECIMALS)
                        cost = taker_amount / Decimal(10 ** self.USDC_DECIMALS)
                        user_side = 'BUY'
                
                # 初始化持仓记录
                if token_id not in positions_map:
                    # 判断是 YES 还是 NO
                    if trade['yes_token_id'] == token_id:
                        outcome = 'YES'
                    elif trade['no_token_id'] == token_id:
                        outcome = 'NO'
                    else:
                        outcome = 'UNKNOWN'
                    
                    positions_map[token_id] = {
                        'token_id': token_id,
                        'market_slug': trade['market_slug'] or 'unknown',
                        'market_title': trade['market_title'] or 'Unknown Market',
                        'outcome': outcome,
                        'total_bought': Decimal('0'),
                        'total_sold': Decimal('0'),
                        'total_cost': Decimal('0'),
                        'total_proceeds': Decimal('0'),
                        'trades_count': 0
                    }
                
                pos = positions_map[token_id]
                pos['trades_count'] += 1
                
                if user_side == 'BUY':
                    pos['total_bought'] += size
                    pos['total_cost'] += cost
                else:
                    pos['total_sold'] += size
                    pos['total_proceeds'] += cost
            
            # 计算净持仓
            result = []
            for token_id, pos in positions_map.items():
                net_size = pos['total_bought'] - pos['total_sold']
                
                # 跳过已平仓（除非要求包含）
                if not include_closed and abs(net_size) < Decimal('0.001'):
                    continue
                
                # 计算平均成本
                if pos['total_bought'] > 0:
                    avg_cost = pos['total_cost'] / pos['total_bought']
                else:
                    avg_cost = Decimal('0')
                
                # 已实现盈亏 = 卖出收入 - 卖出部分的成本
                if pos['total_sold'] > 0 and pos['total_bought'] > 0:
                    sold_cost = pos['total_sold'] * avg_cost
                    realized_pnl = pos['total_proceeds'] - sold_cost
                else:
                    realized_pnl = Decimal('0')
                
                result.append({
                    'token_id': token_id,
                    'market_slug': pos['market_slug'],
                    'market_title': pos['market_title'],
                    'outcome': pos['outcome'],
                    'net_size': str(net_size.quantize(Decimal('0.0001'))),
                    'avg_cost': str(avg_cost.quantize(Decimal('0.0001'))),
                    'total_cost': str(pos['total_cost'].quantize(Decimal('0.01'))),
                    'realized_pnl': str(realized_pnl.quantize(Decimal('0.01'))),
                    'trades_count': pos['trades_count']
                })
            
            return result
            
        finally:
            conn.close()
    
    def calculate_portfolio_pnl(
        self,
        address: str,
        current_prices: Dict[str, Decimal] = None
    ) -> PortfolioSummary:
        """
        计算完整的投资组合盈亏
        
        Args:
            address: 交易者地址
            current_prices: token_id -> 当前价格 的映射（如果不提供，使用最后交易价格）
        """
        positions_data = self.get_trader_positions(address, include_closed=False)
        current_prices = current_prices or {}
        
        positions: List[Position] = []
        total_cost = Decimal('0')
        current_value = Decimal('0')
        total_unrealized = Decimal('0')
        total_realized = Decimal('0')
        winning = 0
        losing = 0
        
        for pos_data in positions_data:
            token_id = pos_data['token_id']
            size = Decimal(pos_data['net_size'])
            avg_cost = Decimal(pos_data['avg_cost'])
            cost = Decimal(pos_data['total_cost'])
            realized = Decimal(pos_data['realized_pnl'])
            
            # 获取当前价格
            if token_id in current_prices:
                current_price = current_prices[token_id]
            else:
                # 使用平均成本作为估算（无实时价格时）
                current_price = avg_cost
            
            # 计算当前价值和未实现盈亏
            if size > 0:
                position_value = size * current_price
                unrealized = position_value - (size * avg_cost)
            else:
                position_value = Decimal('0')
                unrealized = Decimal('0')
            
            # 计算百分比
            if size * avg_cost > 0:
                unrealized_pct = (unrealized / (size * avg_cost)) * 100
            else:
                unrealized_pct = Decimal('0')
            
            position = Position(
                token_id=token_id,
                market_slug=pos_data['market_slug'],
                market_title=pos_data['market_title'],
                outcome=pos_data['outcome'],
                size=size,
                avg_cost=avg_cost,
                current_price=current_price,
                unrealized_pnl=unrealized,
                unrealized_pnl_pct=unrealized_pct,
                realized_pnl=realized,
                total_cost=cost,
                current_value=position_value
            )
            positions.append(position)
            
            # 汇总
            total_cost += cost
            current_value += position_value
            total_unrealized += unrealized
            total_realized += realized
            
            if unrealized >= 0:
                winning += 1
            else:
                losing += 1
        
        # 总盈亏
        total_pnl = total_unrealized + total_realized
        pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else Decimal('0')
        
        return PortfolioSummary(
            address=address,
            total_positions=len(positions),
            total_cost=total_cost,
            current_value=current_value,
            total_unrealized_pnl=total_unrealized,
            total_realized_pnl=total_realized,
            total_pnl=total_pnl,
            pnl_percentage=pnl_pct,
            winning_positions=winning,
            losing_positions=losing,
            positions=sorted(positions, key=lambda p: p.unrealized_pnl, reverse=True)
        )
    
    def get_market_pnl_leaderboard(
        self,
        market_slug: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        获取盈亏排行榜
        
        显示在特定市场（或全部市场）中盈利最多的交易者
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # 获取活跃交易者
            if market_slug:
                cursor.execute("""
                    SELECT DISTINCT LOWER(t.maker) as address
                    FROM trades t
                    JOIN markets m ON (t.token_id = m.yes_token_id OR t.token_id = m.no_token_id)
                    WHERE m.slug = ?
                    UNION
                    SELECT DISTINCT LOWER(t.taker) as address
                    FROM trades t
                    JOIN markets m ON (t.token_id = m.yes_token_id OR t.token_id = m.no_token_id)
                    WHERE m.slug = ?
                    LIMIT 100
                """, (market_slug, market_slug))
            else:
                cursor.execute("""
                    SELECT DISTINCT LOWER(maker) as address FROM trades
                    UNION
                    SELECT DISTINCT LOWER(taker) as address FROM trades
                    LIMIT 200
                """)
            
            addresses = [row['address'] for row in cursor.fetchall()]
            
            # 计算每个地址的盈亏
            leaderboard = []
            for address in addresses:
                if not address or address == '0x0000000000000000000000000000000000000000':
                    continue
                
                try:
                    portfolio = self.calculate_portfolio_pnl(address)
                    leaderboard.append({
                        'address': address,
                        'total_pnl': float(portfolio.total_pnl),
                        'total_positions': portfolio.total_positions,
                        'winning_positions': portfolio.winning_positions,
                        'losing_positions': portfolio.losing_positions,
                        'pnl_percentage': float(portfolio.pnl_percentage)
                    })
                except Exception as e:
                    logger.debug(f"计算 {address} 盈亏失败: {e}")
                    continue
            
            # 按盈亏排序
            leaderboard.sort(key=lambda x: x['total_pnl'], reverse=True)
            
            return leaderboard[:limit]
            
        finally:
            conn.close()


# 全局实例
_pnl_calculator: Optional[PnLCalculator] = None


def get_pnl_calculator() -> PnLCalculator:
    """获取全局 PnL 计算器"""
    global _pnl_calculator
    if _pnl_calculator is None:
        _pnl_calculator = PnLCalculator()
    return _pnl_calculator
