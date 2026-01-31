"""
Redis 缓存管理器
支持热点数据缓存，减少数据库查询压力
"""
import os
import json
import hashlib
import logging
from typing import Any, Optional, Callable, Union
from functools import wraps
from datetime import datetime, timedelta
import pickle

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Redis 缓存管理器
    
    支持:
    - 键值缓存
    - 过期时间
    - 缓存失效
    - 统计信息
    - 降级到内存缓存（Redis不可用时）
    """
    
    def __init__(
        self,
        redis_url: str = None,
        default_ttl: int = 300,  # 默认5分钟
        prefix: str = "polymind:"
    ):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.default_ttl = default_ttl
        self.prefix = prefix
        self.redis_client = None
        self.fallback_cache = {}  # 内存降级缓存
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "fallback_mode": False
        }
        
        self._connect()
    
    def _connect(self):
        """连接 Redis"""
        try:
            import redis
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # 我们自己处理编解码
                socket_connect_timeout=2,
                socket_timeout=2
            )
            # 测试连接
            self.redis_client.ping()
            logger.info(f"✓ Redis 连接成功: {self.redis_url}")
            self.stats["fallback_mode"] = False
        except Exception as e:
            logger.warning(f"Redis 连接失败，使用内存缓存: {e}")
            self.redis_client = None
            self.stats["fallback_mode"] = True
    
    def _make_key(self, key: str) -> str:
        """生成带前缀的缓存键"""
        return f"{self.prefix}{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """序列化值"""
        try:
            # 尝试 JSON 序列化（更通用）
            return json.dumps(value, ensure_ascii=False, default=str).encode('utf-8')
        except (TypeError, ValueError):
            # 降级到 pickle
            return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> Any:
        """反序列化值"""
        if data is None:
            return None
        try:
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return pickle.loads(data)
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        full_key = self._make_key(key)
        
        try:
            if self.redis_client:
                data = self.redis_client.get(full_key)
                if data:
                    self.stats["hits"] += 1
                    return self._deserialize(data)
                self.stats["misses"] += 1
                return None
            else:
                # 内存缓存
                item = self.fallback_cache.get(full_key)
                if item:
                    expires_at, value = item
                    if expires_at > datetime.now():
                        self.stats["hits"] += 1
                        return value
                    else:
                        del self.fallback_cache[full_key]
                self.stats["misses"] += 1
                return None
        except Exception as e:
            logger.error(f"缓存获取失败: {e}")
            self.stats["errors"] += 1
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: int = None
    ) -> bool:
        """设置缓存值"""
        full_key = self._make_key(key)
        ttl = ttl or self.default_ttl
        
        try:
            if self.redis_client:
                data = self._serialize(value)
                self.redis_client.setex(full_key, ttl, data)
                return True
            else:
                # 内存缓存
                expires_at = datetime.now() + timedelta(seconds=ttl)
                self.fallback_cache[full_key] = (expires_at, value)
                # 限制内存缓存大小
                if len(self.fallback_cache) > 10000:
                    self._cleanup_fallback()
                return True
        except Exception as e:
            logger.error(f"缓存设置失败: {e}")
            self.stats["errors"] += 1
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        full_key = self._make_key(key)
        
        try:
            if self.redis_client:
                self.redis_client.delete(full_key)
            else:
                self.fallback_cache.pop(full_key, None)
            return True
        except Exception as e:
            logger.error(f"缓存删除失败: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """按模式删除缓存"""
        full_pattern = self._make_key(pattern)
        count = 0
        
        try:
            if self.redis_client:
                cursor = 0
                while True:
                    cursor, keys = self.redis_client.scan(
                        cursor=cursor,
                        match=full_pattern,
                        count=100
                    )
                    if keys:
                        self.redis_client.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            else:
                # 内存缓存
                import fnmatch
                keys_to_delete = [
                    k for k in self.fallback_cache.keys()
                    if fnmatch.fnmatch(k, full_pattern)
                ]
                for k in keys_to_delete:
                    del self.fallback_cache[k]
                count = len(keys_to_delete)
            
            return count
        except Exception as e:
            logger.error(f"批量删除缓存失败: {e}")
            return 0
    
    def _cleanup_fallback(self):
        """清理过期的内存缓存"""
        now = datetime.now()
        expired = [
            k for k, (expires_at, _) in self.fallback_cache.items()
            if expires_at <= now
        ]
        for k in expired:
            del self.fallback_cache[k]
        
        # 如果还是太多，删除最老的
        if len(self.fallback_cache) > 8000:
            items = sorted(
                self.fallback_cache.items(),
                key=lambda x: x[1][0]
            )
            for k, _ in items[:2000]:
                del self.fallback_cache[k]
    
    def get_stats(self) -> dict:
        """获取缓存统计"""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0
        
        stats = {
            **self.stats,
            "hit_rate": f"{hit_rate:.2%}",
            "total_requests": total,
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info("memory")
                stats["redis_memory"] = info.get("used_memory_human", "N/A")
                stats["redis_keys"] = self.redis_client.dbsize()
            except:
                pass
        else:
            stats["fallback_cache_size"] = len(self.fallback_cache)
        
        return stats
    
    def flush(self) -> bool:
        """清空所有缓存"""
        try:
            if self.redis_client:
                # 只删除我们前缀的键
                self.delete_pattern("*")
            else:
                self.fallback_cache.clear()
            return True
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return False


# 全局缓存实例
_cache_manager: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """获取全局缓存实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cache_decorator(
    ttl: int = 300,
    key_prefix: str = "",
    key_builder: Callable = None
):
    """
    缓存装饰器
    
    用法:
        @cache_decorator(ttl=60, key_prefix="market:")
        def get_market_info(slug: str):
            ...
    
    Args:
        ttl: 过期时间（秒）
        key_prefix: 缓存键前缀
        key_builder: 自定义键生成函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # 生成缓存键
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # 默认：函数名 + 参数哈希
                key_parts = [key_prefix or func.__name__]
                if args:
                    key_parts.append(str(args))
                if kwargs:
                    key_parts.append(str(sorted(kwargs.items())))
                raw_key = ":".join(key_parts)
                cache_key = hashlib.md5(raw_key.encode()).hexdigest()[:16]
                cache_key = f"{key_prefix or func.__name__}:{cache_key}"
            
            # 尝试从缓存获取
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"缓存命中: {cache_key}")
                return cached
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            if result is not None:
                cache.set(cache_key, result, ttl)
                logger.debug(f"缓存设置: {cache_key}")
            
            return result
        
        return wrapper
    return decorator


# 常用缓存键生成器
def market_key_builder(slug: str = None, **kwargs) -> str:
    """市场缓存键"""
    return f"market:{slug}"


def trader_key_builder(address: str = None, **kwargs) -> str:
    """交易者缓存键"""
    return f"trader:{address.lower() if address else 'unknown'}"


def stats_key_builder(**kwargs) -> str:
    """统计缓存键"""
    return "stats:global"
