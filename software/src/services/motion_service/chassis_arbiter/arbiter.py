"""
底盘仲裁器 - 核心数据结构
用于ChassisService的仲裁逻辑
"""
from dataclasses import dataclass


@dataclass
class ControlCommand:
    """控制指令数据结构"""
    source: str
    vx: float
    vy: float
    vz: float
    priority: int
    timestamp: float = 0.0


@dataclass
class ArbiterResponse:
    """仲裁器响应数据结构"""
    success: bool
    message: str
    current_owner: str
    current_priority: int


# 控制源优先级定义
PRIORITIES = {
    "emergency": 4,
    "auto": 3,
    "voice": 2,
    "web": 1,
}
