"""
机器人底盘多源控制仲裁系统 - 网页控制客户端
control_source_web.py - 网页遥控控制源（REQ socket）
优先级: 1
"""
import zmq
import time
from typing import Dict, Any, Optional


class WebControlSource:
    """
    网页遥控控制源客户端
    - 通过ZeroMQ REQ连接仲裁器
    - 发送速度指令并等待仲裁结果
    """
    
    SOURCE_NAME = "web"
    PRIORITY = 1  # 最低优先级
    
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
            print(f"[WEB] 已连接到仲裁器: {self.arbiter_addr}")
            return True
        except Exception as e:
            print(f"[WEB] 连接失败: {e}")
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
            print(f"[WEB] 发送指令: vx={vx}, vy={vy}, vz={vz}")
            
            # 等待响应（REQ-REP模式必须recv）
            response = self._socket.recv_json()
            print(f"[WEB] 收到响应: {response}")
            
            return response
            
        except zmq.error.Again:
            print(f"[WEB] 等待响应超时（{timeout_ms}ms）")
            self._reset_socket()
            return {
                "success": False,
                "message": f"等待响应超时（{timeout_ms}ms）",
                "current_owner": "unknown",
                "current_priority": 0
            }
        except Exception as e:
            print(f"[WEB] 发送失败: {e}")
            return {
                "success": False,
                "message": f"发送失败: {str(e)}",
                "current_owner": "unknown",
                "current_priority": 0
            }
    
    def send_joystick_command(self, forward: float, lateral: float, rotate: float, 
                              speed_scale: float = 0.5) -> Dict[str, Any]:
        """
        发送虚拟摇杆指令
        
        Args:
            forward: 前后方向 (-1.0 ~ 1.0)
            lateral: 左右方向 (-1.0 ~ 1.0)
            rotate: 旋转方向 (-1.0 ~ 1.0)
            speed_scale: 速度缩放系数
        """
        vx = forward * speed_scale
        vy = lateral * speed_scale
        vz = rotate * speed_scale
        return self.send_command(vx, vy, vz)
    
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
        print("[WEB] 已断开连接")


def demo_web_control():
    """
    网页遥控演示
    模拟网页虚拟摇杆操作
    """
    web = WebControlSource()
    
    if not web.connect():
        print("[WEB] 无法连接到仲裁器，退出")
        return
    
    try:
        print("\n[WEB] ========== 网页遥控演示 ==========")
        print("[WEB] 优先级: 1 (最低，会被voice/auto/emergency抢占)")
        print("[WEB] 按Ctrl+C退出\n")
        
        # 模拟摇杆操作序列
        joystick_actions = [
            ("向前", 1.0, 0.0, 0.0),
            ("向前+左转", 1.0, 0.0, -0.5),
            ("原地右转", 0.0, 0.0, 0.8),
            ("停止", 0.0, 0.0, 0.0),
            ("向后", -0.5, 0.0, 0.0),
        ]
        
        for i, (action, fwd, lat, rot) in enumerate(joystick_actions):
            print(f"\n[WEB] >>> 摇杆操作 [{i+1}/{len(joystick_actions)}]: {action}")
            response = web.send_joystick_command(fwd, lat, rot)
            
            if response["success"]:
                print(f"[WEB] ✓ 摇杆指令执行成功")
            else:
                print(f"[WEB] ✗ 摇杆指令被拒绝: {response['message']}")
            
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\n[WEB] 用户中断")
    finally:
        web.disconnect()


def interactive_web_control():
    """
    交互式网页遥控
    通过键盘输入控制
    """
    web = WebControlSource()
    
    if not web.connect():
        print("[WEB] 无法连接到仲裁器，退出")
        return
    
    print("\n[WEB] ========== 交互式网页遥控 ==========")
    print("[WEB] 命令格式: forward lateral rotate (每个值范围 -1.0 ~ 1.0)")
    print("[WEB] 示例: 0.5 0 0 (向前)")
    print("[WEB] 示例: 0 0 0.5 (右转)")
    print("[WEB] 输入 'q' 退出\n")
    
    try:
        while True:
            cmd = input("[WEB] 输入指令 (fwd lat rot): ").strip()
            
            if cmd.lower() == 'q':
                break
            
            try:
                parts = cmd.split()
                if len(parts) != 3:
                    print("[WEB] 错误: 需要3个数值 (forward lateral rotate)")
                    continue
                
                fwd = float(parts[0])
                lat = float(parts[1])
                rot = float(parts[2])
                
                response = web.send_joystick_command(fwd, lat, rot)
                
                if response["success"]:
                    print(f"[WEB] ✓ 控制成功")
                else:
                    print(f"[WEB] ✗ 被拒绝: {response['message']}")
                    
            except ValueError:
                print("[WEB] 错误: 请输入有效数字")
                
    except KeyboardInterrupt:
        print("\n[WEB] 用户中断")
    finally:
        web.disconnect()


def main():
    # 默认运行演示模式
    demo_web_control()
    # 如需交互模式，取消下面注释:
    # interactive_web_control()


if __name__ == "__main__":
    main()
