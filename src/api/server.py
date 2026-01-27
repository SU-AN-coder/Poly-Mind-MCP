"""
阶段二：REST API服务器
用于查询已索引的Polymarket交易数据
"""
import os
import sys
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.schema import get_connection, init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="PolyMind 交易查询API",
    description="Polymarket交易数据查询服务",
    version="1.0.0"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库路径
DB_PATH = os.getenv("DB_PATH", "polymarket.db")


# 数据模型
class Trade(BaseModel):
    """交易数据"""
    id: int
    tx_hash: str
    event_type: str
    maker: str
    taker: str
    asset_yes: str
    asset_no: str
    size: float
    price: float
    block_number: int
    timestamp: str
    market_slug: Optional[str] = None
    outcome: Optional[str] = None


class Market(BaseModel):
    """市场数据"""
    id: int
    market_slug: str
    condition_id: str
    yes_token_id: str
    no_token_id: str
    created_at: str


class TradeListResponse(BaseModel):
    """交易列表响应"""
    total: int
    limit: int
    offset: int
    trades: List[Trade]


class MarketResponse(BaseModel):
    """市场信息响应"""
    market: Market
    stats: Dict[str, Any]


# 辅助函数
def get_market_by_slug(market_slug: str) -> Optional[Dict]:
    """通过slug获取市场"""
    try:
        conn = get_connection(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, market_slug, condition_id, yes_token_id, no_token_id, created_at
            FROM markets
            WHERE market_slug = ?
            LIMIT 1
        """, (market_slug,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'market_slug': row[1],
                'condition_id': row[2],
                'yes_token_id': row[3],
                'no_token_id': row[4],
                'created_at': row[5]
            }
        return None
    except Exception as e:
        logger.error(f"获取市场失败: {e}")
        return None


def get_market_trades(market_slug: str, limit: int, offset: int) -> Dict:
    """获取市场交易"""
    try:
        conn = get_connection(DB_PATH)
        cursor = conn.cursor()
        
        # 获取总数
        cursor.execute("""
            SELECT COUNT(*) FROM events
            WHERE (SELECT market_slug FROM markets WHERE market_slug = ?) IS NOT NULL
        """, (market_slug,))
        total = cursor.fetchone()[0]
        
        # 获取交易
        cursor.execute("""
            SELECT e.id, e.tx_hash, e.event_type, e.maker, e.taker,
                   e.asset_yes, e.asset_no, e.size, e.price,
                   e.block_number, e.timestamp, m.market_slug, 
                   CASE 
                       WHEN e.asset_yes > 0 THEN 'YES'
                       WHEN e.asset_no > 0 THEN 'NO'
                       ELSE NULL
                   END as outcome
            FROM events e
            LEFT JOIN markets m ON (e.asset_yes = m.yes_token_id OR e.asset_no = m.no_token_id)
            WHERE m.market_slug = ?
            ORDER BY e.block_number DESC, e.id DESC
            LIMIT ? OFFSET ?
        """, (market_slug, limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        for row in rows:
            trades.append({
                'id': row[0],
                'tx_hash': row[1],
                'event_type': row[2],
                'maker': row[3],
                'taker': row[4],
                'asset_yes': row[5],
                'asset_no': row[6],
                'size': row[7],
                'price': row[8],
                'block_number': row[9],
                'timestamp': row[10],
                'market_slug': row[11],
                'outcome': row[12]
            })
        
        return {
            'total': total,
            'limit': limit,
            'offset': offset,
            'trades': trades
        }
    except Exception as e:
        logger.error(f"获取市场交易失败: {e}")
        return {
            'total': 0,
            'limit': limit,
            'offset': offset,
            'trades': []
        }


def get_token_trades(token_id: str, limit: int, offset: int) -> Dict:
    """通过TokenId获取交易"""
    try:
        conn = get_connection(DB_PATH)
        cursor = conn.cursor()
        
        # 获取总数
        cursor.execute("""
            SELECT COUNT(*) FROM events
            WHERE asset_yes = ? OR asset_no = ?
        """, (token_id, token_id))
        total = cursor.fetchone()[0]
        
        # 获取交易
        cursor.execute("""
            SELECT id, tx_hash, event_type, maker, taker,
                   asset_yes, asset_no, size, price,
                   block_number, timestamp
            FROM events
            WHERE asset_yes = ? OR asset_no = ?
            ORDER BY block_number DESC, id DESC
            LIMIT ? OFFSET ?
        """, (token_id, token_id, limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        for row in rows:
            trades.append({
                'id': row[0],
                'tx_hash': row[1],
                'event_type': row[2],
                'maker': row[3],
                'taker': row[4],
                'asset_yes': row[5],
                'asset_no': row[6],
                'size': row[7],
                'price': row[8],
                'block_number': row[9],
                'timestamp': row[10]
            })
        
        return {
            'total': total,
            'limit': limit,
            'offset': offset,
            'trades': trades
        }
    except Exception as e:
        logger.error(f"获取TokenId交易失败: {e}")
        return {
            'total': 0,
            'limit': limit,
            'offset': offset,
            'trades': []
        }


def get_market_stats(market_slug: str) -> Dict:
    """获取市场统计信息"""
    try:
        conn = get_connection(DB_PATH)
        cursor = conn.cursor()
        
        # 交易统计
        cursor.execute("""
            SELECT COUNT(*) as trade_count, 
                   AVG(price) as avg_price,
                   MIN(price) as min_price,
                   MAX(price) as max_price,
                   SUM(size) as total_volume
            FROM events e
            LEFT JOIN markets m ON (e.asset_yes = m.yes_token_id OR e.asset_no = m.no_token_id)
            WHERE m.market_slug = ?
        """, (market_slug,))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'trade_count': row[0] or 0,
            'avg_price': float(row[1]) if row[1] else 0.0,
            'min_price': float(row[2]) if row[2] else 0.0,
            'max_price': float(row[3]) if row[3] else 0.0,
            'total_volume': float(row[4]) if row[4] else 0.0
        }
    except Exception as e:
        logger.error(f"获取市场统计失败: {e}")
        return {
            'trade_count': 0,
            'avg_price': 0.0,
            'min_price': 0.0,
            'max_price': 0.0,
            'total_volume': 0.0
        }


# API端点

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查端点 - 返回系统状态和统计信息"""
    try:
        conn = get_connection(DB_PATH)
        cursor = conn.cursor()
        
        # 获取市场数量
        cursor.execute("SELECT COUNT(*) FROM markets")
        markets_count = cursor.fetchone()[0]
        
        # 获取交易数量
        cursor.execute("SELECT COUNT(*) FROM events")
        trades_count = cursor.fetchone()[0]
        
        # 获取最新区块号
        cursor.execute("SELECT MAX(block_number) FROM events")
        block_number = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "status": "ok",
            "service": "PolyMind API",
            "markets_count": markets_count,
            "trades_count": trades_count,
            "block_number": block_number,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "error",
            "service": "PolyMind API",
            "error": str(e)
        }


@app.get("/markets/{market_slug}")
async def get_market(market_slug: str = Path(..., description="市场slug")) -> Dict[str, Any]:
    """
    获取市场信息和统计数据
    
    Args:
        market_slug: 市场slug (例: 'will-there-be-another-us-recession')
        
    Returns:
        市场信息和统计数据
    """
    logger.info(f"查询市场: {market_slug}")
    
    market = get_market_by_slug(market_slug)
    if not market:
        raise HTTPException(status_code=404, detail=f"市场未找到: {market_slug}")
    
    stats = get_market_stats(market_slug)
    
    return {
        "market": market,
        "stats": stats
    }


@app.get("/markets/{market_slug}/trades")
async def get_market_trades_endpoint(
    market_slug: str = Path(..., description="市场slug"),
    limit: int = Query(100, ge=1, le=1000, description="返回结果数量"),
    offset: int = Query(0, ge=0, description="分页偏移量")
) -> TradeListResponse:
    """
    获取市场交易记录
    
    Args:
        market_slug: 市场slug
        limit: 返回结果数量 (1-1000)
        offset: 分页偏移量
        
    Returns:
        交易列表
    """
    logger.info(f"查询市场交易: {market_slug}, limit={limit}, offset={offset}")
    
    market = get_market_by_slug(market_slug)
    if not market:
        raise HTTPException(status_code=404, detail=f"市场未找到: {market_slug}")
    
    result = get_market_trades(market_slug, limit, offset)
    
    return TradeListResponse(
        total=result['total'],
        limit=result['limit'],
        offset=result['offset'],
        trades=[Trade(**trade) for trade in result['trades']]
    )


@app.get("/tokens/{token_id}/trades")
async def get_token_trades_endpoint(
    token_id: str = Path(..., description="ERC-1155 Token ID"),
    limit: int = Query(100, ge=1, le=1000, description="返回结果数量"),
    offset: int = Query(0, ge=0, description="分页偏移量")
) -> TradeListResponse:
    """
    通过TokenId获取交易记录
    
    Args:
        token_id: ERC-1155 Token ID (十六进制)
        limit: 返回结果数量 (1-1000)
        offset: 分页偏移量
        
    Returns:
        交易列表
    """
    logger.info(f"查询TokenId交易: {token_id[:20]}..., limit={limit}, offset={offset}")
    
    result = get_token_trades(token_id, limit, offset)
    
    if result['total'] == 0:
        raise HTTPException(status_code=404, detail=f"TokenId未找到交易: {token_id}")
    
    return TradeListResponse(
        total=result['total'],
        limit=result['limit'],
        offset=result['offset'],
        trades=[Trade(**trade) for trade in result['trades']]
    )


@app.get("/status")
async def get_status() -> Dict[str, Any]:
    """获取索引器状态"""
    try:
        conn = get_connection(DB_PATH)
        cursor = conn.cursor()
        
        # 获取同步状态
        cursor.execute("SELECT last_block, total_events, last_updated FROM sync_state LIMIT 1")
        sync_row = cursor.fetchone()
        
        # 获取统计
        cursor.execute("SELECT COUNT(*) FROM events")
        event_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM markets")
        market_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'last_block': sync_row[0] if sync_row else 0,
            'total_events': sync_row[1] if sync_row else 0,
            'last_updated': sync_row[2] if sync_row else None,
            'indexed_events': event_count,
            'indexed_markets': market_count
        }
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@app.get("/")
async def root() -> Dict[str, str]:
    """根端点 - API信息"""
    return {
        "name": "PolyMind交易查询API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


def main():
    """启动API服务器"""
    port = int(os.getenv("API_PORT", 8000))
    host = os.getenv("API_HOST", "0.0.0.0")
    
    logger.info(f"启动API服务器: {host}:{port}")
    logger.info(f"数据库路径: {DB_PATH}")
    logger.info("文档地址: http://localhost:8000/docs")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
