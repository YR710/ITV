# src/quality/models.py
"""质量监控数据模型"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple


class QualityStatus:
    """质量状态"""
    HEALTHY = "healthy"        # 健康
    WARNING = "warning"        # 警告
    CRITICAL = "critical"      # 严重
    UNKNOWN = "unknown"        # 未知


@dataclass
class QualityReport:
    """质量报告"""
    channel_name: str
    status: str
    success_rate: float
    avg_latency: int
    sample_count: int
    last_check: datetime
    consecutive_fails: int = 0
    
    def needs_replacement(self, max_fails: int = 3) -> bool:
        """判断是否需要替换"""
        return self.status == QualityStatus.CRITICAL or self.consecutive_fails >= max_fails
