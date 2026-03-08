"""Chassis driver interface"""

from common.logging import get_logger

logger = get_logger(__name__)


class ChassisDriver:
    def __init__(self):
        # open serial / motor controller
        pass

    def set_velocity(self, vx: float, vy: float, omega: float):
        logger.debug(f"set velocity {vx},{vy},{omega}")
