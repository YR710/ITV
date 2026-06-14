# src/speed_tester.py - 纯批量日志版本（无进度条刷新）

import asyncio
import aiohttp
import time
import re
from src.config import HEADERS, TIMEOUT, MAX_WORKERS
from src.database import get_db_cache, channel_key
from src.logger import logger

# 广告/追踪域名黑名单
AD_PATTERNS = [
    r'ads?\.', r'adserver', r'doubleclick', r'googlead', r'googlesyndication',
    r'amazon-adsystem', r'criteo', r'taboola', r'outbrain', r'scorecardresearch',
    r'moatads', r'openx', r'pubmatic', r'/ad/', r'/ads/', r'/sponsor', r'/promo',
]

# 无效内容关键词
INVALID_CONTENT_PATTERNS = [
    r'<html', r'<!DOCTYPE', r'404 not found', r'access denied',
    r'forbidden', r'请勿滥用', r'该资源暂不可用', r'live\.twitch\.tv/embed', r'youtube\.com',
]

# 进度输出间隔（每处理多少个频道输出一次）
PROGRESS_INTERVAL = 500


def is_suspicious_url(url: str) -> bool:
    url_lower = url.lower()
    for pattern in AD_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    return False


async def probe_channel_advanced(session: aiohttp.ClientSession, channel: dict) -> tuple:
    url = channel["url"]
    
    if is_suspicious_url(url):
        return channel, 0, False, 0
    
    try:
        start = time.time()
        
        try:
            async with session.head(url, timeout=5, allow_redirects=True, headers=HEADERS) as resp:
                if resp.status != 200:
                    return channel, 0, False, 0
                content_type = resp.headers.get("content-type", "").lower()
                if "video" not in content_type and "mpegurl" not in content_type and "x-mpegurl" not in content_type:
                    return channel, 0, False, 0
        except:
            return channel, 0, False, 0
        
        head_latency = int((time.time() - start) * 1000)
        
        start_download = time.time()
        try:
            async with session.get(url, timeout=TIMEOUT, headers={**HEADERS, "Range": "bytes=0-262144"}) as resp:
                if resp.status not in [200, 206]:
                    return channel, head_latency, False, 0
                
                data = await resp.content.read(262144)
                
                data_lower = data.lower()
                for pattern in INVALID_CONTENT_PATTERNS:
                    if re.search(pattern.encode(), data_lower):
                        return channel, head_latency, False, 0
                
                is_valid = False
                if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                    is_valid = True
                else:
                    video_signatures = [
                        b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp',
                        b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV',
                    ]
                    for sig in video_signatures:
                        if data.startswith(sig):
                            is_valid = True
                            break
                
                if not is_valid:
                    return channel, head_latency, False, 0
                
                download_time = time.time() - start_download
                final_latency = head_latency + int(download_time * 1000)
                
                return channel, final_latency, True, 0
                
        except:
            return channel, head_latency, False, 0
            
    except:
        return channel, 0, False, 0


async def test_channels_concurrent(channels_dict: dict) -> list:
    channels = list(channels_dict.values())
    db = await get_db_cache()
    
    # 缓存读取
    cached_results = []
    to_probe = []
    
    for ch in channels:
        key = channel_key(ch["name"], ch["url"])
        cached = await db.get_speed_result(key)
        if cached and cached.get("latency", 9999) < 5000:
            ch["latency"] = cached["latency"]
            ch["video_codec"] = cached.get("video_codec", "")
            cached_results.append(ch)
        else:
            to_probe.append(ch)
    
    logger.info(f"⚡ 测速: {len(to_probe)} 个新频道需探测，{len(cached_results)} 个来自缓存")
    
    valid = cached_results.copy()
    
    if not to_probe:
        logger.info("✅ 所有频道均来自缓存，无需探测")
        return valid
    
    semaphore = asyncio.Semaphore(MAX_WORKERS)
    
    async def bounded_probe(session, ch):
        async with semaphore:
            return await probe_channel_advanced(session, ch)
    
    connector = aiohttp.TCPConnector(limit=MAX_WORKERS, limit_per_host=3)
    timeout_config = aiohttp.ClientTimeout(total=TIMEOUT + 5)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout_config) as session:
        tasks = [bounded_probe(session, ch) for ch in to_probe]
        
        total = len(tasks)
        completed = 0
        last_log_count = 0
        start_time = time.time()
        valid_count = len(valid)
        
        logger.info(f"  📡 开始测速 {total} 个频道，每 {PROGRESS_INTERVAL} 个输出一次进度...")
        
        for coro in asyncio.as_completed(tasks):
            ch, latency, ok, _ = await coro
            completed += 1
            
            if ok:
                ch["latency"] = latency
                valid.append(ch)
                valid_count += 1
                key = channel_key(ch["name"], ch["url"])
                await db.set_speed_result(key, ch)
            
            # 每完成 PROGRESS_INTERVAL 个或全部完成时输出一次日志
            if completed - last_log_count >= PROGRESS_INTERVAL or completed == total:
                percent = completed * 100 // total
                elapsed = time.time() - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                logger.info(f"  📡 测速进度: {completed}/{total} ({percent}%) - 有效: {valid_count} - 速度: {speed:.1f}频道/秒")
                last_log_count = completed
    
    # 排序
    valid.sort(key=lambda x: x.get("latency", 9999))
    
    total = len(channels)
    filtered = total - len(valid)
    logger.info(f"✅ 测速完成: 有效 {len(valid)}/{total}，过滤 {filtered} 个无效源")
    
    if valid:
        latencies = [ch.get("latency", 9999) for ch in valid[:100]]
        avg_latency = sum(latencies) / len(latencies)
        logger.info(f"📊 平均延迟: {avg_latency:.0f}ms (前100个频道)")
    
    return valid
