"""
Motion Service 启动入口

Usage:
    python -m services.motion_service.chassis_service
    python -m services.motion_service.chassis_service --port COM3
"""
from services.motion_service.chassis_service import main

if __name__ == '__main__':
    main()
