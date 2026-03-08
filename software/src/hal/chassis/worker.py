"""
机器人底盘多源控制仲裁系统 - 底盘执行端
chassis_worker.py - 底盘执行端（SUB socket）
只接收仲裁器发出的最终速度指令
"""
import zmq
import time
import json
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass


@dataclass
class ChassisCommand:
    """底盘指令数据结构"""
    vx: float
    vy: float
    vz: float
    source: str
    priority: int
    timestamp: float


class ChassisWorker:
    """
    底盘执行端
    - 通过ZeroMQ SUB接收仲裁器发布的最终指令
    - 将速度指令转换为底层电机控制
    - 只执行仲裁器输出的唯一指令，避免多源冲突
    """
    
    def __init__(self, 
                 pub_addr: str = "ipc:///tmp/chassis_final.ipc",
                 on_command: Optional[Callable[[ChassisCommand], None]] = None):
        self.pub_addr = pub_addr
        self._on_command = on_command
        self._context: Optional[zmq.Context] = None
        self._socket: Optional[zmq.Socket] = None
        self._running = False
        
        # 当前执行状态
        self._current_vx = 0.0
        self._current_vy = 0.0
        self._current_vz = 0.0
        self._last_source = "none"
        self._last_priority = 0
        
    def connect(self) -> bool:
        """连接仲裁器的PUB端"""
        try:
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.SUB)
            self._socket.connect(self.pub_addr)
            # 订阅所有消息
            self._socket.setsockopt_string(zmq.SUBSCRIBE, "")
            print(f"[CHASSIS] 已连接到仲裁器PUB: {self.pub_addr}")
            return True
        except Exception as e:
            print(f"[CHASSIS] 连接失败: {e}")
            return False
    
    def _parse_command(self, data: Dict[str, Any]) -> Optional[ChassisCommand]:
        """解析指令数据"""
        try:
            return ChassisCommand(
                vx=float(data.get("vx", 0.0)),
                vy=float(data.get("vy", 0.0)),
                vz=float(data.get("vz", 0.0)),
                source=data.get("source", "unknown"),
                priority=int(data.get("priority", 0)),
                timestamp=float(data.get("timestamp", 0.0))
            )
        except (KeyError, ValueError, TypeError) as e:
            print(f"[CHASSIS] 解析指令失败: {e}")
            return None
    
    def _execute_command(self, cmd: ChassisCommand) -> None:
        """
        执行速度指令
        这里应该调用实际的底盘驱动API
        """
        self._current_vx = cmd.vx
        self._current_vy = cmd.vy
        self._current_vz = cmd.vz
        self._last_source = cmd.source
        self._last_priority = cmd.priority
        
        # 调用回调函数（如果提供）
        if self._on_command:
            self._on_command(cmd)
        
        # 打印执行信息
        print(f"[CHASSIS] 执行指令: vx={cmd.vx:+.2f}, vy={cmd.vy:+.2f}, vz={cmd.vz:+.2f} "
              f"[from {cmd.source}({cmd.priority})]")
    
    def run(self) -> None:
        """
        运行底盘执行循环
        持续接收仲裁器发布的指令并执行
        """
        if not self.connect():
            print("[CHASSIS] 无法连接到仲裁器，退出")
            return
        
        self._running = True
        print("\n[CHASSIS] ========== 底盘执行端已启动 ==========")
        print("[CHASSIS] 只接收仲裁器发布的最终指令")
        print("[CHASSIS] 按Ctrl+C停止\n")
        
        try:
            while self._running:
                try:
                    # 非阻塞接收
                    data = self._socket.recv_json(flags=zmq.NOBLOCK)
                    cmd = self._parse_command(data)
                    if cmd:
                        self._execute_command(cmd)
                except zmq.Again:
                    # 无数据，短暂休眠
                    time.sleep(0.001)
                    continue
                    
        except KeyboardInterrupt:
            print("\n[CHASSIS] 收到中断信号")
        finally:
            self.stop()
    
    def run_once(self, timeout_ms: int = 100) -> Optional[ChassisCommand]:
        """
        执行一次接收（用于测试）
        
        Args:
            timeout_ms: 超时时间（毫秒）
            
        Returns:
            接收到的指令，超时返回None
        """
        if not self._socket:
            if not self.connect():
                return None
        
        self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        
        try:
            data = self._socket.recv_json()
            cmd = self._parse_command(data)
            if cmd:
                self._execute_command(cmd)
            return cmd
        except zmq.Again:
            return None
    
    def stop(self) -> None:
        """停止底盘执行"""
        self._running = False
        # 发送停止指令到底层驱动
        self._send_stop_to_hardware()
        
        if self._socket:
            self._socket.close()
        if self._context:
            self._context.term()
        print("[CHASSIS] 底盘执行端已停止")
    
    def _send_stop_to_hardware(self) -> None:
        """向底层硬件发送停止指令"""
        print("[CHASSIS] 向硬件发送停止指令: vx=0, vy=0, vz=0")
        # 这里应该调用实际的底盘驱动API
        # 例如: self.chassis_driver.set_velocity(0, 0, 0)
    
    def get_current_state(self) -> Dict[str, Any]:
        """获取当前执行状态"""
        return {
            "vx": self._current_vx,
            "vy": self._current_vy,
            "vz": self._current_vz,
            "source": self._last_source,
            "priority": self._last_priority
        }


class SimulatedChassisDriver:
    """
    模拟底盘驱动（用于测试）
    实际项目中应替换为真实底盘驱动
    """
    
    def __init__(self):
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
    
    def set_velocity(self, vx: float, vy: float, vz: float) -> None:
        """设置底盘速度"""
        self.vx = vx
        self.vy = vy
        self.vz = vz
        print(f"[DRIVER] 电机速度更新: vx={vx:.3f}, vy={vy:.3f}, vz={vz:.3f}")


def on_chassis_command(cmd: ChassisCommand) -> None:
    """
    底盘指令回调函数
    这里可以接入实际的底盘驱动
    """
    # 创建模拟驱动实例
    driver = SimulatedChassisDriver()
    # 更新电机速度
    driver.set_velocity(cmd.vx, cmd.vy, cmd.vz)


def main():
    """底盘执行端主程序"""
    worker = ChassisWorker(on_command=on_chassis_command)
    worker.run()


if __name__ == "__main__":
    main()
