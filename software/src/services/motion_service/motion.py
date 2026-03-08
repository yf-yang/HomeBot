"""MotionService interface skeleton."""

from common.logging import get_logger

logger = get_logger(__name__)


import zmq

class MotionService:
    def __init__(self, bind_addr: str = "tcp://*:5555"):
        # initialize zmq REP socket, HAL drivers
        from common.zmq_helper import create_socket
        self.socket = create_socket(zmq.REP, bind=True, address=bind_addr)
        # placeholder driver
        self._driver = None

    def handle_velocity(self, vx: float, vy: float, omega: float):
        logger.debug(f"handle velocity {vx},{vy},{omega}")
        # call chassis driver

    def serve_forever(self):
        logger.info("MotionService starting")
        while True:
            msg = self.socket.recv_json()
            logger.debug(f"received: {msg}")
            if msg.get("type") == "cmd.velocity":
                data = msg.get("data", {})
                self.handle_velocity(data.get("vx",0), data.get("vy",0), data.get("omega",0))
                self.socket.send_json({"status": "ok"})
            else:
                self.socket.send_json({"status": "unknown type"})

