"""
数据库模块
"""
from .schema import get_connection, init_db, get_last_indexed_block, set_last_indexed_block

__all__ = ['get_connection', 'init_db', 'get_last_indexed_block', 'set_last_indexed_block']
