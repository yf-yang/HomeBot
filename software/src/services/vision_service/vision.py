"""VisionService interface skeleton."""

from common.logging import get_logger

logger = get_logger(__name__)

import zmq
class VisionService:
    def __init__(self, sub_addr: str = "tcp://localhost:5560"):
        # subscribe camera frames, process
        from common.zmq_helper import create_socket
        self.socket = create_socket(zmq.SUB, bind=False, address=sub_addr)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")  # subscribe all

    def process_frame(self, frame):
        logger.debug("processing frame")
        # placeholder for detection logic

    def listen(self, display: bool = False):
        """Start listening for frames. If display=True, show them in an OpenCV window."""
        import cv2
        import numpy as np

        logger.info("VisionService listening")
        while True:
            # expecting multipart: [frame_id, jpeg_bytes]
            parts = self.socket.recv_multipart()
            if len(parts) == 2:
                frame_id = parts[0].decode()
                buf = parts[1]
                img = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
                logger.debug(f"vision received frame {frame_id}")
                self.process_frame(img)
                if display and img is not None:
                    cv2.imshow('VisionService', img)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
            else:
                logger.warning(f"unexpected message parts: {len(parts)}")
        if display:
            cv2.destroyAllWindows()


