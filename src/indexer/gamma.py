"""
Gamma API集成
"""
import requests
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class GammaAPIClient:
    """Gamma API客户端"""
    
    def __init__(self, base_url: str = "https://gamma-api.polymarket.com"):
        self.base_url = base_url
    
    def fetch_event(self, slug: str) -> Optional[Dict]:
        """获取事件信息"""
        try:
            url = f"{self.base_url}/events/{slug}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取事件失败: {e}")
            return None
    
    def fetch_market(self, slug: str) -> Optional[Dict]:
        """获取市场信息"""
        try:
            url = f"{self.base_url}/markets/{slug}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取市场失败: {e}")
            return None
    
    def fetch_event_markets(self, event_slug: str) -> List[Dict]:
        """获取事件下的所有市场"""
        try:
            url = f"{self.base_url}/events/{event_slug}/markets"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取事件市场列表失败: {e}")
            return []
