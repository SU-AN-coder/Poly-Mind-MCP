"""
数据库模块
"""
from .schema import get_connection, init_db

__all__ = ['get_connection', 'init_db']
