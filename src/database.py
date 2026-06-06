# src/database.py
# 异步 SQLite 数据库缓存模块，统一管理原始源缓存和频道测速缓存

import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pathlib import Path

from src.config import DATABASE_ENABLE, DATABASE_PATH, DATABASE_TABLE, CACHE_RAW_HOURS, CACHE_SPEED_HOURS
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
            logger.info("⚙️ 数据库缓存未启用")
            return
        try:
            DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(DATABASE_PATH))
            await self._create_tables()
            logger.info(f"✅ 数据库缓存已启用: {DATABASE_PATH}")
        except Exception as e:
            logger.warning(f"⚠️ 数据库初始化失败: {e}，缓存功能禁用")
            self._conn = None
    
    async def _create_tables(self):
        await self._conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {DATABASE_TABLE}_raw (
                url TEXT PRIMARY KEY,
                content TEXT,
                etag TEXT,
                last_modified TEXT,
                updated_at TIMESTAMP
            )
        ''')
        await self._conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {DATABASE_TABLE}_speed (
                channel_key TEXT PRIMARY KEY,
                name TEXT,
                url TEXT,
                latency INTEGER,
                video_codec TEXT,
                ip_info TEXT,
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
    
    async def get_raw_source(self, url: str, max_age_hours: int = None) -> Optional[str]:
        if not self._conn:
            return None
        if max_age_hours is None:
            max_age_hours = CACHE_RAW_HOURS
        try:
            cursor = await self._conn.execute(
                f'SELECT content, updated_at FROM {DATABASE_TABLE}_raw WHERE url = ?',
                (url,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                content, updated_at = row
                if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=max_age_hours):
                    return content
        except Exception:
            pass
        return None
    
    async def set_raw_source(self, url: str, content: str, etag: str = "", last_modified: str = ""):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                f'''INSERT OR REPLACE INTO {DATABASE_TABLE}_raw 
                    (url, content, etag, last_modified, updated_at) 
                    VALUES (?, ?, ?, ?, ?)''',
                (url, content, etag, last_modified, datetime.now().isoformat())
            )
            await self._conn.commit()
        except Exception:
            pass
    
    async def get_raw_headers(self, url: str) -> tuple:
        if not self._conn:
            return '', ''
        try:
            cursor = await self._conn.execute(
                f'SELECT etag, last_modified FROM {DATABASE_TABLE}_raw WHERE url = ?',
                (url,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                return row[0] or '', row[1] or ''
            return '', ''
        except Exception:
            return '', ''
    
    async def get_speed_result(self, channel_key: str, max_age_hours: int = None) -> Optional[Dict]:
        if not self._conn:
            return None
        if max_age_hours is None:
            max_age_hours = CACHE_SPEED_HOURS
        try:
            cursor = await self._conn.execute(
                f'SELECT name, url, latency, video_codec, ip_info, updated_at FROM {DATABASE_TABLE}_speed WHERE channel_key = ?',
                (channel_key,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                name, url, latency, video_codec, ip_info_json, updated_at = row
                if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=max_age_hours):
                    return {
                        "name": name,
                        "url": url,
                        "latency": latency,
                        "video_codec": video_codec,
                        "ip_info": json.loads(ip_info_json) if ip_info_json else None
                    }
        except Exception:
            pass
        return None
    
    async def set_speed_result(self, channel_key: str, channel_data: Dict):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                f'''INSERT OR REPLACE INTO {DATABASE_TABLE}_speed 
                    (channel_key, name, url, latency, video_codec, ip_info, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (
                    channel_key,
                    channel_data.get("name", ""),
                    channel_data.get("url", ""),
                    channel_data.get("latency", 9999),
                    channel_data.get("video_codec", ""),
                    json.dumps(channel_data.get("ip_info")) if channel_data.get("ip_info") else None,
                    datetime.now().isoformat()
                )
            )
            await self._conn.commit()
        except Exception:
            pass
    
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
    
    async def is_stale(self, expiry_seconds: int = 3*24*3600) -> bool:
        last = await self.get_last_update_time()
        if last is None:
            return True
        return (int(datetime.now().timestamp()) - last) > expiry_seconds
    
    async def get_stats(self) -> Dict:
        if not self._conn:
            return {"enabled": False}
        try:
            raw_cursor = await self._conn.execute(f'SELECT COUNT(*) FROM {DATABASE_TABLE}_raw')
            raw_count = (await raw_cursor.fetchone())[0]
            speed_cursor = await self._conn.execute(f'SELECT COUNT(*) FROM {DATABASE_TABLE}_speed')
            speed_count = (await speed_cursor.fetchone())[0]
            return {"enabled": True, "raw_sources": raw_count, "speed_results": speed_count}
        except Exception:
            return {"enabled": True, "raw_sources": 0, "speed_results": 0}
    
    async def cleanup_expired(self, raw_hours: int = None, speed_hours: int = None):
        if not self._conn:
            return
        if raw_hours is None:
            raw_hours = CACHE_RAW_HOURS
        if speed_hours is None:
            speed_hours = CACHE_SPEED_HOURS
        expired_raw = datetime.now() - timedelta(hours=raw_hours)
        expired_speed = datetime.now() - timedelta(hours=speed_hours)
        await self._conn.execute(
            f"DELETE FROM {DATABASE_TABLE}_raw WHERE updated_at < ?",
            (expired_raw.isoformat(),)
        )
        await self._conn.execute(
            f"DELETE FROM {DATABASE_TABLE}_speed WHERE updated_at < ?",
            (expired_speed.isoformat(),)
        )
        await self._conn.commit()
        logger.info(f"🧹 清理过期缓存: raw表保留{raw_hours}小时, speed表保留{speed_hours}小时")
    
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
