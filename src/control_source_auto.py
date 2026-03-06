"""
机器人底盘多源控制仲裁系统 - 自动程序控制客户端
control_source_auto.py - 自动程序控制源（REQ socket）
优先级: 3
"""
import zmq
import time
import math
from typing import Dict, Any, Optional, Callable


class AutoControlSource:
    """
    自动程序控制源客户端
    - 通过ZeroMQ REQ连接仲裁器
    - 发送速度指令并等待仲裁结果
    """
    
    SOURCE_NAME = "auto"
    PRIORITY = 3  # 高优先级，仅低于emergency
    
    def __init__(self, arbiter_addr: str = "ipc:///tmp/chassis_arbiter.ipc"):
        self.arbiter_addr = arbiter_addr
        self._context: Optional[zmq.Context] = None
        self._socket: Optional[zmq.Socket] = None
        self._connected = False
        
    def connect(self) -> bool:
        """连接仲裁器"""
        try:
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.REQ)
            self._socket.connect(self.arbiter_addr)
            self._connected = True
            print(f"[AUTO] 已连接到仲裁器: {self.arbiter_addr}")
            return True
        except Exception as e:
            print(f"[AUTO] 连接失败: {e}")
            return False
    
    def send_command(self, vx: float, vy: float, vz: float, timeout_ms: int = 100) -> Dict[str, Any]:
        """
        发送速度指令到仲裁器
        
        Args:
            vx: X方向速度 (m/s)
            vy: Y方向速度 (m/s)
            vz: Z方向角速度 (rad/s)
            timeout_ms: 等待响应超时时间（毫秒）
            
        Returns:
            仲裁器响应字典
        """
        if not self._connected or self._socket is None:
            return {
                "success": False,
                "message": "未连接到仲裁器",
                "current_owner": "unknown",
                "current_priority": 0
            }
        
        # 构建请求
        request = {
            "source": self.SOURCE_NAME,
            "vx": vx,
            "vy": vy,
            "vz": vz,
            "priority": self.PRIORITY
        }
        
        try:
            # 设置接收超时
            self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            
            # 发送请求
            self._socket.send_json(request)
            print(f"[AUTO] 发送指令: vx={vx:.2f}, vy={vy:.2f}, vz={vz:.2f}")
            
            # 等待响应（REQ-REP模式必须recv）
            response = self._socket.recv_json()
            print(f"[AUTO] 收到响应: {response}")
            
            return response
            
        except zmq.error.Again:
            print(f"[AUTO] 等待响应超时（{timeout_ms}ms）")
            self._reset_socket()
            return {
                "success": False,
                "message": f"等待响应超时（{timeout_ms}ms）",
                "current_owner": "unknown",
                "current_priority": 0
            }
        except Exception as e:
            print(f"[AUTO] 发送失败: {e}")
            return {
                "success": False,
                "message": f"发送失败: {str(e)}",
                "current_owner": "unknown",
                "current_priority": 0
            }
    
    def _reset_socket(self) -> None:
        """重置socket（超时后必须重置REQ-REP状态机）"""
        if self._socket:
            self._socket.close()
        self._socket = self._context.socket(zmq.REQ)
        self._socket.connect(self.arbiter_addr)
    
    def disconnect(self) -> None:
        """断开连接"""
        if self._socket:
            self._socket.close()
        if self._context:
            self._context.term()
        self._connected = False
        print("[AUTO] 已断开连接")


class AutoNavigation:
    """
    自动导航程序示例
    实现几种典型的自动行为模式
    """
    
    def __init__(self, control_source: AutoControlSource):
        self.ctrl = control_source
        self._running = False
    
    def move_forward(self, distance: float, speed: float = 0.3) -> bool:
        """
        向前移动指定距离
        
        Args:
            distance: 距离（米）
            speed: 速度（m/s）
        
        Returns:
            是否成功完成
        """
        duration = distance / abs(speed)
        print(f"[AUTO-NAV] 向前移动 {distance}m，速度 {speed}m/s，预计 {duration:.1f}s")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            response = self.ctrl.send_command(speed, 0.0, 0.0)
            if not response["success"]:
                print(f"[AUTO-NAV] 移动被中断: {response['message']}")
                return False
            time.sleep(0.1)  # 100ms 发送一次指令（保持控制权）
        
        # 停止
        self.ctrl.send_command(0.0, 0.0, 0.0)
        print(f"[AUTO-NAV] 向前移动完成")
        return True
    
    def rotate(self, angle_deg: float, angular_speed: float = 0.5) -> bool:
        """
        旋转指定角度
        
        Args:
            angle_deg: 角度（度，正为逆时针）
            angular_speed: 角速度（rad/s）
        
        Returns:
            是否成功完成
        """
        angle_rad = math.radians(angle_deg)
        duration = abs(angle_rad / angular_speed)
        vz = angular_speed if angle_deg > 0 else -angular_speed
        
        print(f"[AUTO-NAV] 旋转 {angle_deg}°，角速度 {vz}rad/s，预计 {duration:.1f}s")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            response = self.ctrl.send_command(0.0, 0.0, vz)
            if not response["success"]:
                print(f"[AUTO-NAV] 旋转被中断: {response['message']}")
                return False
            time.sleep(0.1)
        
        # 停止
        self.ctrl.send_command(0.0, 0.0, 0.0)
        print(f"[AUTO-NAV] 旋转完成")
        return True
    
    def square_path(self, side_length: float = 1.0) -> bool:
        """
        走正方形路径
        """
        print(f"[AUTO-NAV] 开始走正方形，边长 {side_length}m")
        
        for i in range(4):
            print(f"[AUTO-NAV] --- 边 {i+1}/4 ---")
            if not self.move_forward(side_length):
                return False
            if not self.rotate(90):
                return False
        
        print("[AUTO-NAV] 正方形路径完成")
        return True
    
    def stop(self) -> None:
        """停止运动"""
        self.ctrl.send_command(0.0, 0.0, 0.0)


def demo_auto_control():
    """
    自动程序控制演示
    演示自动导航功能
    """
    auto = AutoControlSource()
    
    if not auto.connect():
        print("[AUTO] 无法连接到仲裁器，退出")
        return
    
    try:
        print("\n[AUTO] ========== 自动程序控制演示 ==========")
        print("[AUTO] 优先级: 3 (高优先级，会抢占voice和web)")
        print("[AUTO] 按Ctrl+C退出\n")
        
        navigator = AutoNavigation(auto)
        
        # 演示：走正方形
        navigator.square_path(side_length=0.5)
        
        time.sleep(1.0)
        
        # 演示：向前移动
        navigator.move_forward(distance=0.3, speed=0.2)
        
        print("\n[AUTO] 演示完成")
        
    except KeyboardInterrupt:
        print("\n[AUTO] 用户中断")
        auto.send_command(0.0, 0.0, 0.0)  # 确保停止
    finally:
        auto.disconnect()


def main():
    demo_auto_control()


if __name__ == "__main__":
    main()
