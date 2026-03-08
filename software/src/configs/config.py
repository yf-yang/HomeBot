"""配置管理 - 集中管理所有硬件和系统配置"""
import os
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class CameraConfig:
    """摄像头配置"""
    device_id: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30


@dataclass
class ArmConfig:
    """机械臂配置"""
    serial_port: str = "COM15"
    baudrate: int = 1000000
    # 舵机ID映射
    base_id: int = 1
    shoulder_id: int = 2
    elbow_id: int = 3
    wrist_flex_id: int = 4
    wrist_roll_id: int =5
    gripper_id: int = 6


@dataclass
class ChassisConfig:
    """底盘配置 - 从机器人配置文件读取"""
    # 串口配置（Windows: COM3, Linux: /dev/ttyUSB0）
    serial_port: str = "COM15"
    baudrate: int = 1000000
    
    # 舵机ID映射
    left_front_id: int = 7
    right_front_id: int = 9
    rear_id: int = 8
    
    # 物理参数
    wheel_radius: float = 0.08      # 轮子半径 (m)
    chassis_radius: float = 0.18     # 底盘半径 (m)
    
    # 运动限制
    max_linear_speed: float = 0.5    # 最大线速度 (m/s)
    max_angular_speed: float = 1.0   # 最大角速度 (rad/s)
    default_wheel_speed: int = 3250  # 舵机最大速度
    
    # ZeroMQ地址
    service_addr: str = "tcp://127.0.0.1:5556"


@dataclass
class ZMQConfig:
    """ZeroMQ网络配置"""
    motion_service_addr: str = "tcp://*:5555"
    vision_pub_addr: str = "tcp://*:5560"
    speech_service_addr: str = "tcp://*:5570"


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"


@dataclass
class Config:
    """全局配置"""
    camera: CameraConfig = field(default_factory=CameraConfig)
    arm: ArmConfig = field(default_factory=ArmConfig)
    chassis: ChassisConfig = field(default_factory=ChassisConfig)
    zmq: ZMQConfig = field(default_factory=ZMQConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """从字典创建配置"""
        return cls(
            camera=CameraConfig(**data.get("camera", {})),
            arm=ArmConfig(**data.get("arm", {})),
            chassis=ChassisConfig(**data.get("chassis", {})),
            zmq=ZMQConfig(**data.get("zmq", {})),
            logging=LoggingConfig(**data.get("logging", {}))
        )


# 全局配置实例
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def set_config(config: Config):
    """设置全局配置实例"""
    global _config_instance
    _config_instance = config
