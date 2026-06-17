# src/candidate/observer.py
"""候选版观察者 - 优化版，复用缓存，降低稳定门槛"""

import asyncio
import json
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from src.logger import logger
from src.speed_tester import probe_channel_advanced
from src.database import get_db_cache, channel_key
from src.config import TIMEOUT
from src.candidate.models import ObservationResult, CandidateStatus


class CandidateObserver:
    """
    候选版观察者 - 优化版
    
    观察策略:
    - 复用数据库中的测速结果
    - 降低稳定门槛（3次成功，成功率50%，延迟3000ms）
    - 大批量处理
    """
    
    # 降低稳定门槛，加快提升
    MIN_SUCCESS_COUNT = 3       # 从10降到3
    MIN_SUCCESS_RATE = 0.5      # 从0.8降到0.5
    MAX_AVG_LATENCY = 3000      # 从2000放宽到3000
    MAX_OBSERVE_PER_RUN = 3000  # 从300增加到3000
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("data/candidate_pool.json")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._observations: Dict[str, ObservationResult] = {}
        self._load()
    
    def _load(self):
        """加载观察数据"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self._observations[k] = ObservationResult.from_dict(v)
                logger.info(f"📦 加载候选池: {len(self._observations)} 个候选源")
            except Exception as e:
                logger.warning(f"加载候选池失败: {e}")
    
    def _save(self):
        """保存观察数据"""
        try:
            data = {k: v.to_dict() for k, v in self._observations.items()}
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存候选池失败: {e}")
    
    def add_candidate(self, source_key: str, channel_name: str, url: str):
        """添加候选源"""
        if source_key not in self._observations:
            self._observations[source_key] = ObservationResult(
                source_key=source_key,
                channel_name=channel_name,
                url=url
            )
            self._save()
    
    def add_candidates_batch(self, sources: List[tuple]):
        """批量添加候选源"""
        added = 0
        for source_key, channel_name, url in sources:
            if source_key not in self._observations:
                self._observations[source_key] = ObservationResult(
                    source_key=source_key,
                    channel_name=channel_name,
                    url=url
                )
                added += 1
        if added > 0:
            self._save()
            logger.info(f"📝 批量添加 {added} 个候选源")
    
    async def check_candidate_from_cache(self, source_key: str, db) -> bool:
        """从数据库缓存检查候选源（更快）"""
        obs = self._observations.get(source_key)
        if not obs:
            return False
        
        if obs.status in [CandidateStatus.STABLE, CandidateStatus.PROMOTED]:
            return obs.status == CandidateStatus.STABLE
        
        # 从数据库获取测速结果
        key = channel_key(obs.channel_name, obs.url)
        cached = await db.get_speed_result(key)
        
        obs.check_count += 1
        obs.last_check = datetime.now()
        
        if cached and cached.get("latency", 9999) < 5000:
            obs.success_count += 1
            obs.total_latency += cached.get("latency", 0)
        else:
            obs.fail_count += 1
        
        # 判断是否达到稳定标准（降低门槛）
        if obs.check_count >= self.MIN_SUCCESS_COUNT:
            if (obs.success_rate >= self.MIN_SUCCESS_RATE and 
                obs.avg_latency <= self.MAX_AVG_LATENCY):
                obs.status = CandidateStatus.STABLE
                logger.info(f"✅ 候选源已稳定: {obs.channel_name} (成功率:{obs.success_rate:.1%}, 延迟:{obs.avg_latency:.0f}ms)")
                self._save()
                return True
        
        self._save()
        return obs.status == CandidateStatus.STABLE
    
    async def observe_batch_from_cache(self, batch_size: int = 3000) -> List[ObservationResult]:
        """从缓存分批观察候选源（大批量）"""
        observing = [
            (k, v) for k, v in self._observations.items() 
            if v.status == CandidateStatus.OBSERVING
        ]
        
        if not observing:
            logger.info("📭 没有正在观察的候选源")
            return []
        
        # 按检查次数排序（检查次数少的优先）
        observing.sort(key=lambda x: x[1].check_count)
        
        # 取前 batch_size 个
        batch = observing[:batch_size]
        
        logger.info(f"🔍 本次观察 {len(batch)} 个候选源（共 {len(observing)} 个待观察）...")
        
        db = await get_db_cache()
        stable_results = []
        
        for key, obs in batch:
            if await self.check_candidate_from_cache(key, db):
                stable_results.append(obs)
        
        if stable_results:
            logger.info(f"✅ 本批次 {len(stable_results)} 个源达到稳定标准")
        else:
            logger.info(f"📊 本批次无新稳定源")
        
        return stable_results
    
    def get_candidates(self) -> List[ObservationResult]:
        """获取所有候选源"""
        return list(self._observations.values())
    
    def get_stable_candidates(self) -> List[ObservationResult]:
        """获取已稳定的候选源"""
        return [v for v in self._observations.values() if v.status == CandidateStatus.STABLE]
    
    def get_observing_count(self) -> int:
        """获取正在观察的候选源数量"""
        return sum(1 for v in self._observations.values() if v.status == CandidateStatus.OBSERVING)
    
    def mark_promoted(self, source_key: str):
        """标记为已提升"""
        if source_key in self._observations:
            self._observations[source_key].status = CandidateStatus.PROMOTED
            self._observations[source_key].promoted_at = datetime.now()
            self._save()
    
    def get_statistics(self) -> dict:
        """获取候选池统计"""
        stats = {
            "total": len(self._observations),
            "observing": self.get_observing_count(),
            "stable": sum(1 for v in self._observations.values() if v.status == CandidateStatus.STABLE),
            "promoted": sum(1 for v in self._observations.values() if v.status == CandidateStatus.PROMOTED),
            "rejected": sum(1 for v in self._observations.values() if v.status == CandidateStatus.REJECTED),
        }
        return stats
