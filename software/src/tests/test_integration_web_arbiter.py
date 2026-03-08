"""
集成测试 - 网页控制端 + 真实仲裁器

测试Web控制端与真实ChassisArbiter的完整通信链路

运行方式:
    cd software/src
    python tests/test_integration_web_arbiter.py
"""
import sys
import os
import time
import threading
import socket

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.motion_service.chassis_arbiter.arbiter import ChassisArbiter


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


def test_integration():
    """集成测试：同时启动仲裁器和Web服务器"""
    print("=" * 70)
    print("HomeBot 集成测试 - 网页控制端 + 真实仲裁器")
    print("=" * 70)
    print()
    
    # 使用TCP地址（跨平台兼容）
    rep_addr = "tcp://127.0.0.1:5556"
    pub_addr = "tcp://127.0.0.1:5557"
    web_port = 5001
    print(f"[配置] 仲裁器REP: {rep_addr}")
    print(f"[配置] 仲裁器PUB: {pub_addr}")
    print(f"[配置] Web端口: {web_port}")
    print()
    
    # 步骤1: 启动真实仲裁器
    print("[步骤1] 启动真实仲裁器...")
    arbiter = ChassisArbiter(rep_addr=rep_addr, pub_addr=pub_addr)
    arbiter_thread = threading.Thread(target=arbiter.start, daemon=True)
    arbiter_thread.start()
    
    # 等待仲裁器启动
    time.sleep(1.0)
    print("[OK] 仲裁器已启动")
    print()
    
    # 步骤2: 启动Web控制端
    print("[步骤2] 启动Web控制端...")
    
    # 延迟导入以避免循环导入
    from applications.remote_control.web_server import app, socketio, ZMQBridge
    
    # 创建使用真实仲裁器地址的桥接器
    zmq_bridge = ZMQBridge(arbiter_addr=rep_addr)
    
    # 启动桥接器
    if zmq_bridge.start():
        print("[OK] ZeroMQ桥接器已启动")
    else:
        print("[FAIL] ZeroMQ桥接器启动失败")
        return
    
    # 启动Web服务器（在后台线程）
    web_thread = threading.Thread(
        target=lambda: socketio.run(
            app,
            host='0.0.0.0',
            port=web_port,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
            log_output=False
        ),
        daemon=True
    )
    web_thread.start()
    time.sleep(1.0)
    
    ip = get_ip()
    print(f"[OK] Web服务器已启动")
    print()
    
    # 步骤3: 测试数据流
    print("[步骤3] 测试数据流...")
    print("[测试] 模拟摇杆数据发送...")
    
    # 模拟摇杆数据
    test_commands = [
        (0.0, 0.0, 0.0),   # 停止
        (0.5, 0.0, 0.0),   # 前进
        (0.5, 0.0, 0.3),   # 前进+右转
        (0.0, 0.0, 0.5),   # 原地右转
        (-0.3, 0.0, 0.0),  # 后退
        (0.0, 0.0, 0.0),   # 停止
    ]
    
    for i, (vx, vy, vz) in enumerate(test_commands):
        zmq_bridge.update_command(vx, vy, vz)
        time.sleep(0.2)
        print(f"  指令 {i+1}: vx={vx:+.2f}, vz={vz:+.2f}")
    
    # 等待仲裁器处理
    time.sleep(0.5)
    
    print()
    print("[OK] 数据流测试完成")
    print()
    
    # 显示访问信息
    print("=" * 70)
    print("集成测试环境已启动！")
    print("=" * 70)
    print()
    print(f"📱 手机访问地址: http://{ip}:{web_port}")
    print(f"💻 本机访问地址: http://127.0.0.1:{web_port}")
    print()
    print("测试步骤:")
    print("  1. 在手机/电脑浏览器打开上述地址")
    print("  2. 检查页面顶部两个指示灯是否变绿")
    print("  3. 操作左手摇杆，观察控制台输出的底盘指令")
    print("  4. 点击'紧急停止'按钮测试停止功能")
    print()
    print("按 Ctrl+C 停止测试")
    print("=" * 70)
    
    # 保持运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[停止] 正在关闭...")
    
    # 清理
    zmq_bridge.stop()
    arbiter.stop()
    print("[OK] 测试结束")


if __name__ == '__main__':
    test_integration()
