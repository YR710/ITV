# src/orchestrator.py
"""协调器 - 整合所有模块，实现自治系统"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from src.logger import logger
from src.database import get_db_cache
from src.source_pool import SourceDiscoverer
from src.candidate import CandidateObserver
from src.stable import StableManager
from src.quality import QualityMonitor
from src.config import ENABLE_DEMO_FILTER
from src.demo_filter import parse_demo_order_with_categories
from src.generator import generate_outputs_from_demo


class IPTVOrchestrator:
    """
    IPTV 自治系统协调器
    
    工作流程:
    1. 发现新源 -> 源池
    2. 新源进入候选版观察
    3. 候选源稳定后提升到稳定版
    4. 持续监控稳定版质量
    5. 质量下降时自动从候选池找替代
    """
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化各模块
        self.discoverer = SourceDiscoverer(self.data_dir / "source_pool.json")
        self.candidate_observer = CandidateObserver(self.data_dir / "candidate_pool.json")
        self.stable_manager = StableManager()
        self.quality_monitor = QualityMonitor(self.stable_manager)
        
        # 运行统计
        self.stats = {
            "last_discover": None,
            "last_observe": None,
            "last_quality_check": None,
            "total_promoted": 0,
            "total_replaced": 0
        }
    
    async def discover_phase(self) -> Dict:
        """阶段1: 发现新源"""
        logger.info("=" * 50)
        logger.info("阶段1: 发现新源")
        logger.info("=" * 50)
        
        db = await get_db_cache()
        new_sources = await self.discoverer.discover(db)
        
        # 将新源加入候选池
        for channel_name, sources in new_sources.items():
            for src in sources:
                self.candidate_observer.add_candidate(
                    src.get_key(), channel_name, src.url
                )
        
        self.stats["last_discover"] = datetime.now()
        self.stats["new_sources_count"] = sum(len(s) for s in new_sources.values())
        
        logger.info(f"✅ 发现阶段完成: {self.stats['new_sources_count']} 个新源进入候选池")
        return new_sources
    
    async def observe_phase(self) -> List:
        """阶段2: 观察候选源"""
        logger.info("=" * 50)
        logger.info("阶段2: 观察候选源")
        logger.info("=" * 50)
        
        stable_candidates = await self.candidate_observer.observe_all()
        
        self.stats["last_observe"] = datetime.now()
        self.stats["stable_candidates_count"] = len(stable_candidates)
        
        logger.info(f"✅ 观察阶段完成: {len(stable_candidates)} 个源达到稳定标准")
        return stable_candidates
    
    async def promote_phase(self, stable_candidates: List = None) -> int:
        """阶段3: 提升稳定源"""
        logger.info("=" * 50)
        logger.info("阶段3: 提升稳定源")
        logger.info("=" * 50)
        
        if stable_candidates is None:
            stable_candidates = self.candidate_observer.get_stable_candidates()
        
        promoted_count = 0
        for obs in stable_candidates:
            # 检查稳定版是否已有该频道
            existing = self.stable_manager.stable_sources.get(obs.channel_name)
            
            # 如果已有且是固定源，跳过
            if existing and existing.is_fixed:
                logger.debug(f"⏭️ {obs.channel_name} 是固定源，跳过自动提升")
                continue
            
            # 如果现有源质量更好，跳过
            if existing and existing.latency < obs.avg_latency:
                logger.debug(f"⏭️ {obs.channel_name} 现有源延迟更低 ({existing.latency} < {obs.avg_latency})")
                continue
            
            # 提升为稳定源
            if self.stable_manager.promote_candidate(
                obs.channel_name, obs.url, obs.avg_latency, ""
            ):
                promoted_count += 1
                self.candidate_observer.mark_promoted(obs.source_key)
        
        self.stats["total_promoted"] += promoted_count
        logger.info(f"✅ 提升阶段完成: {promoted_count} 个源被提升到稳定版")
        return promoted_count
    
    async def quality_phase(self) -> List:
        """阶段4: 质量监控"""
        logger.info("=" * 50)
        logger.info("阶段4: 质量监控")
        logger.info("=" * 50)
        
        reports = await self.quality_monitor.check_all_active_sources()
        
        self.stats["last_quality_check"] = datetime.now()
        
        # 处理需要替换的源
        replaced = []
        for report in reports:
            if report.status == "critical":
                logger.warning(f"⚠️ {report.channel_name} 质量严重下降，寻找替代源...")
                
                # 从候选池找替代
                for obs in self.candidate_observer.get_stable_candidates():
                    if obs.channel_name == report.channel_name:
                        if self.stable_manager.replace_source(
                            report.channel_name, obs.url, obs.avg_latency, ""
                        ):
                            replaced.append(report.channel_name)
                            self.stats["total_replaced"] += 1
                            break
        
        logger.info(f"✅ 质量检查完成: 替换了 {len(replaced)} 个失效源")
        return replaced
    
    async def generate_output_phase(self):
        """阶段5: 生成输出"""
        logger.info("=" * 50)
        logger.info("阶段5: 生成输出")
        logger.info("=" * 50)
        
        channels = self.stable_manager.get_output_channels()
        
        if not channels:
            logger.warning("⚠️ 没有可输出的稳定源")
            return
        
        # 获取 demo 顺序
        demo_order = parse_demo_order_with_categories() if ENABLE_DEMO_FILTER else []
        
        # 生成输出
        if demo_order:
            generate_outputs_from_demo(channels, demo_order)
        else:
            # 简单输出
            from src.generator import M3U_FILE, TXT_FILE, OUTPUT_DIR
            from src.generator_enhanced import EnhancedOutputGenerator
            output_gen = EnhancedOutputGenerator()
            output_gen.generate_all_outputs(channels, [], enable_json=True, enable_lite=True, enable_epg=True)
        
        logger.info(f"✅ 输出生成完成: {len(channels)} 个稳定源")
    
    async def run_once(self) -> Dict:
        """完整执行一次自治流程"""
        logger.info("🚀 IPTV 自治系统启动")
        
        try:
            # 1. 发现新源
            await self.discover_phase()
            
            # 2. 观察候选源
            stable_candidates = await self.observe_phase()
            
            # 3. 提升稳定源
            await self.promote_phase(stable_candidates)
            
            # 4. 质量监控
            await self.quality_phase()
            
            # 5. 生成输出
            await self.generate_output_phase()
            
            # 打印统计
            logger.info("=" * 50)
            logger.info("📊 运行统计")
            logger.info("=" * 50)
            logger.info(f"  源池总数: {self.discoverer.get_statistics()['total']}")
            logger.info(f"  候选池总数: {self.candidate_observer.get_statistics()['total']}")
            logger.info(f"  稳定源数量: {len(self.stable_manager.get_active_sources())}")
            logger.info(f"  固定源数量: {sum(1 for s in self.stable_manager.stable_sources.values() if s.is_fixed)}")
            logger.info(f"  累计提升: {self.stats['total_promoted']}")
            logger.info(f"  累计替换: {self.stats['total_replaced']}")
            
        except Exception as e:
            logger.exception(f"❌ 自治流程执行失败: {e}")
        
        return self.stats


# 全局实例
_orchestrator = None


def get_orchestrator() -> IPTVOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IPTVOrchestrator()
    return _orchestrator


async def run_autonomous_mode():
    """运行自治模式（替代原有 run.py）"""
    orchestrator = get_orchestrator()
    return await orchestrator.run_once()
