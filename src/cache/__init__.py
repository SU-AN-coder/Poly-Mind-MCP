"""
缓存模块
"""
from .redis_cache import CacheManager, cache_decorator, get_cache

__all__ = ['CacheManager', 'cache_decorator', 'get_cache']
