"""Human follow app placeholder."""

from common.logging import get_logger

logger = get_logger(__name__)


class HumanFollower:
    def __init__(self):
        # initialize cv models, zmq subscriptions
        from common.zmq_helper import create_socket
        self.socket = create_socket(zmq.SUB, bind=False, address="tcp://localhost:5560")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")

    def start_following(self):
        logger.info("starting follow mode")

    def stop(self):
        logger.info("stopping follow mode")

    def start_following(self):
        logger.info("starting follow mode")

    def stop(self):
        logger.info("stopping follow mode")
