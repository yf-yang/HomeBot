"""Camera subscriber helper (if other modules need raw frames)."""

from common.logging import get_logger
logger = get_logger(__name__)

class CameraSubscriber:
    def __init__(self, sub_addr: str = "tcp://localhost:5560"):
        import zmq
        from common.zmq_helper import create_socket
        self.socket = create_socket(zmq.SUB, bind=False, address=sub_addr)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")

    def read_loop(self):
        while True:
            msg = self.socket.recv_json()
            logger.debug(f"camera_sub got {msg}")
            # process raw frame if needed
