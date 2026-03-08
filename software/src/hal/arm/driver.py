"""Arm driver interface"""

from common.logging import get_logger

logger = get_logger(__name__)


class ArmDriver:
    def __init__(self):
        # initialize arm communication
        pass

    def move_joints(self, joints, speed):
        logger.debug(f"move joints {joints} at {speed}")
