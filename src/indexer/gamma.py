"""
Gamma API 客户端
用于获取 Polymarket 市场元数据
"""
import os
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime

from src.db.schema import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GAMMA_BASE_URL = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")


class GammaClient:
    """Gamma API 客户端"""
    
    def __init__(self, base_url: str = GAMMA_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "PolyMind-MCP/1.0"
        })
    
    def get_markets(self, limit: int = 100, offset: int = 0, active: bool = True) -> List[Dict]:
        """获取市场列表"""
        try:
            params = {"_limit": limit, "_offset": offset}
            if active:
                params["active"] = "true"
            
            response = self.session.get(f"{self.base_url}/markets", params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取市场列表失败: {e}")
            return []
    
    def get_market_by_slug(self, slug: str) -> Optional[Dict]:
        """通过 slug 获取市场"""
        try:
            response = self.session.get(
                f"{self.base_url}/markets",
                params={"slug": slug},
                timeout=15
            )
            response.raise_for_status()
            markets = response.json()
            return markets[0] if markets else None
        except Exception as e:
            logger.error(f"获取市场 {slug} 失败: {e}")
            return None
    
    def get_market_by_condition_id(self, condition_id: str) -> Optional[Dict]:
        """通过 condition_id 获取市场"""
        try:
            response = self.session.get(
                f"{self.base_url}/markets",
                params={"conditionId": condition_id},
                timeout=15
            )
            response.raise_for_status()
            markets = response.json()
            return markets[0] if markets else None
        except Exception as e:
            logger.error(f"获取市场 (condition_id={condition_id}) 失败: {e}")
            return None
    
    def sync_markets_to_db(self, db_path: Optional[str] = None, limit: int = 500) -> int:
        """同步市场数据到数据库"""
        conn = get_connection(db_path)
        cursor = conn.cursor()
        
        synced = 0
        offset = 0
        batch_size = 100
        
        while synced < limit:
            markets = self.get_markets(limit=batch_size, offset=offset, active=True)
            if not markets:
                break
            
            for market in markets:
                try:
                    # 提取 token 信息
                    tokens = market.get("tokens", [])
                    yes_token_id = no_token_id = None
                    yes_price = no_price = 0.5
                    
                    for token in tokens:
                        outcome = token.get("outcome", "").lower()
                        if outcome == "yes":
                            yes_token_id = token.get("token_id")
                            yes_price = float(token.get("price", 0.5))
                        elif outcome == "no":
                            no_token_id = token.get("token_id")
                            no_price = float(token.get("price", 0.5))
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO markets 
                        (condition_id, slug, question, description, end_date, 
                         yes_token_id, no_token_id, volume, liquidity, 
                         yes_price, no_price, active, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        market.get("conditionId"),
                        market.get("slug"),
                        market.get("question"),
                        market.get("description", ""),
                        market.get("endDate"),
                        yes_token_id,
                        no_token_id,
                        float(market.get("volume", 0)),
                        float(market.get("liquidity", 0)),
                        yes_price,
                        no_price,
                        1 if market.get("active") else 0,
                        datetime.now().isoformat()
                    ))
                    synced += 1
                except Exception as e:
                    logger.error(f"保存市场失败: {e}")
                    continue
            
            offset += batch_size
            if len(markets) < batch_size:
                break
        
        conn.commit()
        conn.close()
        logger.info(f"同步完成，共 {synced} 个市场")
        return synced


# 便捷函数
def sync_markets(db_path: Optional[str] = None, limit: int = 500) -> int:
    """同步市场数据"""
    client = GammaClient()
    return client.sync_markets_to_db(db_path, limit)


if __name__ == "__main__":
    from src.db.schema import init_db
    init_db()
    count = sync_markets()
    print(f"同步了 {count} 个市场")
