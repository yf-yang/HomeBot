"""Camera driver-based publisher that streams frames over ZMQ."""

from common.logging import get_logger
logger = get_logger(__name__)

class CameraPublisher:
    def __init__(self, pub_addr: str = "tcp://*:5560", config=None):
        import zmq
        from common.zmq_helper import create_socket
        from hal.camera.driver import CameraDriver
        # if config object provided use camera settings
        cam_device = 0
        if config is not None:
            cam_device = getattr(config.camera, 'device_id', cam_device)
            pub_addr = getattr(config.network.zmq, 'vision_pub_addr', pub_addr)
        logger.info(f"camera publisher using device {cam_device} and pub_addr {pub_addr}")
        self.socket = create_socket(zmq.PUB, bind=True, address=pub_addr)
        # open actual camera with config device id
        self._cam = CameraDriver(cam_device)
        self.fps = getattr(config.camera, 'fps', 30) if config else 30

    def start(self):
        import time
        import cv2
        frame_id = 0
        # cache frequently used attributes to locals to reduce attr lookup cost
        cap = self._cam
        sock = self.socket
        fps = self.fps
        tgt_int = 1.0 / fps if fps > 0 else 0
        warn = logger.warning
        info = logger.info
        # avoid debug in loop for speed
        try:
            perf = time.perf_counter
            while True:
                t0 = perf()
                frame = cap.capture_frame()
                if frame is None:
                    warn("no frame captured")
                    time.sleep(0.1)
                    continue
                # encode and send
                ret, buf = cv2.imencode('.jpg', frame)
                if not ret:
                    warn("failed to encode frame")
                else:
                    sock.send_multipart([str(frame_id).encode(), buf.tobytes()])
                    frame_id += 1
                elapsed = perf() - t0
                rem = tgt_int - elapsed
                if rem > 0:
                    # use time.sleep only if enough time, else busy-wait minimal
                    time.sleep(rem)
        except KeyboardInterrupt:
            info("camera publisher interrupted")
        finally:
            cap.release()

if __name__ == "__main__":
    # load configuration if available
    try:
        from common.config import Config
        cfg = Config()
    except Exception:
        cfg = None
    pub = CameraPublisher(config=cfg)
    pub.start()
