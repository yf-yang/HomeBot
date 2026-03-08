"""
机器人底盘多源控制仲裁系统 - 仲裁核心服务
chassis_arbiter.py - 仲裁服务端（REP socket）
"""
import zmq
import time
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from threading import Lock


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


class ChassisArbiter:
    """
    底盘控制仲裁器
    - 接收多个控制源的REQ请求
    - 根据优先级仲裁决定控制权归属
    - 1000ms超时自动释放控制权
    """
    
    # 控制源优先级定义（数值越大优先级越高）
    PRIORITIES = {
        "emergency": 4,   # 急停 - 最高优先级
        "auto": 3,        # 自动程序
        "voice": 2,       # 语音控制
        "web": 1,         # 网页遥控 - 最低优先级
    }
    
    # 超时时间（毫秒）
    TIMEOUT_MS = 1000
    
    def __init__(self, 
                 rep_addr: str = "ipc:///tmp/chassis_arbiter.ipc",
                 pub_addr: str = "ipc:///tmp/chassis_final.ipc"):
        self.rep_addr = rep_addr
        self.pub_addr = pub_addr
        
        # 当前控制权状态
        self._current_owner: Optional[str] = None
        self._current_priority: int = 0
        self._last_command_time: float = 0.0
        self._last_vx: float = 0.0
        self._last_vy: float = 0.0
        self._last_vz: float = 0.0
        
        # 线程锁
        self._lock = Lock()
        
        # ZeroMQ上下文和套接字
        self._context: Optional[zmq.Context] = None
        self._rep_socket: Optional[zmq.Socket] = None
        self._pub_socket: Optional[zmq.Socket] = None
        
    def _check_timeout(self) -> None:
        """检查当前控制权是否超时，超时时释放控制权"""
        if self._current_owner is None:
            return
            
        elapsed_ms = (time.time() - self._last_command_time) * 1000
        if elapsed_ms > self.TIMEOUT_MS:
            # 超时释放控制权
            print(f"[ARBITER] 控制权超时释放: {self._current_owner} (已等待 {elapsed_ms:.0f}ms)")
            self._current_owner = None
            self._current_priority = 0
            self._last_vx = 0.0
            self._last_vy = 0.0
            self._last_vz = 0.0
    
    def _arbitrate(self, cmd: ControlCommand) -> ArbiterResponse:
        """
        仲裁核心逻辑
        - 检查超时
        - 根据优先级决定是否接受指令
        """
        with self._lock:
            # 1. 检查是否超时释放
            self._check_timeout()
            
            # 2. 获取新指令的优先级
            new_priority = cmd.priority
            
            # 3. 仲裁决策
            if self._current_owner is None:
                # 无人占用，直接接受
                self._current_owner = cmd.source
                self._current_priority = new_priority
                self._last_command_time = time.time()
                self._last_vx = cmd.vx
                self._last_vy = cmd.vy
                self._last_vz = cmd.vz
                
                # 发布到底盘
                self._publish_to_chassis(cmd)
                
                return ArbiterResponse(
                    success=True,
                    message=f"指令已接受，获得控制权",
                    current_owner=cmd.source,
                    current_priority=new_priority
                )
            
            elif new_priority >= self._current_priority:
                # 优先级足够（高优先级可抢占同优先级）
                old_owner = self._current_owner
                self._current_owner = cmd.source
                self._current_priority = new_priority
                self._last_command_time = time.time()
                self._last_vx = cmd.vx
                self._last_vy = cmd.vy
                self._last_vz = cmd.vz
                
                # 发布到底盘
                self._publish_to_chassis(cmd)
                
                if old_owner != cmd.source:
                    return ArbiterResponse(
                        success=True,
                        message=f"指令已接受，抢占控制权（原控制源: {old_owner}）",
                        current_owner=cmd.source,
                        current_priority=new_priority
                    )
                else:
                    return ArbiterResponse(
                        success=True,
                        message="指令已接受（续期控制权）",
                        current_owner=cmd.source,
                        current_priority=new_priority
                    )
            else:
                # 优先级不足，拒绝
                return ArbiterResponse(
                    success=False,
                    message=f"优先级不足，当前被 {self._current_owner} 占用",
                    current_owner=self._current_owner,
                    current_priority=self._current_priority
                )
    
    def _publish_to_chassis(self, cmd: ControlCommand) -> None:
        """将最终速度指令发布给底盘执行端"""
        if self._pub_socket:
            msg = {
                "vx": cmd.vx,
                "vy": cmd.vy,
                "vz": cmd.vz,
                "source": cmd.source,
                "priority": cmd.priority,
                "timestamp": time.time()
            }
            self._pub_socket.send_json(msg)
            print(f"[ARBITER] 发布到底盘: vx={cmd.vx}, vy={cmd.vy}, vz={cmd.vz}, source={cmd.source}")
    
    def _parse_request(self, data: Dict[str, Any]) -> Optional[ControlCommand]:
        """解析REQ请求数据"""
        try:
            source = data.get("source", "")
            vx = float(data.get("vx", 0.0))
            vy = float(data.get("vy", 0.0))
            vz = float(data.get("vz", 0.0))
            priority = int(data.get("priority", 0))
            
            # 如果没有提供priority，根据source查找
            if priority == 0 and source in self.PRIORITIES:
                priority = self.PRIORITIES[source]
            
            return ControlCommand(
                source=source,
                vx=vx,
                vy=vy,
                vz=vz,
                priority=priority,
                timestamp=time.time()
            )
        except (KeyError, ValueError, TypeError) as e:
            print(f"[ARBITER] 解析请求失败: {e}")
            return None
    
    def start(self) -> None:
        """启动仲裁服务"""
        self._context = zmq.Context()
        
        # 创建REP套接字（接收控制源请求）
        self._rep_socket = self._context.socket(zmq.REP)
        self._rep_socket.bind(self.rep_addr)
        
        # 创建PUB套接字（发布给底盘）
        self._pub_socket = self._context.socket(zmq.PUB)
        self._pub_socket.bind(self.pub_addr)
        
        print(f"[ARBITER] 仲裁器已启动")
        print(f"[ARBITER] REP地址: {self.rep_addr}")
        print(f"[ARBITER] PUB地址: {self.pub_addr}")
        print(f"[ARBITER] 优先级: emergency(4) > auto(3) > voice(2) > web(1)")
        print(f"[ARBITER] 超时时间: {self.TIMEOUT_MS}ms")
        print("[ARBITER] 等待控制源连接...")
        
        try:
            while True:
                # 接收请求（REQ-REP模式必须成对使用）
                try:
                    request_data = self._rep_socket.recv_json(flags=zmq.NOBLOCK)
                except zmq.Again:
                    # 无数据，短暂休眠后继续
                    time.sleep(0.001)
                    continue
                
                print(f"\n[ARBITER] 收到请求: {request_data}")
                
                # 解析请求
                cmd = self._parse_request(request_data)
                
                if cmd is None:
                    # 解析失败，返回错误
                    response = ArbiterResponse(
                        success=False,
                        message="请求格式错误",
                        current_owner=self._current_owner or "none",
                        current_priority=self._current_priority
                    )
                else:
                    # 执行仲裁
                    response = self._arbitrate(cmd)
                
                # 发送响应
                response_dict = asdict(response)
                self._rep_socket.send_json(response_dict)
                print(f"[ARBITER] 发送响应: {response_dict}")
                
        except KeyboardInterrupt:
            print("\n[ARBITER] 收到中断信号，正在关闭...")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """停止仲裁服务"""
        if self._rep_socket:
            self._rep_socket.close()
        if self._pub_socket:
            self._pub_socket.close()
        if self._context:
            self._context.term()
        print("[ARBITER] 仲裁器已关闭")


def main():
    arbiter = ChassisArbiter()
    arbiter.start()


if __name__ == "__main__":
    main()
