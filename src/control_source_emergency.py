"""
机器人底盘多源控制仲裁系统 - 急停控制客户端
control_source_emergency.py - 急停控制源（REQ socket）
优先级: 4 (最高)
"""
import zmq
import time
from typing import Dict, Any, Optional


class EmergencyControlSource:
    """
    急停控制源客户端
    - 最高优先级，可抢占任何其他控制源
    - 用于紧急停止和安全保护
    """
    
    SOURCE_NAME = "emergency"
    PRIORITY = 4  # 最高优先级
    
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
            print(f"[EMERGENCY] 已连接到仲裁器: {self.arbiter_addr}")
            return True
        except Exception as e:
            print(f"[EMERGENCY] 连接失败: {e}")
            return False
    
    def send_command(self, vx: float, vy: float, vz: float, timeout_ms: int = 100) -> Dict[str, Any]:
        """发送速度指令到仲裁器"""
        if not self._connected or self._socket is None:
            return {
                "success": False,
                "message": "未连接到仲裁器",
                "current_owner": "unknown",
                "current_priority": 0
            }
        
        request = {
            "source": self.SOURCE_NAME,
            "vx": vx,
            "vy": vy,
            "vz": vz,
            "priority": self.PRIORITY
        }
        
        try:
            self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            self._socket.send_json(request)
            print(f"[EMERGENCY] 发送指令: vx={vx}, vy={vy}, vz={vz}")
            
            response = self._socket.recv_json()
            print(f"[EMERGENCY] 收到响应: {response}")
            return response
            
        except zmq.error.Again:
            print(f"[EMERGENCY] 等待响应超时（{timeout_ms}ms）")
            self._reset_socket()
            return {
                "success": False,
                "message": f"等待响应超时（{timeout_ms}ms）",
                "current_owner": "unknown",
                "current_priority": 0
            }
        except Exception as e:
            print(f"[EMERGENCY] 发送失败: {e}")
            return {
                "success": False,
                "message": f"发送失败: {str(e)}",
                "current_owner": "unknown",
                "current_priority": 0
            }
    
    def emergency_stop(self) -> Dict[str, Any]:
        """
        紧急停止
        最高优先级，可立即停止任何运动
        """
        print("\n[!] 触发紧急停止 [!]")
        return self.send_command(0.0, 0.0, 0.0)
    
    def _reset_socket(self) -> None:
        """重置socket"""
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
        print("[EMERGENCY] 已断开连接")


def demo_emergency():
    """急停演示"""
    emergency = EmergencyControlSource()
    
    if not emergency.connect():
        print("[EMERGENCY] 无法连接到仲裁器，退出")
        return
    
    try:
        print("\n[EMERGENCY] ========== 急停控制演示 ==========")
        print("[EMERGENCY] 优先级: 4 (最高，可抢占任何控制源)")
        print("[EMERGENCY] 按Ctrl+C退出\n")
        
        # 演示急停
        response = emergency.emergency_stop()
        
        if response["success"]:
            print("[EMERGENCY] ✓ 急停成功执行")
        else:
            print(f"[EMERGENCY] ✗ 急停失败: {response['message']}")
            
    except KeyboardInterrupt:
        print("\n[EMERGENCY] 用户中断")
    finally:
        emergency.disconnect()


if __name__ == "__main__":
    demo_emergency()
