"""
机器人底盘多源控制仲裁系统 - 语音控制客户端
control_source_voice.py - 语音控制源（REQ socket）
优先级: 2
"""
import zmq
import time
import json
from typing import Dict, Any, Optional


class VoiceControlSource:
    """
    语音控制源客户端
    - 通过ZeroMQ REQ连接仲裁器
    - 发送速度指令并等待仲裁结果
    """
    
    SOURCE_NAME = "voice"
    PRIORITY = 2
    
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
            print(f"[VOICE] 已连接到仲裁器: {self.arbiter_addr}")
            return True
        except Exception as e:
            print(f"[VOICE] 连接失败: {e}")
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
            print(f"[VOICE] 发送指令: vx={vx}, vy={vy}, vz={vz}")
            
            # 等待响应（REQ-REP模式必须recv）
            response = self._socket.recv_json()
            print(f"[VOICE] 收到响应: {response}")
            
            return response
            
        except zmq.error.Again:
            print(f"[VOICE] 等待响应超时（{timeout_ms}ms）")
            # 超时后需要重新创建socket（REQ-REP状态机重置）
            self._reset_socket()
            return {
                "success": False,
                "message": f"等待响应超时（{timeout_ms}ms）",
                "current_owner": "unknown",
                "current_priority": 0
            }
        except Exception as e:
            print(f"[VOICE] 发送失败: {e}")
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
        print("[VOICE] 已断开连接")


def demo_voice_control():
    """
    语音控制演示
    模拟语音指令：前进、后退、左转、右转、停止
    """
    voice = VoiceControlSource()
    
    if not voice.connect():
        print("[VOICE] 无法连接到仲裁器，退出")
        return
    
    try:
        print("\n[VOICE] ========== 语音控制演示 ==========")
        print("[VOICE] 优先级: 2 (低于auto(3)，高于web(1))")
        print("[VOICE] 按Ctrl+C退出\n")
        
        # 模拟语音指令序列
        commands = [
            ("前进", 0.3, 0.0, 0.0),
            ("继续", 0.3, 0.0, 0.0),
            ("左转", 0.0, 0.0, 0.5),
            ("前进", 0.3, 0.0, 0.0),
            ("停止", 0.0, 0.0, 0.0),
        ]
        
        for i, (action, vx, vy, vz) in enumerate(commands):
            print(f"\n[VOICE] >>> 语音指令 [{i+1}/{len(commands)}]: {action}")
            response = voice.send_command(vx, vy, vz)
            
            if response["success"]:
                print(f"[VOICE] ✓ 指令执行成功")
            else:
                print(f"[VOICE] ✗ 指令被拒绝: {response['message']}")
            
            time.sleep(1.5)  # 语音指令间隔
            
    except KeyboardInterrupt:
        print("\n[VOICE] 用户中断")
    finally:
        voice.disconnect()


def main():
    demo_voice_control()


if __name__ == "__main__":
    main()
