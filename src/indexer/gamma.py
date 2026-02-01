"""
Gamma API 客户端
用于获取 Polymarket 市场元数据
"""
import os
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime

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
    
    def fetch_active_markets(self, limit: int = 100) -> List[Dict]:
        """获取活跃市场（别名）"""
        return self.get_markets(limit=limit, active=True)
    
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
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from src.db.schema import get_connection
        
        conn = get_connection(db_path)
        cursor = conn.cursor()
        
        # 先检查表结构
        cursor.execute("PRAGMA table_info(markets)")
        columns = {row[1] for row in cursor.fetchall()}
        logger.info(f"Markets 表列: {columns}")
        
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
                    
                    condition_id = market.get("conditionId")
                    slug = market.get("slug")
                    
                    if not condition_id:
                        continue
                    
                    # 根据实际表结构插入数据
                    if "question" in columns:
                        # 新表结构
                        cursor.execute("""
                            INSERT OR REPLACE INTO markets 
                            (condition_id, slug, question, description, end_date, 
                             yes_token_id, no_token_id, volume, liquidity, 
                             yes_price, no_price, active, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            condition_id,
                            slug,
                            market.get("question", slug),
                            market.get("description", ""),
                            market.get("endDate"),
                            yes_token_id,
                            no_token_id,
                            float(market.get("volume", 0) or 0),
                            float(market.get("liquidity", 0) or 0),
                            yes_price,
                            no_price,
                            1 if market.get("active") else 0,
                            datetime.now().isoformat()
                        ))
                    else:
                        # 现有表结构 - 适配字段
                        # 检查有哪些列
                        if "title" in columns:
                            title_field = "title"
                        else:
                            title_field = None
                        
                        # 尝试使用简单的 INSERT OR REPLACE
                        if title_field:
                            cursor.execute(f"""
                                INSERT OR REPLACE INTO markets 
                                (condition_id, slug, {title_field}, yes_token_id, no_token_id, 
                                 volume, liquidity, yes_price, no_price, active, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                condition_id,
                                slug,
                                market.get("question", slug),
                                yes_token_id,
                                no_token_id,
                                float(market.get("volume", 0) or 0),
                                float(market.get("liquidity", 0) or 0),
                                yes_price,
                                no_price,
                                1 if market.get("active") else 0,
                                datetime.now().isoformat()
                            ))
                        else:
                            # 最简模式 - 只更新基本字段
                            cursor.execute("""
                                UPDATE markets SET 
                                    yes_token_id = ?,
                                    no_token_id = ?,
                                    volume = ?,
                                    liquidity = ?,
                                    yes_price = ?,
                                    no_price = ?,
                                    active = ?,
                                    updated_at = ?
                                WHERE condition_id = ? OR slug = ?
                            """, (
                                yes_token_id,
                                no_token_id,
                                float(market.get("volume", 0) or 0),
                                float(market.get("liquidity", 0) or 0),
                                yes_price,
                                no_price,
                                1 if market.get("active") else 0,
                                datetime.now().isoformat(),
                                condition_id,
                                slug
                            ))
                            
                            # 如果没有更新到任何行，尝试插入
                            if cursor.rowcount == 0:
                                # 获取所有列，动态构建 INSERT
                                col_list = list(columns)
                                values = {}
                                values['condition_id'] = condition_id
                                values['slug'] = slug
                                if 'yes_token_id' in columns:
                                    values['yes_token_id'] = yes_token_id
                                if 'no_token_id' in columns:
                                    values['no_token_id'] = no_token_id
                                if 'volume' in columns:
                                    values['volume'] = float(market.get("volume", 0) or 0)
                                if 'liquidity' in columns:
                                    values['liquidity'] = float(market.get("liquidity", 0) or 0)
                                if 'yes_price' in columns:
                                    values['yes_price'] = yes_price
                                if 'no_price' in columns:
                                    values['no_price'] = no_price
                                if 'active' in columns:
                                    values['active'] = 1 if market.get("active") else 0
                                if 'updated_at' in columns:
                                    values['updated_at'] = datetime.now().isoformat()
                                
                                cols = ", ".join(values.keys())
                                placeholders = ", ".join(["?" for _ in values])
                                cursor.execute(
                                    f"INSERT OR IGNORE INTO markets ({cols}) VALUES ({placeholders})",
                                    list(values.values())
                                )
                    
                    synced += 1
                    
                except Exception as e:
                    logger.error(f"保存市场 {market.get('slug', 'unknown')} 失败: {e}")
                    continue
            
            offset += batch_size
            if len(markets) < batch_size:
                break
        
        conn.commit()
        conn.close()
        logger.info(f"同步完成，共 {synced} 个市场")
        return synced


# 别名，保持兼容性
GammaAPIClient = GammaClient


# 便捷函数
def sync_markets(db_path: Optional[str] = None, limit: int = 500) -> int:
    """同步市场数据"""
    client = GammaClient()
    return client.sync_markets_to_db(db_path, limit)


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.db.schema import init_db
    init_db()
    count = sync_markets()
    print(f"同步了 {count} 个市场")
