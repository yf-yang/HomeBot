"""
飞特舵机驱动示例
展示如何使用底盘和机械臂驱动
"""
import time

from hal.chassis import ChassisDriver, ChassisConfig
from hal.arm import ArmDriver, ArmConfig


def demo_chassis():
    """底盘运动演示"""
    print("=" * 50)
    print("底盘控制演示")
    print("=" * 50)

    # 创建底盘配置（可根据实际硬件修改）
    config = ChassisConfig(
        left_front_id=7,
        right_front_id=9,
        rear_id=8,
        # port="/dev/ttyUSB0",  # Linux
        port="COM15",        # Windows
    )

    # 创建并初始化底盘
    chassis = ChassisDriver(config)
    if not chassis.initialize():
        print("底盘初始化失败")
        return

    try:
        # 前进 0.5米
        # print("\n[Demo] 前进 0.5米")
        # chassis.move_forward(0.5)
        # time.sleep(1)

        # 旋转 90度
        print("\n[Demo] 顺时针旋转 90度")
        chassis.rotate(90)
        time.sleep(1)
        chassis.rotate(-90)

        # # 速度控制示例
        # print("\n[Demo] 速度控制: vx=0.2, vy=0, omega=0")
        # chassis.set_velocity(0.2, 0, 0)
        # time.sleep(2)

        # print("\n[Demo] 速度控制: vx=0, vy=0.1, omega=0.5")
        # chassis.set_velocity(0, 0.1, 0.5)
        # time.sleep(2)

        # 停止
        print("\n[Demo] 停止")
        chassis.stop()

    finally:
        chassis.close()


def demo_arm():
    """机械臂运动演示"""
    print("\n" + "=" * 50)
    print("机械臂控制演示")
    print("=" * 50)

    # 创建机械臂配置
    config = ArmConfig(
        joint_ids={
            "waist": 4,
            "shoulder": 5,
            "elbow": 6,
            "wrist": 7,
            "gripper": 8,
        },
        port="/dev/ttyUSB0",
        # port="COM1",
    )

    # 创建并初始化机械臂
    arm = ArmDriver(config)
    if not arm.initialize():
        print("机械臂初始化失败")
        return

    try:
        # 读取当前位置
        print("\n[Demo] 当前关节角度:")
        angles = arm.get_all_joint_angles()
        for joint, angle in angles.items():
            print(f"  {joint}: {angle:.1f}°")

        # 单关节控制
        print("\n[Demo] 设置 waist = 45°")
        arm.set_joint_angle("waist", 45, wait=True)
        time.sleep(0.5)

        print("\n[Demo] 设置 shoulder = 30°")
        arm.set_joint_angle("shoulder", 30, wait=True)
        time.sleep(0.5)

        # 多关节同步控制
        print("\n[Demo] 同步设置多个关节")
        arm.set_joint_angles({
            "elbow": 60,
            "wrist": -20,
        }, wait=True)
        time.sleep(0.5)

        # 夹爪控制
        print("\n[Demo] 打开夹爪")
        arm.open_gripper()
        time.sleep(1)

        print("\n[Demo] 关闭夹爪")
        arm.close_gripper()
        time.sleep(1)

        # 回到初始位置
        print("\n[Demo] 回到初始位置")
        arm.move_to_home()

    finally:
        arm.close()


def demo_combined():
    """底盘+机械臂组合演示"""
    print("\n" + "=" * 50)
    print("组合控制演示")
    print("=" * 50)

    # 注意：实际使用时底盘和机械臂可能需要分开两个串口
    # 这里假设它们共用同一个总线

    chassis_config = ChassisConfig(port="/dev/ttyUSB0")
    arm_config = ArmConfig(port="/dev/ttyUSB0")

    chassis = ChassisDriver(chassis_config)
    arm = ArmDriver(arm_config)

    if not chassis.initialize():
        print("底盘初始化失败")
        return

    if not arm.initialize():
        print("机械臂初始化失败")
        chassis.close()
        return

    try:
        # 同时控制底盘和机械臂
        print("\n[Demo] 边移动边操作机械臂")

        chassis.set_velocity(0.1, 0, 0)  # 缓慢前进
        arm.set_joint_angle("waist", 30)
        time.sleep(1)

        arm.set_joint_angle("shoulder", 45)
        time.sleep(1)

        chassis.stop()
        arm.move_to_home()

    finally:
        arm.close()
        chassis.close()


if __name__ == "__main__":
    print("\n飞特舵机驱动示例程序")
    print("请确保舵机已正确连接并上电\n")

    # 运行演示
    demo_chassis()
    # demo_arm()
    # demo_combined()

    print("\n演示完成!")
