# src/database.py
# 简化版 SQLite 数据库缓存

import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

from src.config import DATABASE_ENABLE, DATABASE_PATH, CACHE_HOURS
from src.logger import logger

class DatabaseCache:
    _instance = None
    _conn = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def init(self):
        if not DATABASE_ENABLE:
            return
        try:
            DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(DATABASE_PATH))
            await self._create_tables()
            logger.info(f"✅ 数据库缓存已启用: {DATABASE_PATH}")
        except Exception as e:
            logger.warning(f"⚠️ 数据库初始化失败: {e}")
            self._conn = None
    
    async def _create_tables(self):
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS channel_cache (
                channel_key TEXT PRIMARY KEY,
                name TEXT,
                url TEXT,
                latency INTEGER,
                video_codec TEXT,
                updated_at TIMESTAMP
            )
        ''')
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS raw_cache (
                url TEXT PRIMARY KEY,
                content TEXT,
                updated_at TIMESTAMP
            )
        ''')
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await self._conn.commit()
    
    async def get_raw_source(self, url: str) -> Optional[str]:
        if not self._conn:
            return None
        try:
            cursor = await self._conn.execute(
                'SELECT content, updated_at FROM raw_cache WHERE url = ?',
                (url,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                content, updated_at = row
                if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=CACHE_HOURS):
                    return content
        except Exception:
            pass
        return None
    
    async def set_raw_source(self, url: str, content: str):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                'INSERT OR REPLACE INTO raw_cache (url, content, updated_at) VALUES (?, ?, ?)',
                (url, content, datetime.now().isoformat())
            )
            await self._conn.commit()
        except Exception:
            pass
    
    async def get_speed_result(self, channel_key: str) -> Optional[Dict]:
        if not self._conn:
            return None
        try:
            cursor = await self._conn.execute(
                'SELECT name, url, latency, video_codec, updated_at FROM channel_cache WHERE channel_key = ?',
                (channel_key,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                name, url, latency, video_codec, updated_at = row
                if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=CACHE_HOURS):
                    return {
                        "name": name,
                        "url": url,
                        "latency": latency,
                        "video_codec": video_codec
                    }
        except Exception:
            pass
        return None
    
    async def set_speed_result(self, channel_key: str, channel_data: Dict):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                '''INSERT OR REPLACE INTO channel_cache 
                   (channel_key, name, url, latency, video_codec, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    channel_key,
                    channel_data.get("name", ""),
                    channel_data.get("url", ""),
                    channel_data.get("latency", 9999),
                    channel_data.get("video_codec", ""),
                    datetime.now().isoformat()
                )
            )
            await self._conn.commit()
        except Exception:
            pass
    
    async def save_speed_results(self, channels: List[Dict]):
        for ch in channels:
            key = f"{ch['name']}|{ch['url']}"
            await self.set_speed_result(key, ch)
    
    async def get_last_update_time(self) -> Optional[int]:
        if not self._conn:
            return None
        cursor = await self._conn.execute("SELECT value FROM metadata WHERE key = 'last_update'")
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            return int(row[0])
        return None
    
    async def set_last_update_time(self, timestamp: int = None):
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        if not self._conn:
            return
        await self._conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("last_update", str(timestamp))
        )
        await self._conn.commit()
    
    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

_db_cache = None

async def get_db_cache() -> DatabaseCache:
    global _db_cache
    if _db_cache is None:
        _db_cache = DatabaseCache()
        await _db_cache.init()
    return _db_cache

def channel_key(name: str, url: str) -> str:
    import hashlib
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()
