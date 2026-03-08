"""配置管理，支持 json/yaml/env 等基础加载，同时提供内置 Python Config 类。"""
import os
import json
from typing import Any, Dict
from dataclasses import dataclass, field


@dataclass
class CameraConfig:
    device_id: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30


@dataclass
class ArmConfig:
    serial_port: str = "COM3"
    baudrate: int = 115200


@dataclass
class ChassisConfig:
    max_velocity: float = 1.0
    max_angular_velocity: float = 1.5


@dataclass
class ZMQConfig:
    motion_service_addr: str = "tcp://*:5555"
    vision_pub_addr: str = "tcp://*:5560"
    speech_service_addr: str = "tcp://*:5570"


@dataclass
class NetworkConfig:
    zmq: ZMQConfig = field(default_factory=ZMQConfig)


@dataclass
class LoggingConfig:
    level: str = "INFO"


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    arm: ArmConfig = field(default_factory=ArmConfig)
    chassis: ChassisConfig = field(default_factory=ChassisConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

