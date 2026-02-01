"""
索引器模块
"""
from .store import DataStore
from .gamma import GammaClient, sync_markets

# 别名兼容
GammaAPIClient = GammaClient

__all__ = ['DataStore', 'GammaClient', 'GammaAPIClient', 'sync_markets']

def get_indexer_class():
    """延迟导入避免循环依赖"""
    from .run import PolymarketIndexer
    return PolymarketIndexer

def get_run_indexer():
    """延迟导入避免循环依赖"""
    from .run import run_indexer
    return run_indexer
