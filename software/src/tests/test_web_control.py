"""
网页控制端测试 - 验证Web-ZeroMQ通信链路

测试内容:
1. 启动模拟仲裁器
2. 启动Web服务器
3. 测试SocketIO连接
4. 测试摇杆数据流向

运行方式:
    cd software/src
    python tests/test_web_control.py
"""
import sys
import os
import time
import json
import threading
import socket

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 使用TCP地址以便Windows测试
TEST_ARBITER_ADDR = "tcp://127.0.0.1:5556"
TEST_PUB_ADDR = "tcp://127.0.0.1:5557"
WEB_PORT = 5001


class MockArbiter:
    """模拟仲裁器 - 用于测试"""
    
    def __init__(self):
        self.commands = []
        self.running = False
        
    def start(self):
        """启动模拟仲裁器"""
        import zmq
        
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind(TEST_ARBITER_ADDR)
        
        pub_socket = context.socket(zmq.PUB)
        pub_socket.bind(TEST_PUB_ADDR)
        
        print("[MockArbiter] 模拟仲裁器已启动")
        print(f"[MockArbiter] REP: {TEST_ARBITER_ADDR}")
        print(f"[MockArbiter] PUB: {TEST_PUB_ADDR}")
        
        self.running = True
        
        while self.running:
            try:
                # 非阻塞接收
                request = socket.recv_json(flags=zmq.NOBLOCK)
                print(f"[MockArbiter] 收到指令: {request}")
                
                self.commands.append(request)
                
                # 响应
                response = {
                    "success": True,
                    "message": "测试接受",
                    "current_owner": "web",
                    "current_priority": 1
                }
                socket.send_json(response)
                
                # 发布到底盘
                pub_socket.send_json({
                    "vx": request.get("vx", 0),
                    "vy": request.get("vy", 0),
                    "vz": request.get("vz", 0),
                    "source": "web"
                })
                
            except zmq.Again:
                time.sleep(0.001)
            except Exception as e:
                print(f"[MockArbiter] 错误: {e}")
                
    def stop(self):
        self.running = False


def get_ip():
    """获取本机IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def test_web_control():
    """测试网页控制端"""
    print("=" * 60)
    print("HomeBot 网页控制端通信测试")
    print("=" * 60)
    print()
    
    # 步骤1: 启动模拟仲裁器
    print("[步骤1] 启动模拟仲裁器...")
    mock_arbiter = MockArbiter()
    arbiter_thread = threading.Thread(target=mock_arbiter.start, daemon=True)
    arbiter_thread.start()
    time.sleep(0.5)  # 等待仲裁器启动
    
    # 步骤2: 启动Web服务器
    print("[步骤2] 启动Web服务器...")
    
    # 延迟导入，避免全局初始化
    from applications.remote_control.web_server import app, socketio, ZMQBridge
    
    # 创建新的桥接器使用测试地址
    test_bridge = ZMQBridge(arbiter_addr=TEST_ARBITER_ADDR)
    
    web_thread = threading.Thread(
        target=lambda: socketio.run(
            app, 
            host='127.0.0.1', 
            port=WEB_PORT,
            debug=False, 
            use_reloader=False,
            allow_unsafe_werkzeug=True,
            log_output=False
        ),
        daemon=True
    )
    web_thread.start()
    time.sleep(1.0)  # 等待服务器启动
    
    ip = get_ip()
    print(f"[信息] Web服务器地址: http://{ip}:{WEB_PORT}")
    print()
    
    # 步骤3: 测试ZeroMQ桥接
    print("[步骤3] 测试ZeroMQ桥接通信...")
    
    if test_bridge.start():
        print("[OK] ZeroMQ桥接器启动成功")
    else:
        print("[FAIL] ZeroMQ桥接器启动失败")
        return
    
    # 发送测试指令
    print("[测试] 发送测试摇杆数据...")
    test_bridge.update_command(0.5, 0.0, 0.3)
    time.sleep(0.3)
    
    # 检查是否收到
    if len(mock_arbiter.commands) > 0:
        print(f"[OK] 仲裁器收到 {len(mock_arbiter.commands)} 条指令")
        print(f"  最新指令: {mock_arbiter.commands[-1]}")
    else:
        print("[FAIL] 未收到指令")
    
    # 发送更多测试数据
    print("[测试] 发送更多测试数据...")
    for i in range(5):
        test_bridge.update_command(0.2 * i, 0, 0.1 * i)
        time.sleep(0.1)
    
    time.sleep(0.2)
    print(f"[OK] 仲裁器总共收到 {len(mock_arbiter.commands)} 条指令")
    
    print()
    print("[步骤4] 手动测试指南:")
    print(f"  1. 在浏览器中打开: http://{ip}:{WEB_PORT}")
    print("  2. 观察控制台输出的摇杆数据")
    print("  3. 检查'仲裁器收到指令'确认链路正常")
    print()
    
    # 保持运行一段时间
    print("[信息] 测试服务器运行中，按Ctrl+C停止...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[信息] 测试结束")
    
    test_bridge.stop()
    mock_arbiter.stop()


if __name__ == '__main__':
    test_web_control()
