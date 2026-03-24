"""MCP Server - 提供机器人控制工具

通过 ZeroMQ 调用底盘服务和机械臂服务
与 dialogue_manager 集成，支持 LLM 工具调用
"""
import json
import zmq
import time
import asyncio
import threading
from typing import Optional
from fastmcp import FastMCP

from common.logging import get_logger
from common.zmq_helper import create_socket
from configs.config import get_config

logger = get_logger(__name__)

# 创建全局 FastMCP 服务器实例
mcp = FastMCP("HomeBot Voice Interaction MCP Server")


class RobotControllerClient:
    """机器人控制器客户端 - 通过 ZeroMQ 调用服务"""
    
    # 默认超时时间（毫秒）
    DEFAULT_TIMEOUT_MS = 3000  # 3秒超时
    
    def __init__(self, timeout_ms: int = None):
        """初始化客户端
        
        Args:
            timeout_ms: 请求超时时间（毫秒），默认3000ms
        """
        config = get_config()
        self.chassis_addr = config.zmq.chassis_service_addr.replace("*", "localhost")
        self.arm_addr = config.zmq.arm_service_addr.replace("*", "localhost")
        self.context = zmq.Context()
        self.chassis_socket = None
        self.arm_socket = None
        self.timeout_ms = timeout_ms or self.DEFAULT_TIMEOUT_MS
        self._chassis_available = None  # 缓存底盘服务可用状态
        self._arm_available = None      # 缓存机械臂服务可用状态
    
    def _get_chassis_socket(self):
        """获取底盘服务 socket（惰性创建）"""
        if self.chassis_socket is None:
            self.chassis_socket = create_socket(
                zmq.REQ, 
                bind=False, 
                address=self.chassis_addr,
                context=self.context
            )
            # 设置发送和接收超时
            self.chassis_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
            self.chassis_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
            # 设置 linger 避免关闭时阻塞
            self.chassis_socket.setsockopt(zmq.LINGER, 0)
        return self.chassis_socket
    
    def _get_arm_socket(self):
        """获取机械臂服务 socket（惰性创建）"""
        if self.arm_socket is None:
            self.arm_socket = create_socket(
                zmq.REQ,
                bind=False,
                address=self.arm_addr,
                context=self.context
            )
            # 设置发送和接收超时
            self.arm_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
            self.arm_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
            # 设置 linger 避免关闭时阻塞
            self.arm_socket.setsockopt(zmq.LINGER, 0)
        return self.arm_socket
    
    def _reset_chassis_socket(self):
        """重置底盘 socket（超时后需要重新创建）"""
        if self.chassis_socket:
            try:
                self.chassis_socket.close()
            except:
                pass
            self.chassis_socket = None
            self._chassis_available = False
    
    def _reset_arm_socket(self):
        """重置机械臂 socket（超时后需要重新创建）"""
        if self.arm_socket:
            try:
                self.arm_socket.close()
            except:
                pass
            self.arm_socket = None
            self._arm_available = False
    
    def send_chassis_command(self, vx: float, vy: float, vz: float, duration_ms: int = 1000) -> dict:
        """发送底盘控制命令
        
        Args:
            vx: X方向线速度（m/s）
            vy: Y方向线速度（m/s）
            vz: Z方向角速度（rad/s）
            duration_ms: 持续时间（毫秒），默认1秒后自动停止
            
        Returns:
            dict: 命令执行结果
        """
        try:
            socket = self._get_chassis_socket()
            command = {
                "source": "voice",
                "vx": vx,
                "vy": vy,
                "vz": vz,
                "priority": 2
            }
            
            # 发送命令（带超时）
            try:
                socket.send_json(command, flags=zmq.NOBLOCK)
            except zmq.Again:
                # 发送超时，重置 socket
                self._reset_chassis_socket()
                return {
                    "status": "error", 
                    "message": f"发送命令超时，底盘服务未响应（地址: {self.chassis_addr}）。请检查底盘服务是否已启动。"
                }
            
            # 接收响应（带超时）
            try:
                response = socket.recv_json()
            except zmq.Again:
                # 接收超时，重置 socket
                self._reset_chassis_socket()
                return {
                    "status": "error", 
                    "message": f"接收响应超时，底盘服务未响应（地址: {self.chassis_addr}）。请检查底盘服务是否已启动。"
                }
            
            # 标记服务可用
            self._chassis_available = True
            
            # 如果指定了持续时间，等待后发送停止命令
            if duration_ms > 0:
                time.sleep(duration_ms / 1000.0)
                stop_command = {
                    "source": "voice",
                    "vx": 0,
                    "vy": 0,
                    "vz": 0,
                    "priority": 2
                }
                try:
                    socket.send_json(stop_command, flags=zmq.NOBLOCK)
                    socket.recv_json()
                except zmq.Again:
                    # 停止命令超时，不重置 socket（移动命令已执行）
                    logger.warning("停止命令超时，但移动命令可能已执行")
            
            return {"status": "success", "data": response}
            
        except zmq.ZMQError as e:
            # ZeroMQ 错误，重置 socket
            self._reset_chassis_socket()
            logger.error(f"ZeroMQ 错误: {e}")
            return {
                "status": "error", 
                "message": f"通信错误: {e}。请检查底盘服务是否已启动。"
            }
        except Exception as e:
            logger.error(f"发送底盘命令失败: {e}")
            return {
                "status": "error", 
                "message": f"发送命令失败: {e}"
            }
    
    def stop_chassis(self) -> dict:
        """停止底盘运动"""
        try:
            socket = self._get_chassis_socket()
            command = {
                "source": "voice",
                "vx": 0,
                "vy": 0,
                "vz": 0,
                "priority": 2
            }
            
            # 发送命令（带超时）
            try:
                socket.send_json(command, flags=zmq.NOBLOCK)
            except zmq.Again:
                self._reset_chassis_socket()
                return {
                    "status": "error",
                    "message": f"发送停止命令超时，底盘服务未响应（地址: {self.chassis_addr}）。请检查底盘服务是否已启动。"
                }
            
            # 接收响应（带超时）
            try:
                response = socket.recv_json()
            except zmq.Again:
                self._reset_chassis_socket()
                return {
                    "status": "error",
                    "message": f"接收停止响应超时，底盘服务未响应（地址: {self.chassis_addr}）。请检查底盘服务是否已启动。"
                }
            
            self._chassis_available = True
            return {"status": "success", "data": response}
            
        except zmq.ZMQError as e:
            self._reset_chassis_socket()
            logger.error(f"ZeroMQ 错误: {e}")
            return {
                "status": "error",
                "message": f"通信错误: {e}。请检查底盘服务是否已启动。"
            }
        except Exception as e:
            logger.error(f"停止底盘失败: {e}")
            return {"status": "error", "message": f"停止失败: {e}"}
    
    def send_arm_command(self, action: str, params: dict = None) -> dict:
        """发送机械臂控制命令（预留）
        
        Args:
            action: 动作名称
            params: 动作参数
            
        Returns:
            dict: 命令执行结果
        """
        try:
            socket = self._get_arm_socket()
            command = {
                "source": "voice",
                "action": action,
                "params": params or {},
                "priority": 2
            }
            
            # 发送命令（带超时）
            try:
                socket.send_json(command, flags=zmq.NOBLOCK)
            except zmq.Again:
                self._reset_arm_socket()
                return {
                    "status": "error",
                    "message": f"发送命令超时，机械臂服务未响应（地址: {self.arm_addr}）。请检查机械臂服务是否已启动。"
                }
            
            # 接收响应（带超时）
            try:
                response = socket.recv_json()
            except zmq.Again:
                self._reset_arm_socket()
                return {
                    "status": "error",
                    "message": f"接收响应超时，机械臂服务未响应（地址: {self.arm_addr}）。请检查机械臂服务是否已启动。"
                }
            
            self._arm_available = True
            return {"status": "success", "data": response}
            
        except zmq.ZMQError as e:
            self._reset_arm_socket()
            logger.error(f"ZeroMQ 错误: {e}")
            return {
                "status": "error",
                "message": f"通信错误: {e}。请检查机械臂服务是否已启动。"
            }
        except Exception as e:
            logger.error(f"发送机械臂命令失败: {e}")
            return {"status": "error", "message": f"发送命令失败: {e}"}
    
    def send_arm_joints(self, joint_angles: dict, speed: int = 800) -> dict:
        """发送机械臂关节角度命令
        
        Args:
            joint_angles: 关节角度字典，如 {"base": 0, "shoulder": 45, "elbow": 90}
            speed: 运动速度
            
        Returns:
            dict: 命令执行结果
        """
        try:
            socket = self._get_arm_socket()
            command = {
                "source": "voice",
                "priority": 2,
                "speed": speed,
                "joints": joint_angles
            }
            
            logger.info(f"发送机械臂命令: {command}, 地址: {self.arm_addr}")
            
            # 发送命令（带超时）
            try:
                socket.send_json(command, flags=zmq.NOBLOCK)
            except zmq.Again:
                self._reset_arm_socket()
                return {
                    "status": "error",
                    "message": f"发送命令超时，机械臂服务未响应（地址: {self.arm_addr}）。请检查机械臂服务是否已启动。"
                }
            
            # 接收响应（带超时）
            try:
                response = socket.recv_json()
                logger.info(f"机械臂服务响应: {response}")
            except zmq.Again:
                self._reset_arm_socket()
                return {
                    "status": "error",
                    "message": f"接收响应超时，机械臂服务未响应（地址: {self.arm_addr}）。请检查机械臂服务是否已启动。"
                }
            
            self._arm_available = True
            success = response.get("success", False)
            return {
                "status": "success" if success else "failed",
                "data": response,
                "message": response.get("message", "执行完成")
            }
            
        except zmq.ZMQError as e:
            self._reset_arm_socket()
            logger.error(f"ZeroMQ 错误: {e}")
            return {
                "status": "error",
                "message": f"通信错误: {e}。请检查机械臂服务是否已启动。"
            }
        except Exception as e:
            logger.error(f"发送机械臂关节命令失败: {e}")
            return {"status": "error", "message": f"发送命令失败: {e}"}
    
    def get_arm_joint_states(self) -> dict:
        """获取机械臂当前关节状态
        
        Returns:
            dict: 包含关节角度的字典，如 {"base": 0, "shoulder": 45, ...}
                  如果获取失败，返回空字典
        """
        try:
            socket = self._get_arm_socket()
            # 发送查询命令
            command = {
                "source": "voice",
                "priority": 2,
                "speed": 0,
                "joints": {},  # 空字典
                "query": True  # 标记为查询请求
            }
            
            logger.info(f"查询机械臂关节状态, 地址: {self.arm_addr}")
            
            # 发送命令（带超时）
            try:
                socket.send_json(command, flags=zmq.NOBLOCK)
            except zmq.Again:
                self._reset_arm_socket()
                return {}
            
            # 接收响应（带超时）
            try:
                response = socket.recv_json()
                logger.info(f"机械臂状态响应: {response}")
            except zmq.Again:
                self._reset_arm_socket()
                return {}
            
            # 从响应中提取关节状态
            joint_states = response.get("joint_states")
            if joint_states and isinstance(joint_states, dict):
                return joint_states
            
            # 如果服务端返回的 joint_states 为空，尝试从当前配置获取默认位置
            return {}
            
        except Exception as e:
            logger.error(f"获取机械臂关节状态失败: {e}")
            return {}
    
    def close(self):
        """关闭连接"""
        if self.chassis_socket:
            self.chassis_socket.close()
        if self.arm_socket:
            self.arm_socket.close()
        self.context.term()


# 全局控制器客户端实例
_controller_client: Optional[RobotControllerClient] = None


def get_controller() -> RobotControllerClient:
    """获取机器人控制器客户端（单例）"""
    global _controller_client
    if _controller_client is None:
        _controller_client = RobotControllerClient()
    return _controller_client


# ==================== MCP 工具定义 ====================

@mcp.tool
def move_forward(distance: float, speed: float = 0.3) -> dict:
    """控制机器人向前移动指定距离
    
    Args:
        distance: 移动距离，单位：米，范围 0.1-2.0
        speed: 移动速度，范围 0.1-0.5 m/s
    
    Returns:
        移动结果
    """
    try:
        controller = get_controller()
        # 计算持续时间（毫秒）
        duration_ms = int((distance / speed) * 1000) if speed > 0 else 1000
        # 限制最大持续时间（安全）
        duration_ms = min(duration_ms, 5000)  # 最多5秒
        
        result = controller.send_chassis_command(speed, 0, 0, duration_ms)
        success = result.get("status") == "success"
        
        return {
            "status": "success" if success else "failed",
            "message": f"机器人已向前移动 {distance} 米" if success else f"移动失败: {result.get('message', '')}"
        }
    except Exception as e:
        logger.error(f"移动机器人失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def move_backward(distance: float, speed: float = 0.3) -> dict:
    """控制机器人向后移动指定距离
    
    Args:
        distance: 移动距离，单位：米，范围 0.1-2.0
        speed: 移动速度，范围 0.1-0.5 m/s
    
    Returns:
        移动结果
    """
    try:
        controller = get_controller()
        duration_ms = int((distance / speed) * 1000) if speed > 0 else 1000
        duration_ms = min(duration_ms, 5000)
        
        result = controller.send_chassis_command(-speed, 0, 0, duration_ms)
        success = result.get("status") == "success"
        
        return {
            "status": "success" if success else "failed",
            "message": f"机器人已向后移动 {distance} 米" if success else f"移动失败: {result.get('message', '')}"
        }
    except Exception as e:
        logger.error(f"移动机器人失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def turn_left(angle: float, speed: float = 0.5) -> dict:
    """控制机器人向左旋转指定角度
    
    Args:
        angle: 旋转角度，单位：度，范围 15-360
        speed: 旋转速度，范围 0.3-1.0 rad/s
    
    Returns:
        旋转结果
    """
    try:
        controller = get_controller()
        # 角度转弧度，计算持续时间
        angle_rad = angle * 3.14159 / 180.0
        duration_ms = int((angle_rad / speed) * 1000)
        duration_ms = min(duration_ms, 5000)
        
        result = controller.send_chassis_command(0, 0, speed, duration_ms)
        success = result.get("status") == "success"
        
        return {
            "status": "success" if success else "failed",
            "message": f"机器人已向左旋转 {angle} 度" if success else f"旋转失败: {result.get('message', '')}"
        }
    except Exception as e:
        logger.error(f"旋转机器人失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def turn_right(angle: float, speed: float = 0.5) -> dict:
    """控制机器人向右旋转指定角度
    
    Args:
        angle: 旋转角度，单位：度，范围 15-360
        speed: 旋转速度，范围 0.3-1.0 rad/s
    
    Returns:
        旋转结果
    """
    try:
        controller = get_controller()
        angle_rad = angle * 3.14159 / 180.0
        duration_ms = int((angle_rad / speed) * 1000)
        duration_ms = min(duration_ms, 5000)
        
        result = controller.send_chassis_command(0, 0, -speed, duration_ms)
        success = result.get("status") == "success"
        
        return {
            "status": "success" if success else "failed",
            "message": f"机器人已向右旋转 {angle} 度" if success else f"旋转失败: {result.get('message', '')}"
        }
    except Exception as e:
        logger.error(f"旋转机器人失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def stop_robot() -> dict:
    """停止机器人当前动作
    
    Returns:
        停止结果
    """
    try:
        controller = get_controller()
        result = controller.stop_chassis()
        success = result.get("status") == "success"
        
        return {
            "status": "success" if success else "failed",
            "message": "机器人已停止" if success else f"停止失败: {result.get('message', '')}"
        }
    except Exception as e:
        logger.error(f"停止机器人失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def get_robot_status() -> dict:
    """获取机器人当前状态
    
    Returns:
        机器人状态信息，包含底盘、机械臂、语音和电池状态
    """
    try:
        controller = get_controller()
        # 通过发送一个停止命令来检查连接状态
        result = controller.stop_chassis()
        chassis_connected = result.get("status") == "success"
        
        # 获取电池状态（通过订阅电池话题）
        battery_info = _get_battery_status()
        
        return {
            "status": "success",
            "data": {
                "chassis_connected": chassis_connected,
                "chassis": "ready" if chassis_connected else "offline",
                "arm": "ready",  # 预留
                "speech": "active",
                "battery": battery_info
            }
        }
    except Exception as e:
        logger.error(f"获取机器人状态失败: {e}")
        return {
            "status": "success",  # 即使失败也返回成功，避免中断对话
            "data": {
                "chassis": "unknown",
                "arm": "unknown",
                "speech": "active",
                "battery": {"status": "unknown", "note": "无法获取电池状态"},
                "note": "无法获取底盘状态，可能服务未启动"
            }
        }


# 全局电池状态缓存（用于解决订阅超时问题）
_battery_status_cache: dict = {"valid": False, "timestamp": 0}
_battery_subscriber_thread = None


def _start_battery_subscriber():
    """启动电池状态订阅线程（后台持续订阅）"""
    global _battery_subscriber_thread, _battery_status_cache
    
    if _battery_subscriber_thread is not None:
        return  # 已经在运行
    
    def subscriber_loop():
        """订阅循环"""
        global _battery_status_cache
        
        try:
            config = get_config()
            battery_addr = config.battery.pub_addr.replace("*", "localhost")
            
            # 创建新的 Context（避免与主线程冲突）
            context = zmq.Context()
            socket = context.socket(zmq.SUB)
            socket.setsockopt(zmq.LINGER, 0)
            socket.connect(battery_addr)
            socket.setsockopt_string(zmq.SUBSCRIBE, "")
            
            logger.info(f"电池状态订阅线程启动: {battery_addr}")
            
            while True:
                try:
                    message = socket.recv_json()
                    if message.get("type") == "sensor.battery":
                        data = message.get("data", {})
                        _battery_status_cache = {
                            "voltage": data.get("voltage", 0),
                            "percentage": data.get("percentage", 0),
                            "status": data.get("status", "unknown"),
                            "temperature": data.get("temperature"),
                            "servo_id": data.get("servo_id", 0),
                            "timestamp": message.get("timestamp", 0),
                            "valid": True
                        }
                        logger.debug(f"收到电池状态: {_battery_status_cache}")
                except Exception as e:
                    logger.warning(f"电池订阅错误: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"电池订阅线程异常: {e}")
        finally:
            socket.close()
            context.term()
    
    # 启动订阅线程
    _battery_subscriber_thread = threading.Thread(target=subscriber_loop, daemon=True)
    _battery_subscriber_thread.start()
    time.sleep(0.5)  # 给线程启动时间


def _get_battery_status(timeout_ms: int = 2000) -> dict:
    """获取电池状态（优先从缓存获取，缓存不存在则尝试订阅获取）
    
    Args:
        timeout_ms: 等待超时时间（毫秒）
        
    Returns:
        电池状态信息字典
    """
    global _battery_status_cache
    
    # 首先检查缓存（60秒内的数据都有效）
    current_time = time.time()
    if (_battery_status_cache.get("valid") and 
        (current_time - _battery_status_cache.get("timestamp", 0)) < 60):
        return _battery_status_cache
    
    # 缓存无效，启动后台订阅线程
    try:
        _start_battery_subscriber()
    except Exception as e:
        logger.warning(f"启动电池订阅线程失败: {e}")
    
    # 尝试直接获取（同步方式）
    try:
        config = get_config()
        battery_addr = config.battery.pub_addr.replace("*", "localhost")
        
        # 创建新的 Context（避免与主线程冲突）
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        socket.connect(battery_addr)
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        try:
            # 尝试接收一条消息
            message = socket.recv_json()
            if message.get("type") == "sensor.battery":
                data = message.get("data", {})
                result = {
                    "voltage": data.get("voltage", 0),
                    "percentage": data.get("percentage", 0),
                    "status": data.get("status", "unknown"),
                    "temperature": data.get("temperature"),
                    "servo_id": data.get("servo_id", 0),
                    "timestamp": message.get("timestamp", 0),
                    "valid": True
                }
                # 更新缓存
                _battery_status_cache = result
                return result
        except zmq.Again:
            pass
        finally:
            socket.close()
            context.term()
            
    except Exception as e:
        logger.warning(f"获取电池状态失败: {e}")
    
    # 如果缓存有数据（即使超时了），返回缓存
    if _battery_status_cache.get("valid"):
        return {
            **_battery_status_cache,
            "note": "使用缓存数据（可能不是最新的）"
        }
    
    # 完全无法获取
    return {
        "status": "unknown",
        "note": "未收到电池状态数据，请确保底盘服务已启动",
        "valid": False
    }


@mcp.tool
def get_battery_status() -> dict:
    """获取机器人电池状态
    
    当用户询问"电池电量多少"、"还剩多少电"、"电压多少"等时调用此工具。
    
    Returns:
        电池状态信息，包含电压、电量百分比、状态等
    """
    try:
        battery_info = _get_battery_status(timeout_ms=3000)
        
        if battery_info.get("valid"):
            voltage = battery_info.get("voltage", 0)
            percentage = battery_info.get("percentage", 0)
            status = battery_info.get("status", "unknown")
            temperature = battery_info.get("temperature")
            
            # 构建用户友好的消息
            status_map = {
                "normal": "正常",
                "low": "低电量",
                "critical": "电量严重不足",
                "charging": "充电中",
                "unknown": "未知"
            }
            status_text = status_map.get(status, status)
            
            message = f"当前电池电压{voltage:.1f}伏，电量{percentage:.0f}%，状态{status_text}"
            if temperature is not None:
                message += f"，舵机温度{temperature}度"
            
            return {
                "status": "success",
                "message": message,
                "data": battery_info
            }
        else:
            return {
                "status": "error",
                "message": "无法获取电池状态，请确保底盘服务已启动",
                "data": battery_info
            }
            
    except Exception as e:
        logger.error(f"获取电池状态失败: {e}")
        return {
            "status": "error",
            "message": f"获取电池状态失败: {e}",
            "data": {"valid": False}
        }


@mcp.tool
def reset_arm() -> dict:
    """机械臂复位，恢复到初始姿态
    
    将机械臂移动到配置文件中定义的休息位置（rest_position）。
    这是机械臂的安全初始姿态，适用于启动或任务完成后。
    
    Returns:
        复位执行结果
    """
    try:
        controller = get_controller()
        
        # 从配置读取休息位置
        from configs.config import get_config
        config = get_config()
        rest_position = config.arm.rest_position
        
        logger.info(f"机械臂复位到初始姿态: {rest_position}")
        
        # 发送关节命令
        result = controller.send_arm_joints(rest_position, speed=800)
        
        if result.get("status") == "success":
            # 更新当前位置记录（通过正运动学计算）
            global _current_arm_pos, _current_base_angle
            kin = _get_kinematics()
            r, z = kin.forward_kinematics(
                rest_position.get("shoulder", 0),
                rest_position.get("elbow", 0)
            )
            _current_arm_pos["r"] = r
            _current_arm_pos["z"] = z
            _current_base_angle = rest_position.get("base", 0)
            
            return {
                "status": "success",
                "message": "机械臂已复位到初始姿态"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"机械臂复位失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def move_arm_to_position(joint_angles: dict, speed: int = 800) -> dict:
    """控制机械臂移动到指定关节角度位置
    
    控制机械臂的各个关节移动到指定的角度位置。支持设置基座、肩关节、
    肘关节、腕关节和夹爪的角度。
    
    Args:
        joint_angles: 关节角度字典，如 {"base": 0, "shoulder": 45, "elbow": 90, 
                     "wrist_flex": 0, "wrist_roll": 0, "gripper": 45}
        speed: 运动速度，范围 100-2000，默认 800
    
    Returns:
        动作执行结果
    """
    try:
        controller = get_controller()
        config = get_config()
        
        # 验证关节名称并限制角度范围
        valid_joints = ["base", "shoulder", "elbow", "wrist_flex", "wrist_roll", "gripper"]
        filtered_angles = {}
        
        for joint, angle in joint_angles.items():
            if joint not in valid_joints:
                return {
                    "status": "error",
                    "message": f"未知的关节名称: {joint}，有效关节: {valid_joints}"
                }
            
            # 限制角度在有效范围内
            if joint in config.arm.joint_limits:
                min_angle, max_angle = config.arm.joint_limits[joint]
                angle = max(min_angle, min(max_angle, angle))
            
            filtered_angles[joint] = angle
        
        if not filtered_angles:
            return {
                "status": "error",
                "message": "未提供有效的关节角度"
            }
        
        logger.info(f"移动机械臂到位置: {filtered_angles}, 速度: {speed}")
        
        # 发送关节命令
        result = controller.send_arm_joints(filtered_angles, speed=speed)
        
        if result.get("status") == "success":
            # 更新当前位置记录
            global _current_arm_pos, _current_base_angle
            
            # 如果包含肩关节和肘关节角度，更新位置记录
            if "shoulder" in filtered_angles and "elbow" in filtered_angles:
                kin = _get_kinematics()
                r, z = kin.forward_kinematics(
                    filtered_angles.get("shoulder", 0),
                    filtered_angles.get("elbow", 0)
                )
                _current_arm_pos["r"] = r
                _current_arm_pos["z"] = z
            
            # 更新基座角度
            if "base" in filtered_angles:
                _current_base_angle = filtered_angles["base"]
            
            joint_desc = ", ".join([f"{k}={v}°" for k, v in filtered_angles.items()])
            return {
                "status": "success",
                "message": f"机械臂已移动到指定位置: {joint_desc}"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"移动机械臂失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def grab_object(gripper_angle: float = 0.0) -> dict:
    """控制机械臂夹爪执行抓取动作（闭合夹爪）
    
    控制机械臂的夹爪闭合以抓取物体。可以通过 gripper_angle 参数
    指定夹爪的闭合程度。
    
    Args:
        gripper_angle: 夹爪闭合角度，单位：度，范围 0-45，默认 0（完全闭合）
    
    Returns:
        抓取结果
    """
    try:
        controller = get_controller()
        config = get_config()
        
        # 限制角度范围在 0-45 度之间（半闭合，适合抓取）
        gripper_angle = max(0.0, min(45.0, gripper_angle))
        
        logger.info(f"执行抓取动作，夹爪角度: {gripper_angle}")
        
        # 发送夹爪命令
        joint_angles = {"gripper": gripper_angle}
        result = controller.send_arm_joints(joint_angles, speed=800)
        
        if result.get("status") == "success":
            return {
                "status": "success",
                "message": f"夹爪已闭合到 {gripper_angle} 度，抓取完成"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"抓取动作失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def release_object(gripper_angle: float = 90.0) -> dict:
    """控制机械臂夹爪执行释放动作（打开夹爪）
    
    控制机械臂的夹爪打开放开物体。可以通过 gripper_angle 参数
    指定夹爪的打开程度。
    
    Args:
        gripper_angle: 夹爪打开角度，单位：度，范围 45-90，默认 90（完全打开）
    
    Returns:
        释放结果
    """
    try:
        controller = get_controller()
        config = get_config()
        
        # 限制角度范围在 45-90 度之间
        gripper_angle = max(45.0, min(90.0, gripper_angle))
        
        logger.info(f"执行释放动作，夹爪角度: {gripper_angle}")
        
        # 发送夹爪命令
        joint_angles = {"gripper": gripper_angle}
        result = controller.send_arm_joints(joint_angles, speed=800)
        
        if result.get("status") == "success":
            return {
                "status": "success",
                "message": f"夹爪已打开到 {gripper_angle} 度，释放完成"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"释放动作失败: {e}")
        return {"status": "error", "message": str(e)}


# 机械臂运动学实例（从配置读取连杆长度）
_arm_kinematics = None

def _get_kinematics():
    """获取运动学实例（延迟初始化，从配置读取连杆长度）"""
    global _arm_kinematics
    if _arm_kinematics is None:
        from hal.arm.Kinematics import ArmKinematics
        from configs.config import get_config
        config = get_config()
        _arm_kinematics = ArmKinematics(
            L1=config.arm.upper_arm_length,
            L2=config.arm.forearm_length
        )
    return _arm_kinematics


def _init_arm_position() -> tuple:
    """初始化机械臂位置 - 通过正运动学计算当前实际位置
    
    Returns:
        tuple: (arm_pos_dict, base_angle)
               arm_pos_dict: {"r": 水平距离, "z": 垂直高度} 单位 mm
               base_angle: 基座角度 单位度
    """
    try:
        controller = get_controller()
        joint_states = controller.get_arm_joint_states()
        
        if joint_states and "shoulder" in joint_states and "elbow" in joint_states:
            # 从实际关节角度通过正运动学计算末端位置
            kin = _get_kinematics()
            shoulder_angle = joint_states.get("shoulder", 0)
            elbow_angle = joint_states.get("elbow", 0)
            r, z = kin.forward_kinematics(shoulder_angle, elbow_angle)
            base_angle = joint_states.get("base", 0)
            
            logger.info(f"机械臂初始位置(正运动学计算): r={r:.1f}mm, z={z:.1f}mm, base={base_angle:.1f}°")
            return {"r": r, "z": z}, base_angle
        else:
            # 无法获取实际角度，使用配置的休息位置计算
            from configs.config import get_config
            config = get_config()
            rest_position = config.arm.rest_position
            
            kin = _get_kinematics()
            shoulder_angle = rest_position.get("shoulder", 0)
            elbow_angle = rest_position.get("elbow", 0)
            r, z = kin.forward_kinematics(shoulder_angle, elbow_angle)
            base_angle = rest_position.get("base", 0)
            
            logger.info(f"机械臂初始位置(配置计算): r={r:.1f}mm, z={z:.1f}mm, base={base_angle:.1f}°")
            return {"r": r, "z": z}, base_angle
            
    except Exception as e:
        logger.error(f"初始化机械臂位置失败: {e}，使用默认值")
        # 使用硬编码默认值作为最后的回退
        return {"r": 150.0, "z": 150.0}, 0


# 当前机械臂末端位置（r 水平距离, z 垂直高度，单位：mm）
# 通过正运动学从实际关节角度计算初始位置
_current_arm_pos, _current_base_angle = _init_arm_position()


def _refresh_arm_position() -> bool:
    """刷新机械臂位置 - 从实际关节角度通过正运动学计算
    
    在每次运动前调用此函数，确保 _current_arm_pos 与实际机械臂状态同步
    
    Returns:
        bool: 是否成功刷新位置
    """
    global _current_arm_pos, _current_base_angle
    try:
        controller = get_controller()
        joint_states = controller.get_arm_joint_states()
        
        if joint_states and "shoulder" in joint_states and "elbow" in joint_states:
            kin = _get_kinematics()
            shoulder_angle = joint_states.get("shoulder", 0)
            elbow_angle = joint_states.get("elbow", 0)
            r, z = kin.forward_kinematics(shoulder_angle, elbow_angle)
            _current_arm_pos["r"] = r
            _current_arm_pos["z"] = z
            _current_base_angle = joint_states.get("base", 0)
            logger.debug(f"刷新机械臂位置: r={r:.1f}mm, z={z:.1f}mm, base={_current_base_angle:.1f}°")
            return True
        else:
            logger.warning("无法获取机械臂关节状态，使用缓存位置")
            return False
            
    except Exception as e:
        logger.warning(f"刷新机械臂位置失败: {e}，使用缓存位置")
        return False


@mcp.tool
def raise_arm(distance: float = 0.03) -> dict:
    """控制机械臂抬高（末端向上移动，Z方向）
    
    使用逆运动学计算关节角度，控制机械臂末端在垂直方向向上移动。
    
    Args:
        distance: 抬高距离，单位：米，范围 0.01-0.1，默认 0.03（3厘米）
    
    Returns:
        动作执行结果
    """
    try:
        controller = get_controller()
        kin = _get_kinematics()
        
        # 刷新当前位置（从实际关节角度同步）
        _refresh_arm_position()
        
        # 限制范围并转换为毫米
        distance_mm = max(0.01, min(0.1, distance)) * 1000
        
        # 计算新目标位置（Z方向增加）
        global _current_arm_pos
        target_r = _current_arm_pos["r"]
        target_z = _current_arm_pos["z"] + distance_mm
        
        # 使用逆运动学计算关节角度
        angles = kin.inverse_kinematics(target_r, target_z, elbow_up=True)
        if angles is None:
            return {
                "status": "error",
                "message": f"目标位置({target_r:.0f}, {target_z:.0f})mm 不可达"
            }
        
        shoulder_angle, elbow_angle = angles
        
        # 计算腕关节角度以保持末端水平（掌心始终向下）
        wrist_flex_angle = 180 - (shoulder_angle + elbow_angle)
        
        # 发送关节命令（包含 base 以保持基座角度，wrist_flex 以保持水平）
        global _current_base_angle
        joint_angles = {
            "base": _current_base_angle,
            "shoulder": shoulder_angle,
            "elbow": elbow_angle,
            "wrist_flex": wrist_flex_angle
        }
        result = controller.send_arm_joints(joint_angles)
        
        if result.get("status") == "success":
            _current_arm_pos["z"] = target_z  # 更新当前位置
            return {
                "status": "success",
                "message": f"机械臂已抬高 {distance*100:.0f} 厘米"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"抬高机械臂失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def lower_arm(distance: float = 0.03) -> dict:
    """控制机械臂放低（末端向下移动，Z方向）
    
    使用逆运动学计算关节角度，控制机械臂末端在垂直方向向下移动。
    
    Args:
        distance: 放低距离，单位：米，范围 0.01-0.1，默认 0.03（3厘米）
    
    Returns:
        动作执行结果
    """
    try:
        controller = get_controller()
        kin = _get_kinematics()
        
        # 刷新当前位置（从实际关节角度同步）
        _refresh_arm_position()
        
        # 限制范围并转换为毫米
        distance_mm = max(0.01, min(0.1, distance)) * 1000
        
        # 计算新目标位置（Z方向减少）
        global _current_arm_pos
        target_r = _current_arm_pos["r"]
        target_z = _current_arm_pos["z"] - distance_mm
        
        # 确保不碰到地面（至少20mm）
        target_z = max(20.0, target_z)
        
        # 使用逆运动学计算关节角度
        angles = kin.inverse_kinematics(target_r, target_z, elbow_up=True)
        if angles is None:
            return {
                "status": "error",
                "message": f"目标位置({target_r:.0f}, {target_z:.0f})mm 不可达"
            }
        
        shoulder_angle, elbow_angle = angles
        
        # 计算腕关节角度以保持末端水平（掌心始终向下）
        wrist_flex_angle = 180 - (shoulder_angle + elbow_angle)
        
        # 发送关节命令（包含 base 以保持基座角度，wrist_flex 以保持水平）
        global _current_base_angle
        joint_angles = {
            "base": _current_base_angle,
            "shoulder": shoulder_angle,
            "elbow": elbow_angle,
            "wrist_flex": wrist_flex_angle
        }
        result = controller.send_arm_joints(joint_angles)
        
        if result.get("status") == "success":
            _current_arm_pos["z"] = target_z  # 更新当前位置
            return {
                "status": "success",
                "message": f"机械臂已放低 {distance*100:.0f} 厘米"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"放低机械臂失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def extend_arm(distance: float = 0.03) -> dict:
    """控制机械臂前伸（末端向前移动，X方向）
    
    使用逆运动学计算关节角度，控制机械臂末端在水平方向向前伸展。
    
    Args:
        distance: 前伸距离，单位：米，范围 0.01-0.1，默认 0.03（3厘米）
    
    Returns:
        动作执行结果
    """
    try:
        controller = get_controller()
        kin = _get_kinematics()
        
        # 刷新当前位置（从实际关节角度同步）
        _refresh_arm_position()
        
        # 限制范围并转换为毫米
        distance_mm = max(0.01, min(0.1, distance)) * 1000
        
        # 计算新目标位置（r方向增加）
        global _current_arm_pos
        target_r = _current_arm_pos["r"] + distance_mm
        target_z = _current_arm_pos["z"]
        
        # 使用逆运动学计算关节角度
        angles = kin.inverse_kinematics(target_r, target_z, elbow_up=True)
        if angles is None:
            return {
                "status": "error",
                "message": f"目标位置({target_r:.0f}, {target_z:.0f})mm 不可达"
            }
        
        shoulder_angle, elbow_angle = angles
        
        # 计算腕关节角度以保持末端水平（掌心始终向下）
        wrist_flex_angle = 180 - (shoulder_angle + elbow_angle)
        
        # 发送关节命令（包含 base 以保持基座角度，wrist_flex 以保持水平）
        global _current_base_angle
        joint_angles = {
            "base": _current_base_angle,
            "shoulder": shoulder_angle,
            "elbow": elbow_angle,
            "wrist_flex": wrist_flex_angle
        }
        result = controller.send_arm_joints(joint_angles)
        
        if result.get("status") == "success":
            _current_arm_pos["r"] = target_r  # 更新当前位置
            return {
                "status": "success",
                "message": f"机械臂已前伸 {distance*100:.0f} 厘米"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"前伸机械臂失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def retract_arm(distance: float = 0.03) -> dict:
    """控制机械臂后退（末端向后移动，X方向）
    
    使用逆运动学计算关节角度，控制机械臂末端在水平方向向后收缩。
    
    Args:
        distance: 后退距离，单位：米，范围 0.01-0.1，默认 0.03（3厘米）
    
    Returns:
        动作执行结果
    """
    try:
        controller = get_controller()
        kin = _get_kinematics()
        
        # 刷新当前位置（从实际关节角度同步）
        _refresh_arm_position()
        
        # 限制范围并转换为毫米
        distance_mm = max(0.01, min(0.1, distance)) * 1000
        
        # 计算新目标位置（r方向减少）
        global _current_arm_pos
        target_r = _current_arm_pos["r"] - distance_mm
        target_z = _current_arm_pos["z"]
        
        # 确保不收缩过度（至少50mm）
        target_r = max(50.0, target_r)
        
        # 使用逆运动学计算关节角度
        angles = kin.inverse_kinematics(target_r, target_z, elbow_up=True)
        if angles is None:
            return {
                "status": "error",
                "message": f"目标位置({target_r:.0f}, {target_z:.0f})mm 不可达"
            }
        
        shoulder_angle, elbow_angle = angles
        
        # 计算腕关节角度以保持末端水平（掌心始终向下）
        wrist_flex_angle = 180 - (shoulder_angle + elbow_angle)
        
        # 发送关节命令（包含 base 以保持基座角度，wrist_flex 以保持水平）
        global _current_base_angle
        joint_angles = {
            "base": _current_base_angle,
            "shoulder": shoulder_angle,
            "elbow": elbow_angle,
            "wrist_flex": wrist_flex_angle
        }
        result = controller.send_arm_joints(joint_angles)
        
        if result.get("status") == "success":
            _current_arm_pos["r"] = target_r  # 更新当前位置
            return {
                "status": "success",
                "message": f"机械臂已后退 {distance*100:.0f} 厘米"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"后退机械臂失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def rotate_arm_left(degree: float = 30) -> dict:
    """控制机械臂基座左转（水平旋转）
    
    控制机械臂基座向左旋转，改变末端在水平面内的方向。
    
    Args:
        degree: 旋转角度，单位：度，范围 5-180，默认 30
    
    Returns:
        动作执行结果
    """
    try:
        controller = get_controller()
        
        # 刷新当前位置（从实际关节角度同步）
        _refresh_arm_position()
        
        # 限制范围
        degree = max(5, min(180, degree))
        
        global _current_base_angle
        target_angle = _current_base_angle - degree
        
        # 限制在 -180~180 范围内
        if target_angle > 180:
            target_angle = 180
        
        # 发送关节命令
        joint_angles = {
            "base": target_angle
        }
        result = controller.send_arm_joints(joint_angles)
        
        if result.get("status") == "success":
            _current_base_angle = target_angle  # 更新当前角度
            return {
                "status": "success",
                "message": f"机械臂已左转 {degree:.0f} 度"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"左转机械臂失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def rotate_arm_right(degree: float = 30) -> dict:
    """控制机械臂基座右转（水平旋转）
    
    控制机械臂基座向右旋转，改变末端在水平面内的方向。
    
    Args:
        degree: 旋转角度，单位：度，范围 5-180，默认 30
    
    Returns:
        动作执行结果
    """
    try:
        controller = get_controller()
        
        # 刷新当前位置（从实际关节角度同步）
        _refresh_arm_position()
        
        # 限制范围
        degree = max(5, min(180, degree))
        
        global _current_base_angle
        target_angle = _current_base_angle + degree
        
        # 限制在 -180~180 范围内
        if target_angle < -180:
            target_angle = -180
        
        # 发送关节命令
        joint_angles = {
            "base": target_angle
        }
        result = controller.send_arm_joints(joint_angles)
        
        if result.get("status") == "success":
            _current_base_angle = target_angle  # 更新当前角度
            return {
                "status": "success",
                "message": f"机械臂已右转 {degree:.0f} 度"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"右转机械臂失败: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool
def what_does_robot_see(prompt: str = "请描述这张图片的内容") -> dict:
    """让机器人观察当前画面并描述看到的内容
    
    当用户问"你看到了什么"、"前面有什么"、"描述一下周围环境"等
    与视觉相关的问题时，调用此工具获取画面描述。
    
    Args:
        prompt: 对图片的提问或指令，例如"描述这张图片的内容"、"图中有几个人"
    
    Returns:
        观察结果，包含画面描述或错误信息
    """
    try:
        logger.info(f"机器人视觉理解请求，提示词: {prompt}")
        
        # 导入 VisionAnalyzer
        try:
            from applications.vision_understanding.vision_analyzer import VisionAnalyzer
        except ImportError as e:
            logger.error(f"导入 VisionAnalyzer 失败: {e}")
            return {
                "status": "error",
                "message": "视觉理解模块未安装或不可用"
            }
        
        # 获取配置
        config = get_config()
        video_addr = config.zmq.vision_pub_addr.replace("*", "localhost")
        
        # 创建分析器并执行
        with VisionAnalyzer(video_addr=video_addr) as analyzer:
            result = analyzer.capture_and_analyze(prompt=prompt)
            
            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": result["description"],
                    "image_path": result.get("image_path", "")
                }
            else:
                return {
                    "status": "error",
                    "message": result.get("message", "视觉分析失败")
                }
                
    except Exception as e:
        logger.error(f"视觉理解失败: {e}")
        return {
            "status": "error",
            "message": f"视觉理解失败: {e}"
        }


# ==================== MCP 客户端集成 ====================

class MCPClientWrapper:
    """MCP 客户端包装器 - 供 DialogueManager 使用"""
    
    def __init__(self):
        self.tools = self._get_tools_schema()
    
    def _get_tools_schema(self) -> list:
        """获取工具列表（OpenAI Function Calling 格式）"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "move_forward",
                    "description": "控制机器人向前移动指定距离",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distance": {"type": "number", "description": "移动距离（米）"},
                            "speed": {"type": "number", "description": "移动速度（m/s）"}
                        },
                        "required": ["distance"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "move_backward",
                    "description": "控制机器人向后移动指定距离",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distance": {"type": "number", "description": "移动距离（米）"},
                            "speed": {"type": "number", "description": "移动速度（m/s）"}
                        },
                        "required": ["distance"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "turn_left",
                    "description": "控制机器人向左旋转指定角度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "angle": {"type": "number", "description": "旋转角度（度）"},
                            "speed": {"type": "number", "description": "旋转速度（rad/s）"}
                        },
                        "required": ["angle"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "turn_right",
                    "description": "控制机器人向右旋转指定角度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "angle": {"type": "number", "description": "旋转角度（度）"},
                            "speed": {"type": "number", "description": "旋转速度（rad/s）"}
                        },
                        "required": ["angle"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "stop_robot",
                    "description": "停止机器人当前动作",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_robot_status",
                    "description": "获取机器人当前状态",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_battery_status",
                    "description": "获取机器人电池状态。当用户询问'电池电量多少'、'还剩多少电'、'电压多少'等与电池相关的问题时调用此工具",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "what_does_robot_see",
                    "description": "让机器人观察当前画面并描述看到的内容。当用户问'你看到了什么'、'前面有什么'、'描述一下周围环境'等与视觉相关的问题时调用此工具",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "对图片的提问或指令，例如'描述这张图片的内容'、'图中有几个人'、'这是什么物体'"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "move_arm_to_position",
                    "description": "控制机械臂移动到指定关节角度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "joint_angles": {
                                "type": "object",
                                "description": "关节角度字典，如{\"base\":0, \"shoulder\":45, \"elbow\":90, \"wrist_flex\":0, \"wrist_roll\":0, \"gripper\":45}"
                            }
                        },
                        "required": ["joint_angles"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "grab_object",
                    "description": "控制机械臂执行抓取动作",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "release_object",
                    "description": "控制机械臂执行释放/松开动作",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "reset_arm",
                    "description": "机械臂复位，恢复到配置文件中定义的初始姿态（休息位置）",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "raise_arm",
                    "description": "控制机械臂末端抬高（向上移动，Z方向），使用逆运动学计算关节角度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distance": {"type": "number", "description": "抬高距离，单位：米，范围 0.01-0.1，默认 0.03（3厘米）"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "lower_arm",
                    "description": "控制机械臂末端放低（向下移动，Z方向），使用逆运动学计算关节角度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distance": {"type": "number", "description": "放低距离，单位：米，范围 0.01-0.1，默认 0.03（3厘米）"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "extend_arm",
                    "description": "控制机械臂末端前伸（向前移动，X方向），使用逆运动学计算关节角度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distance": {"type": "number", "description": "前伸距离，单位：米，范围 0.01-0.1，默认 0.03（3厘米）"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "retract_arm",
                    "description": "控制机械臂末端后退（向后移动，X方向），使用逆运动学计算关节角度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distance": {"type": "number", "description": "后退距离，单位：米，范围 0.01-0.1，默认 0.03（3厘米）"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rotate_arm_left",
                    "description": "控制机械臂基座左转（向左旋转）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "degree": {"type": "number", "description": "旋转角度，单位：度，范围 5-180，默认 30"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rotate_arm_right",
                    "description": "控制机械臂基座右转（向右旋转）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "degree": {"type": "number", "description": "旋转角度，单位：度，范围 5-180，默认 30"}
                        }
                    }
                }
            }
        ]
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用工具"""
        logger.info(f"MCP调用工具: {tool_name}, 参数: {arguments}")
        
        # 工具映射
        tool_map = {
            "move_forward": move_forward,
            "move_backward": move_backward,
            "turn_left": turn_left,
            "turn_right": turn_right,
            "stop_robot": stop_robot,
            "get_robot_status": get_robot_status,
            "get_battery_status": get_battery_status,
            "grab_object": grab_object,
            "release_object": release_object,
            "reset_arm": reset_arm,
            "what_does_robot_see": what_does_robot_see,
            "raise_arm": raise_arm,
            "lower_arm": lower_arm,
            "extend_arm": extend_arm,
            "retract_arm": retract_arm,
            "rotate_arm_left": rotate_arm_left,
            "rotate_arm_right": rotate_arm_right,
            "move_arm_to_position": move_arm_to_position,
        }
        
        if tool_name in tool_map:
            try:
                # 同步工具在异步环境中运行
                result = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: tool_map[tool_name](**arguments)
                )
                return result
            except Exception as e:
                logger.error(f"工具调用异常: {e}")
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "error", "message": f"未知工具: {tool_name}"}


def get_mcp_client():
    """获取 MCP 客户端实例（供 DialogueManager 使用）"""
    return MCPClientWrapper()


if __name__ == "__main__":
    # 运行 MCP 服务器，使用 STDIO 传输
    logger.info("启动 MCP 服务器...")
    mcp.run()
