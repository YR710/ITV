# src/epg_injector.py
"""EPG 信息注入模块：为 M3U 输出添加 tvg-id 和 tvg-logo"""

from typing import Dict, List
from src.iptv_org_adapter import get_iptv_org_adapter
from src.logger import logger

class EPGInjector:
    """为频道注入 EPG 元数据"""
    
    def __init__(self):
        self.adapter = get_iptv_org_adapter()
        self.injected_count = 0
    
    def inject_epg_metadata(self, channels: List[Dict]) -> List[Dict]:
        """为频道列表注入 tvg-id 和 tvg-logo"""
        if not self.adapter.enabled:
            logger.info("⏭️ EPG 注入已跳过（适配器未启用）")
            return channels
        
        for ch in channels:
            # 获取 EPG ID
            epg_id = self.adapter.get_epg_id(ch["name"])
            if epg_id:
                ch["tvg_id"] = epg_id
                self.injected_count += 1
                
                # 如果频道没有 logo，从 iptv-org 获取
                if not ch.get("logo"):
                    ch["logo"] = self.adapter.get_logo_url(epg_id)
        
        logger.info(f"📺 EPG 注入完成：{self.injected_count}/{len(channels)} 个频道已匹配")
        return channels
    
    def generate_m3u_with_epg(self, channels: List[Dict], output_path) -> None:
        """生成带完整 EPG 标签的 M3U 文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for ch in channels:
                # 构建 EXTINF 行，包含 EPG 属性
                tags = []
                if ch.get("tvg_id"):
                    tags.append(f'tvg-id="{ch["tvg_id"]}"')
                if ch.get("logo"):
                    tags.append(f'tvg-logo="{ch["logo"]}"')
                if ch.get("group_title"):
                    tags.append(f'group-title="{ch["group_title"]}"')
                
                tags_str = " ".join(tags)
                url = ch.get("urls", [ch.get("url")])[0]
                name = ch["name"]
                
                f.write(f'#EXTINF:-1 {tags_str},{name}\n{url}\n')
        
        logger.info(f"✅ EPG M3U 文件已生成: {output_path}")

# 全局实例
_injector = None

def get_epg_injector() -> EPGInjector:
    global _injector
    if _injector is None:
        _injector = EPGInjector()
    return _injector
