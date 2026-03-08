from hal import ChassisDriver, ArmDriver, ChassisConfig, ArmConfig

# 底盘控制
chassis = ChassisDriver(ChassisConfig(port="com15"))
chassis.initialize()
chassis.set_velocity(0.5, 0, 0.3)  # vx, vy, omega
chassis.move_forward(1.0)           # 前进1米
chassis.close()

# 机械臂控制
arm = ArmDriver(ArmConfig(port='com15'))
arm.initialize()
arm.set_joint_angle("shoulder", 45)
arm.set_joint_angles({"elbow": 90, "wrist": -30})
arm.open_gripper()
arm.close()