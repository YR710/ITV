#!/usr/bin/env python3
# src/server.py
# IPTV Web 服务器 - 提供文件服务、REST API 和 Web 管理界面

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from aiohttp import web

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    OUTPUT_DIR, WEB_SERVER_HOST, WEB_SERVER_PORT,
    MAX_WORKERS, TIMEOUT, FFMPEG_ENABLE,
    MAX_SOURCES_PER_CHANNEL, DEMO_MATCH_MODE,
    CACHE_RAW_HOURS, CACHE_SPEED_HOURS
)
from src.logger import logger
from src.stable.manager import StableManager
from src.source_pool.discoverer import SourceDiscoverer
from src.candidate.observer import CandidateObserver
from src.web.db import get_quality_history, get_all_channels_with_history


# ============================================================
#  API 处理函数
# ============================================================

async def api_status(request):
    """获取系统状态"""
    stable_mgr = StableManager()
    stable_sources = stable_mgr.get_active_sources()
    
    discoverer = SourceDiscoverer()
    pool_stats = discoverer.get_statistics()
    
    observer = CandidateObserver()
    candidate_stats = observer.get_statistics()
    
    last_run = None
    stats_file = OUTPUT_DIR / "stats.json"
    if stats_file.exists():
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                last_run = data.get('timestamp')
        except:
            pass
    
    return web.json_response({
        'stable_count': len(stable_sources),
        'fixed_count': sum(1 for s in stable_sources.values() if s.is_fixed),
        'pool_total': pool_stats.get('total', 0),
        'candidate_observing': candidate_stats.get('observing', 0),
        'last_run': last_run,
        'status': 'running'
    })


async def api_channels(request):
    """获取频道列表（支持搜索和分类筛选）"""
    search = request.query.get('search', '').strip().lower()
    category = request.query.get('category', '').strip()
    
    stable_mgr = StableManager()
    sources = stable_mgr.get_active_sources()
    
    channels = []
    for name, src in sources.items():
        if not src.url:
            continue
        if search and search not in name.lower():
            continue
        # 分类推断
        cat = '其他'
        if name.startswith('CCTV'):
            cat = '央视'
        elif '卫视' in name:
            cat = '卫视'
        elif '频道' in name and not name.startswith('CCTV'):
            cat = '地方'
        elif any(kw in name for kw in ['港', '澳', '台', 'TVB', '翡翠', '凤凰']):
            cat = '港澳台'
        if category and cat != category:
            continue
        
        channels.append({
            'name': name,
            'url': src.url,
            'latency': src.latency,
            'codec': src.video_codec,
            'is_fixed': src.is_fixed,
            'category': cat,
            'last_verified': src.last_verified.isoformat() if src.last_verified else None
        })
    
    channels.sort(key=lambda x: x['name'])
    return web.json_response(channels)


async def api_fixed_sources(request):
    """获取固定源列表"""
    stable_mgr = StableManager()
    fixed = {name: src.url for name, src in stable_mgr.stable_sources.items() if src.is_fixed}
    return web.json_response(fixed)


async def api_add_fixed_source(request):
    """添加固定源"""
    try:
        data = await request.json()
    except:
        return web.json_response({'error': '无效的JSON数据'}, status=400)
    
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    if not name or not url:
        return web.json_response({'error': '缺少频道名或URL'}, status=400)
    
    stable_mgr = StableManager()
    if stable_mgr.set_fixed_source(name, url):
        return web.json_response({'success': True, 'message': f'已添加固定源 {name}'})
    else:
        return web.json_response({'error': '添加失败'}, status=500)


async def api_delete_fixed_source(request):
    """删除固定源"""
    name = request.match_info.get('name', '')
    if not name:
        return web.json_response({'error': '缺少频道名'}, status=400)
    
    stable_mgr = StableManager()
    if name in stable_mgr.stable_sources and stable_mgr.stable_sources[name].is_fixed:
        del stable_mgr.stable_sources[name]
        stable_mgr._save()
        return web.json_response({'success': True})
    return web.json_response({'error': '固定源不存在'}, status=404)


async def api_config_get(request):
    """获取当前配置"""
    return web.json_response({
        'max_workers': MAX_WORKERS,
        'timeout': TIMEOUT,
        'ffmpeg_enable': FFMPEG_ENABLE,
        'max_sources_per_channel': MAX_SOURCES_PER_CHANNEL,
        'demo_match_mode': DEMO_MATCH_MODE,
        'cache_raw_hours': CACHE_RAW_HOURS,
        'cache_speed_hours': CACHE_SPEED_HOURS,
    })


async def api_config_post(request):
    """更新配置（示例，实际需持久化）"""
    try:
        data = await request.json()
    except:
        return web.json_response({'error': '无效数据'}, status=400)
    # 这里可以持久化，但为演示仅返回成功
    return web.json_response({
        'success': True,
        'message': '配置已接收，请重启服务生效。'
    })


async def api_quality_channel(request):
    """获取单个频道的质量趋势"""
    channel_name = request.match_info.get('channel_name', '')
    days = request.query.get('days', 7, type=int)
    if not channel_name:
        return web.json_response({'error': '缺少频道名'}, status=400)
    history = get_quality_history(channel_name, days)
    return web.json_response(history)


async def api_quality_all(request):
    """获取所有频道的质量趋势"""
    days = request.query.get('days', 7, type=int)
    data = get_all_channels_with_history(days)
    return web.json_response(data)


# ============================================================
#  静态文件与页面服务
# ============================================================

async def index_handler(request):
    """管理界面首页"""
    # 优先尝试从 src/web/static/index.html 加载
    static_dir = Path(__file__).parent / "web" / "static"
    index_path = static_dir / "index.html"
    if index_path.exists():
        return web.FileResponse(index_path)
    # 如果没有，则返回简单的提示
    return web.Response(
        text='<h1>IPTV 管理界面</h1><p>静态文件未找到，请检查 src/web/static/index.html</p>',
        content_type='text/html'
    )


async def file_handler(request):
    """文件服务：提供 output 目录下的文件"""
    filename = request.match_info.get('filename', '')
    if not filename:
        return web.Response(status=404)
    file_path = OUTPUT_DIR / filename
    if file_path.exists() and file_path.is_file():
        return web.FileResponse(file_path)
    return web.Response(status=404)


# ============================================================
#  跨域中间件
# ============================================================

@web.middleware
async def cors_middleware(request, handler):
    """添加跨域头"""
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# ============================================================
#  应用初始化与启动
# ============================================================

def create_app():
    """创建应用并注册路由"""
    app = web.Application(middlewares=[cors_middleware])
    
    # 静态文件目录（前端资源）
    static_dir = Path(__file__).parent / "web" / "static"
    if static_dir.exists():
        app.router.add_static('/static', static_dir)
        logger.info(f"📁 静态文件目录: {static_dir}")
    else:
        logger.warning(f"⚠️ 静态文件目录不存在: {static_dir}，请创建并放入 index.html, css, js 等文件")
        # 如果不存在，尝试创建
        try:
            static_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ 已创建静态文件目录: {static_dir}")
        except:
            pass
    
    # API 路由
    app.router.add_get('/api/status', api_status)
    app.router.add_get('/api/channels', api_channels)
    app.router.add_get('/api/fixed_sources', api_fixed_sources)
    app.router.add_post('/api/fixed_sources', api_add_fixed_source)
    app.router.add_delete('/api/fixed_sources/{name}', api_delete_fixed_source)
    app.router.add_get('/api/config', api_config_get)
    app.router.add_post('/api/config', api_config_post)
    app.router.add_get('/api/quality/{channel_name}', api_quality_channel)
    app.router.add_get('/api/quality/all', api_quality_all)
    
    # 首页（管理界面）
    app.router.add_get('/', index_handler)
    
    # 文件服务（output 目录下的文件）
    app.router.add_get('/{filename}', file_handler)
    
    return app


def start_server():
    """启动 Web 服务器"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app = create_app()
    
    logger.info(f"🌐 Web 管理界面启动: http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}/")
    logger.info(f"📄 播放列表: http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}/tv.m3u")
    logger.info(f"📊 API 状态: http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}/api/status")
    
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


if __name__ == "__main__":
    try:
        start_server()
    except KeyboardInterrupt:
        logger.info("⏹️ 服务器已停止")
    except Exception as e:
        logger.exception(f"❌ 服务器启动失败: {e}")
        sys.exit(1)
