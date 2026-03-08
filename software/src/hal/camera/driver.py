"""Camera driver implementation using OpenCV."""

from common.logging import get_logger

logger = get_logger(__name__)


class CameraDriver:
    def __init__(self, device: int = 0):
        """Open the camera device index (default 0)."""
        import cv2
        self._device = device
        self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():
            logger.error(f"failed to open camera device {device}")
            raise RuntimeError(f"Camera {device} open failed")
        logger.info(f"camera {device} opened")

    def capture_frame(self):
        """Capture a single frame and return as numpy array (BGR)."""
        import cv2
        if self._cap is None:
            raise RuntimeError("camera not initialized")
        ret, frame = self._cap.read()
        if not ret:
            logger.warning("failed to read frame")
            return None
        logger.debug("captured frame")
        return frame

    def release(self):
        """Release the camera resource."""
        if self._cap:
            self._cap.release()
            self._cap = None
            logger.info("camera released")
