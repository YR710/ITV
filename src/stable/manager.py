# src/stable/manager.py
"""稳定版管理器 - 管理最终使用的稳定源"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.logger import logger
from src.config import OUTPUT_DIR
from src.stable.models import StableSource, StableStatus


class StableManager:
    """稳定版管理器"""
    
    STABLE_FILE = OUTPUT_DIR / "stable_sources.json"
    
    def __init__(self):
        self.stable_sources: Dict[str, StableSource] = {}
        self._load()
    
    def _load(self):
        """加载稳定源配置"""
        if self.STABLE_FILE.exists():
            try:
                with open(self.STABLE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, src in data.items():
                        self.stable_sources[name] = StableSource.from_dict(src)
                logger.info(f"✅ 加载 {len(self.stable_sources)} 个稳定源")
            except Exception as e:
                logger.warning(f"加载稳定源失败: {e}")
    
    def _save(self):
        """保存稳定源配置"""
        try:
            data = {name: src.to_dict() for name, src in self.stable_sources.items()}
            with open(self.STABLE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存稳定源失败: {e}")
    
    def promote_candidate(self, channel_name: str, url: str, latency: int, video_codec: str) -> bool:
        """将候选源提升为稳定源"""
        current = self.stable_sources.get(channel_name)
        
        # 如果是固定源，不允许自动替换
        if current and current.is_fixed:
            logger.warning(f"⚠️ {channel_name} 是固定源，不允许自动替换")
            return False
        
        # 如果 URL 相同，不需要更新
        if current and current.url == url:
            logger.debug(f"{channel_name} URL 未变化，跳过更新")
            return False
        
        self.stable_sources[channel_name] = StableSource(
            channel_name=channel_name,
            url=url,
            latency=latency,
            video_codec=video_codec,
            promoted_at=datetime.now(),
            is_fixed=False,
            status=StableStatus.ACTIVE
        )
        self._save()
        logger.info(f"✅ {channel_name} 已提升为稳定源: {url[:80]}...")
        return True
    
    def set_fixed_source(self, channel_name: str, url: str) -> bool:
        """设置固定源（用户明确保留，不会被自动替换）"""
        if not url:
            return False
        
        self.stable_sources[channel_name] = StableSource(
            channel_name=channel_name,
            url=url,
            latency=0,
            video_codec="",
            promoted_at=datetime.now(),
            is_fixed=True,
            status=StableStatus.ACTIVE
        )
        self._save()
        logger.info(f"📌 {channel_name} 已设为固定源: {url[:80]}...")
        return True

    def remove_fixed_source(self, channel_name: str) -> bool:
        """删除固定源（取消固定标记，但保留源）"""
        if channel_name not in self.stable_sources:
            logger.warning(f"⚠️ {channel_name} 不存在，无法取消固定")
            return False
        
        src = self.stable_sources[channel_name]
        if not src.is_fixed:
            logger.warning(f"⚠️ {channel_name} 不是固定源")
            return False
        
        # 取消固定标记，但保留源（状态改为 active）
        src.is_fixed = False
        self._save()
        logger.info(f"🗑️ 已取消固定源: {channel_name}")
        return True
    
    def get_stable_sources(self) -> Dict[str, StableSource]:
        """获取所有稳定源"""
        return self.stable_sources
    
    def get_active_sources(self) -> Dict[str, StableSource]:
        """获取活跃的稳定源"""
        return {n: s for n, s in self.stable_sources.items() if s.status == StableStatus.ACTIVE}
    
    def get_output_channels(self) -> List[dict]:
        """生成输出用的频道列表"""
        channels = []
        for name, src in self.stable_sources.items():
            if src.status == StableStatus.ACTIVE and src.url:
                channels.append({
                    "name": name,
                    "url": src.url,
                    "latency": src.latency,
                    "video_codec": src.video_codec,
                    "is_fixed": src.is_fixed
                })
        return channels
    
    def record_failure(self, channel_name: str):
        """记录失败"""
        if channel_name in self.stable_sources:
            src = self.stable_sources[channel_name]
            src.fail_count += 1
            src.last_verified = datetime.now()
            if src.fail_count >= 3 and not src.is_fixed:
                src.status = StableStatus.DEGRADED
                logger.warning(f"⚠️ {channel_name} 质量下降，已标记为 DEGRADED")
            self._save()
    
    def record_success(self, channel_name: str):
        """记录成功"""
        if channel_name in self.stable_sources:
            src = self.stable_sources[channel_name]
            src.fail_count = 0
            src.last_verified = datetime.now()
            if src.status == StableStatus.DEGRADED:
                src.status = StableStatus.ACTIVE
                logger.info(f"✅ {channel_name} 已恢复活跃")
            self._save()
    
    def replace_source(self, channel_name: str, new_url: str, latency: int, video_codec: str) -> bool:
        """替换失效源"""
        current = self.stable_sources.get(channel_name)
        if current and current.is_fixed:
            logger.warning(f"⚠️ {channel_name} 是固定源，不允许自动替换")
            return False
        
        old_url = current.url if current else "None"
        self.stable_sources[channel_name] = StableSource(
            channel_name=channel_name,
            url=new_url,
            latency=latency,
            video_codec=video_codec,
            promoted_at=datetime.now(),
            is_fixed=False,
            status=StableStatus.ACTIVE
        )
        self._save()
        logger.info(f"🔄 {channel_name} 已替换: {old_url[:50]}... -> {new_url[:50]}...")
        return True
