"""
PolyMind MCP API 服务器
"""
import os
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

from src.db.schema import get_connection
from src.mcp.tools import PolymarketTools
from .websocket_manager import ws_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

DB_PATH = os.getenv("DB_PATH", "data/polymarket.db")
tools = PolymarketTools()

LARGE_TRADE_THRESHOLD = 1000


def get_db():
    """获取数据库连接"""
    return get_connection(DB_PATH)


def safe_float(val, default=0.0):
    """安全转换为浮点数"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_trade_amount(maker_amount, taker_amount):
    """解析交易金额 - 金额存储为微单位（1e6）"""
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


def calculate_price(maker_amount, taker_amount, stored_price):
    """计算价格 - 如果存储的价格无效，尝试计算"""
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


@app.route('/health', methods=['GET'])
def health_check():
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({
            "status": "healthy", 
            "timestamp": datetime.now().isoformat(),
            "websocket": ws_manager.get_stats()
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(DISTINCT maker) FROM trades")
        unique_traders = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT SUM(
                CASE 
                    WHEN CAST(maker_amount AS REAL) < CAST(taker_amount AS REAL) 
                    THEN CAST(maker_amount AS REAL)
                    ELSE CAST(taker_amount AS REAL)
                END
            ) FROM trades
        """)
        total_volume_raw = cursor.fetchone()[0] or 0
        if total_volume_raw > 1e9:
            total_volume = total_volume_raw / 1e6
        else:
            total_volume = total_volume_raw
        
        cursor.execute("SELECT COUNT(*) FROM markets")
        total_markets = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT COUNT(*) FROM trades 
            WHERE (
                CASE 
                    WHEN CAST(maker_amount AS REAL) < CAST(taker_amount AS REAL) 
                    THEN CAST(maker_amount AS REAL) / 1e6
                    ELSE CAST(taker_amount AS REAL) / 1e6
                END
            ) >= ?
        """, (LARGE_TRADE_THRESHOLD,))
        large_trades_count = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            "total_trades": total_trades,
            "unique_traders": unique_traders,
            "total_volume": round(total_volume, 2),
            "total_markets": total_markets,
            "large_trades_count": large_trades_count,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/trades/recent', methods=['GET'])
def get_recent_trades():
    """获取最近交易"""
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # 直接查询，不依赖市场表关联
        cursor.execute("""
            SELECT 
                t.tx_hash, t.maker, t.taker, t.side, t.outcome,
                t.price, t.maker_amount, t.taker_amount, t.timestamp
            FROM trades t
            ORDER BY t.id DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        for row in rows:
            tx_hash, maker, taker, side, outcome, price, maker_amt, taker_amt, timestamp = row
            
            # 计算USDC金额
            maker_amt = safe_float(maker_amt)
            taker_amt = safe_float(taker_amt)
            
            if maker_amt < 1e6 and taker_amt > 1e6:
                size = maker_amt
            elif taker_amt < 1e6 and maker_amt > 1e6:
                size = taker_amt
            else:
                smaller = min(maker_amt, taker_amt)
                size = smaller / 1e6 if smaller > 1e6 else smaller
            
            # 计算价格
            price_val = safe_float(price)
            if price_val <= 0.001 or price_val >= 1.0:
                if maker_amt > 0 and taker_amt > 0:
                    if maker_amt < taker_amt:
                        price_val = maker_amt / taker_amt
                    else:
                        price_val = taker_amt / maker_amt
                    if price_val < 0.001 or price_val > 1.0:
                        price_val = 0.5
                else:
                    price_val = 0.5
            
            trades.append({
                "tx_hash": tx_hash or "",
                "maker": maker or "",
                "taker": taker or "",
                "side": side or "BUY",
                "outcome": outcome or "",
                "price": round(price_val, 4),
                "size": round(size, 2),
                "timestamp": timestamp or "",
                "market_slug": "unknown",
                "market_title": "Unknown Market",
                "is_large": size >= LARGE_TRADE_THRESHOLD
            })
        
        return jsonify({"trades": trades, "count": len(trades)})
    except Exception as e:
        logger.error(f"获取最近交易失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"trades": [], "error": str(e), "count": 0})


@app.route('/trades/large', methods=['GET'])
def get_large_trades():
    """获取大单交易"""
    limit = request.args.get('limit', 50, type=int)
    min_size = request.args.get('min_size', LARGE_TRADE_THRESHOLD, type=float)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                t.tx_hash, t.maker, t.taker, t.side, t.outcome,
                t.price, t.maker_amount, t.taker_amount, t.timestamp
            FROM trades t
            ORDER BY 
                CASE 
                    WHEN CAST(t.maker_amount AS REAL) < CAST(t.taker_amount AS REAL) 
                    THEN CAST(t.maker_amount AS REAL)
                    ELSE CAST(t.taker_amount AS REAL)
                END DESC
            LIMIT 500
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        total_volume = buy_volume = sell_volume = 0
        
        for row in rows:
            maker_amt = safe_float(row[6])
            taker_amt = safe_float(row[7])
            size = parse_trade_amount(maker_amt, taker_amt)
            
            if size < min_size:
                continue
            
            price = calculate_price(maker_amt, taker_amt, row[5])
            side = row[3] or "BUY"
            
            total_volume += size
            if side == 'BUY':
                buy_volume += size
            else:
                sell_volume += size
            
            trades.append({
                "tx_hash": row[0],
                "maker": row[1],
                "taker": row[2],
                "side": side,
                "outcome": row[4],
                "price": round(price, 4),
                "size": round(size, 2),
                "timestamp": row[8],
                "market_slug": "unknown",
                "market_title": "Unknown Market"
            })
            
            if len(trades) >= limit:
                break
        
        return jsonify({
            "trades": trades,
            "count": len(trades),
            "min_size": min_size,
            "summary": {
                "total_volume": round(total_volume, 2),
                "buy_volume": round(buy_volume, 2),
                "sell_volume": round(sell_volume, 2),
                "buy_ratio": round(buy_volume / total_volume * 100, 1) if total_volume > 0 else 50
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取大单交易失败: {e}")
        return jsonify({"trades": [], "error": str(e)}), 500


@app.route('/sentiment', methods=['GET'])
def get_market_sentiment():
    """获取市场情绪指数"""
    market_slug = request.args.get('market', None)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT side, maker_amount, taker_amount FROM trades")
        
        rows = cursor.fetchall()
        conn.close()
        
        buy_count = sell_count = 0
        buy_volume = sell_volume = 0.0
        
        for row in rows:
            side = row[0] or "BUY"
            amount = parse_trade_amount(row[1], row[2])
            
            if side == 'BUY':
                buy_count += 1
                buy_volume += amount
            else:
                sell_count += 1
                sell_volume += amount
        
        total_count = buy_count + sell_count
        total_volume = buy_volume + sell_volume
        
        sentiment_by_count = buy_count / total_count * 100 if total_count > 0 else 50
        sentiment_by_volume = buy_volume / total_volume * 100 if total_volume > 0 else 50
        overall_sentiment = sentiment_by_count * 0.3 + sentiment_by_volume * 0.7
        
        if overall_sentiment >= 70:
            sentiment_label = "极度乐观"
        elif overall_sentiment >= 60:
            sentiment_label = "乐观"
        elif overall_sentiment >= 40:
            sentiment_label = "中性"
        elif overall_sentiment >= 30:
            sentiment_label = "悲观"
        else:
            sentiment_label = "极度悲观"
        
        return jsonify({
            "market": market_slug or "全市场",
            "sentiment_index": round(overall_sentiment, 1),
            "sentiment_label": sentiment_label,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "buy_volume": round(buy_volume, 2),
            "sell_volume": round(sell_volume, 2),
            "buy_ratio_count": round(sentiment_by_count, 1),
            "buy_ratio_volume": round(sentiment_by_volume, 1),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取市场情绪失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/market/<slug>/price-history', methods=['GET'])
def get_price_history(slug: str):
    limit = request.args.get('limit', 100, type=int)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.price, t.timestamp, t.side, t.outcome, t.maker_amount, t.taker_amount
            FROM trades t
            LEFT JOIN markets m1 ON t.token_id = m1.yes_token_id
            LEFT JOIN markets m2 ON t.token_id = m2.no_token_id
            WHERE m1.slug = ? OR m2.slug = ?
            ORDER BY t.id DESC
            LIMIT ?
        """, (slug, slug, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        rows = list(reversed(rows))
        
        history = []
        for row in rows:
            price = calculate_price(row[4], row[5], row[0])
            size = parse_trade_amount(row[4], row[5])
            history.append({
                "price": round(price, 4),
                "timestamp": row[1],
                "side": row[2] or "BUY",
                "outcome": row[3],
                "size": round(size, 2)
            })
        
        return jsonify({
            "market_slug": slug,
            "history": history,
            "count": len(history),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取价格历史失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/ws/stats', methods=['GET'])
def get_ws_stats():
    return jsonify(ws_manager.get_stats())


@app.route('/ws/subscribe', methods=['POST'])
def ws_subscribe():
    data = request.get_json() or {}
    client_id = data.get('client_id', 'test-client')
    channel = data.get('channel', 'trades')
    target = data.get('target')
    
    if client_id not in ws_manager.clients:
        ws_manager.register_client(client_id)
    
    success = ws_manager.subscribe(client_id, channel, target)
    return jsonify({"success": success, "client_id": client_id, "channel": channel, "target": target})


@app.route('/hot', methods=['GET'])
def get_hot_markets():
    limit = request.args.get('limit', 10, type=int)
    sort_by = request.args.get('sort', 'volume')
    try:
        result = tools.execute_tool("get_hot_markets", {"limit": limit, "sort_by": sort_by})
        return jsonify(result)
    except Exception as e:
        return jsonify({"markets": [], "error": str(e)}), 500


@app.route('/smart-money', methods=['GET'])
def get_smart_money():
    min_win_rate = request.args.get('min_win_rate', 50, type=float)
    market_slug = request.args.get('market', None)
    try:
        result = tools.execute_tool("get_smart_money_activity", {"market_slug": market_slug, "min_win_rate": min_win_rate})
        return jsonify(result)
    except Exception as e:
        return jsonify({"smart_money_addresses": [], "error": str(e)}), 500


@app.route('/trader/<address>', methods=['GET'])
def get_trader_detail(address: str):
    try:
        result = tools.execute_tool("analyze_trader", {"address": address})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/arbitrage', methods=['GET'])
def get_arbitrage():
    limit = request.args.get('limit', 20, type=int)
    try:
        result = tools.execute_tool("find_arbitrage", {"limit": limit})
        return jsonify(result)
    except Exception as e:
        return jsonify({"opportunities": [], "error": str(e)}), 500


@app.route('/markets/search', methods=['GET'])
def search_markets():
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    if not query:
        return jsonify({"results": [], "error": "缺少搜索关键词"}), 400
    try:
        result = tools.execute_tool("search_markets", {"query": query, "limit": limit})
        return jsonify(result)
    except Exception as e:
        return jsonify({"results": [], "error": str(e)}), 500


@app.route('/market/<slug>', methods=['GET'])
def get_market_info(slug: str):
    try:
        result = tools.execute_tool("get_market_info", {"market_slug": slug})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/nl-query', methods=['POST'])
def natural_language_query():
    try:
        data = request.get_json() or {}
        query = data.get('query', '')
        if not query:
            return jsonify({"error": "缺少查询内容"}), 400
        
        query_lower = query.lower()
        
        if '大单' in query or 'large' in query_lower:
            result = get_large_trades().get_json()
            result['type'] = 'large_trades'
        elif '情绪' in query or 'sentiment' in query_lower:
            result = get_market_sentiment().get_json()
            result['type'] = 'sentiment'
        elif '搜索' in query or 'search' in query_lower:
            keywords = query.replace('搜索', '').replace('关于', '').replace('的市场', '').strip()
            result = tools.execute_tool("search_markets", {"query": keywords, "limit": 10})
            result['type'] = 'search'
        elif '套利' in query or 'arbitrage' in query_lower:
            result = tools.execute_tool("find_arbitrage", {"limit": 20})
            result['type'] = 'arbitrage'
        elif '热门' in query or 'hot' in query_lower:
            result = tools.execute_tool("get_hot_markets", {"limit": 10, "sort_by": "volume"})
            result['type'] = 'hot_markets'
        elif '聪明钱' in query or 'smart money' in query_lower:
            result = tools.execute_tool("get_smart_money_activity", {"min_win_rate": 50})
            result['type'] = 'smart_money'
        else:
            result = tools.execute_tool("search_markets", {"query": query, "limit": 5})
            result['type'] = 'search_fallback'
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/advice/<slug>', methods=['GET'])
def get_trading_advice(slug: str):
    intent = request.args.get('intent', None)
    try:
        result = tools.execute_tool("get_trading_advice", {"market_slug": slug, "user_intent": intent})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/alerts/<slug>', methods=['GET'])
def get_smart_alerts(slug: str):
    try:
        result = tools.execute_tool("get_smart_alerts", {"watched_market": slug})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/relationship', methods=['GET'])
def analyze_relationship():
    market_a = request.args.get('a', '')
    market_b = request.args.get('b', '')
    if not market_a or not market_b:
        return jsonify({"error": "需要两个市场参数 a 和 b"}), 400
    try:
        result = tools.execute_tool("analyze_market_relationship", {"market_a": market_a, "market_b": market_b})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api-docs', methods=['GET'])
def api_docs():
    return jsonify({
        "openapi": "3.0.0",
        "info": {"title": "PolyMind MCP API", "version": "2.0.0"},
        "paths": {
            "/health": {"get": {"summary": "健康检查"}},
            "/stats": {"get": {"summary": "统计数据"}},
            "/trades/recent": {"get": {"summary": "最近交易"}},
            "/trades/large": {"get": {"summary": "大单交易"}},
            "/sentiment": {"get": {"summary": "市场情绪"}},
            "/hot": {"get": {"summary": "热门市场"}},
            "/smart-money": {"get": {"summary": "聪明钱"}},
            "/arbitrage": {"get": {"summary": "套利机会"}},
            "/markets/search": {"get": {"summary": "搜索市场"}},
        }
    })


def run_server(host: str = '0.0.0.0', port: int = 8888, debug: bool = False):
    logger.info(f"启动 API 服务器: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    run_server(debug=True)
