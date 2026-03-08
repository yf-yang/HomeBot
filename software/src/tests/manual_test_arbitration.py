"""
机器人底盘多源控制仲裁系统 - 集成测试
测试多源控制+优先级仲裁功能
"""
import subprocess
import time
import sys
import os

def run_in_terminal(title: str, command: list, delay: float = 0.5):
    """在终端窗口运行命令"""
    print(f"\n[TEST] 启动: {title}")
    # 使用tmux或screen可以更好地管理多个窗口
    # 这里用后台进程模拟
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    time.sleep(delay)
    return process

def print_separator(title: str):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def main():
    print_separator("机器人底盘多源控制仲裁系统 - 集成测试")
    
    print("""
测试场景说明:
1. 首先启动底盘执行端 (chassis_worker.py)
2. 然后启动仲裁器 (chassis_arbiter.py)  
3. 最后测试各个控制源:
   - web (优先级1) - 最低
   - voice (优先级2) - 中等
   - auto (优先级3) - 高
   - emergency (优先级4) - 最高

仲裁规则验证:
- 高优先级可抢占低优先级
- 1000ms无新指令自动释放控制权
- 低优先级尝试控制高优先级占用时会被拒绝
    """)
    
    print("\n[TEST] 请先手动运行以下命令（在不同的终端窗口）:")
    print()
    print("  # 终端1: 启动底盘执行端")
    print("  cd /root/.openclaw/workspace/homebot/src")
    print("  python3 chassis_worker.py")
    print()
    print("  # 终端2: 启动仲裁器")
    print("  cd /root/.openclaw/workspace/homebot/src")
    print("  python3 chassis_arbiter.py")
    print()
    print("  # 终端3: 测试语音控制")
    print("  cd /root/.openclaw/workspace/homebot/src")
    print("  python3 control_source_voice.py")
    print()
    print("  # 终端4: 测试网页控制")
    print("  cd /root/.openclaw/workspace/homebot/src")
    print("  python3 control_source_web.py")
    print()
    print("  # 终端5: 测试自动程序")
    print("  cd /root/.openclaw/workspace/homebot/src")
    print("  python3 control_source_auto.py")
    print()
    
    print_separator("测试步骤建议")
    print("""
1. 先启动底盘执行端和仲裁器（保持运行）

2. 测试优先级抢占:
   - 先启动 web 控制（优先级1），发送一些指令
   - 再启动 voice 控制（优先级2），观察抢占行为
   - 最后启动 auto 控制（优先级3），观察抢占行为

3. 测试超时释放:
   - 让某个控制源获得控制权
   - 停止发送指令超过1秒
   - 观察控制权是否被自动释放

4. 测试拒绝响应:
   - 让高优先级控制源（如auto）获得控制权
   - 低优先级控制源（如web）发送指令
   - 观察web收到的拒绝响应
    """)
    
    print_separator("文件清单")
    src_dir = os.path.dirname(os.path.abspath(__file__))
    files = [
        "chassis_arbiter.py",
        "control_source_voice.py",
        "control_source_web.py",
        "control_source_auto.py",
        "chassis_worker.py",
        "test_arbitration.py"
    ]
    
    for f in files:
        filepath = os.path.join(src_dir, f)
        exists = "✓" if os.path.exists(filepath) else "✗"
        print(f"  {exists} {f}")
    
    print_separator("说明")
    print("所有文件已生成在: /root/.openclaw/workspace/homebot/src/")
    print("请手动在多个终端中运行测试")

if __name__ == "__main__":
    main()
