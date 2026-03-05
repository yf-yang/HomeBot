"""Speech interaction application skeleton."""

from common.logging import get_logger

logger = get_logger(__name__)


class SpeechApp:
    def __init__(self, req_addr: str = "tcp://localhost:5570"):
        # initialize speech recognition / TTS
        from common.zmq_helper import create_socket
        self.socket = create_socket(zmq.REQ, bind=False, address=req_addr)

    def listen(self) -> str:
        """返回识别到的文本"""
        return ""

    def speak(self, text: str):
        logger.info(f"speaking: {text}")
        # send TTS request
        self.socket.send_json({"type": "tts", "text": text})
        return self.socket.recv_json()

    def listen(self) -> str:
        """返回识别到的文本"""
        return ""

    def speak(self, text: str):
        logger.info(f"speaking: {text}")
