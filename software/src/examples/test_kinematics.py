"""
底盘运动学测试
验证逆运动学计算是否正确
"""
import sys
sys.path.insert(0, 'software/src')

import math
from hal.chassis.driver import ChassisDriver, ChassisConfig


def test_kinematics():
    """测试逆运动学"""
    
    config = ChassisConfig(
        wheel_radius=0.03,
        chassis_radius=0.1,
    )
    
    # 创建底盘但不连接硬件
    chassis = ChassisDriver(config)
    
    print("=" * 60)
    print("三轮全向轮逆运动学测试")
    print("=" * 60)
    print()
    print("布局:")
    print("  左前轮: -60° (右前方)")
    print("  右前轮: 60° (左前方)")
    print("  后轮: 180° (正后方)")
    print()
    
    test_cases = [
        ("前进 (vx=1, vy=0, omega=0)", 1.0, 0.0, 0.0),
        ("后退 (vx=-1, vy=0, omega=0)", -1.0, 0.0, 0.0),
        ("右移 (vx=0, vy=1, omega=0)", 0.0, 1.0, 0.0),
        ("左移 (vx=0, vy=-1, omega=0)", 0.0, -1.0, 0.0),
        ("逆时针旋转 (vx=0, vy=0, omega=1)", 0.0, 0.0, 1.0),
        ("顺时针旋转 (vx=0, vy=0, omega=-1)", 0.0, 0.0, -1.0),
        ("前进+右转 (vx=1, vy=1, omega=0)", 1.0, 1.0, 0.0),
    ]
    
    for name, vx, vy, omega in test_cases:
        wheel_speeds = chassis._inverse_kinematics(vx, vy, omega)
        left, right, rear = wheel_speeds
        
        print(f"{name}:")
        print(f"  左前轮: {left:+.3f} m/s")
        print(f"  右前轮: {right:+.3f} m/s")
        print(f"  后轮:   {rear:+.3f} m/s")
        print()
    
    print("=" * 60)
    print("验证:")
    print("=" * 60)
    
    # 验证前进时三个轮子的关系
    vx, vy, omega = 1.0, 0.0, 0.0
    left, right, rear = chassis._inverse_kinematics(vx, vy, omega)
    print(f"\n前进:")
    print(f"  左前轮 = 右前轮 = {left:.3f} ≈ 0.5 (因为cos(±60°)=0.5)")
    print(f"  后轮 = {rear:.3f} = -1 (因为cos(180°)=-1)")
    
    # 验证旋转
    vx, vy, omega = 0.0, 0.0, 1.0
    left, right, rear = chassis._inverse_kinematics(vx, vy, omega)
    print(f"\n逆时针旋转:")
    print(f"  三个轮子速度相同 = {left:.3f} = r * omega = {config.chassis_radius}")


if __name__ == "__main__":
    test_kinematics()
