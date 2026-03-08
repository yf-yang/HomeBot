"""VisionService - 图像采集、处理和发布服务.

其他应用通过订阅此服务发布的图像帧来获取视频流.
"""

import zmq
import time
from common.logging import get_logger

logger = get_logger(__name__)


class VisionService:
    """视觉服务: 直接采集图像,处理后发布给其他应用订阅."""
    
    def __init__(self, pub_addr: str = "tcp://*:5560", config=None):
        """
        初始化视觉服务.
        
        Args:
            pub_addr: ZMQ PUB socket 绑定地址
            config: 配置对象,包含 camera 和 zmq 配置
        """
        from common.zmq_helper import create_socket
        from configs.config import get_config
        
        # 加载配置
        if config is None:
            config = get_config()
        self._config = config
        
        # 从配置获取地址
        pub_addr = getattr(config, 'zmq', config).vision_pub_addr if hasattr(config, 'zmq') else pub_addr
        if hasattr(config, 'network') and hasattr(config.network, 'zmq'):
            pub_addr = config.network.zmq.vision_pub_addr
            
        # 创建 PUB socket 用于发布图像帧
        self._pub_socket = create_socket(zmq.PUB, bind=True, address=pub_addr)
        logger.info(f"VisionService PUB socket bound to {pub_addr}")
        
        # 相机配置
        self._cam_device = getattr(config.camera, 'device_id', 0) if hasattr(config, 'camera') else 0
        self._fps = getattr(config.camera, 'fps', 30) if hasattr(config, 'camera') else 30
        self._width = getattr(config.camera, 'width', 640) if hasattr(config, 'camera') else 640
        self._height = getattr(config.camera, 'height', 480) if hasattr(config, 'camera') else 480
        
        # 相机驱动 (延迟初始化)
        self._cam = None
        
        # 运行标志
        self._running = False

    def _init_camera(self):
        """初始化相机驱动."""
        from hal.camera.driver import CameraDriver
        self._cam = CameraDriver(self._cam_device)
        logger.info(f"Camera initialized: device={self._cam_device}, fps={self._fps}")

    def process_frame(self, frame):
        """处理图像帧 (子类可重写此方法添加视觉处理逻辑).
        
        Args:
            frame: OpenCV 图像帧 (numpy array)
            
        Returns:
            处理后的图像帧,如果不需要修改则返回原帧
        """
        # placeholder for detection logic (e.g., object detection, tracking)
        return frame

    def start(self, display: bool = False):
        """启动图像采集和发布循环.
        
        Args:
            display: 是否显示图像窗口 (调试用)
        """
        import cv2
        import numpy as np
        
        self._init_camera()
        self._running = True
        
        frame_id = 0
        tgt_int = 1.0 / self._fps if self._fps > 0 else 0
        
        logger.info(f"VisionService started publishing at {self._fps} FPS")
        
        try:
            perf = time.perf_counter
            while self._running:
                t0 = perf()
                
                # 1. 采集图像
                frame = self._cam.capture_frame()
                if frame is None:
                    logger.warning("no frame captured")
                    time.sleep(0.1)
                    continue
                
                # 2. 处理图像 (子类可扩展)
                processed_frame = self.process_frame(frame)
                
                # 3. 编码并发布
                ret, buf = cv2.imencode('.jpg', processed_frame)
                if not ret:
                    logger.warning("failed to encode frame")
                    continue
                    
                self._pub_socket.send_multipart([str(frame_id).encode(), buf.tobytes()])
                frame_id += 1
                
                # 4. 可选显示
                if display and processed_frame is not None:
                    cv2.imshow('VisionService', processed_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                # FPS 控制
                elapsed = perf() - t0
                rem = tgt_int - elapsed
                if rem > 0:
                    time.sleep(rem)
                    
        except KeyboardInterrupt:
            logger.info("VisionService interrupted by user")
        except Exception as e:
            logger.error(f"VisionService error: {e}")
        finally:
            self.stop()
            if display:
                cv2.destroyAllWindows()

    def stop(self):
        """停止服务并释放资源."""
        self._running = False
        if self._cam:
            self._cam.release()
            self._cam = None
        logger.info("VisionService stopped")

    # 保持向后兼容: listen 方法重命名为 start
    listen = start


class VisionSubscriber:
    """视觉订阅者 - 用于其他应用订阅 VisionService 发布的图像帧."""
    
    def __init__(self, sub_addr: str = "tcp://localhost:5560"):
        """
        初始化视觉订阅者.
        
        Args:
            sub_addr: VisionService 的 PUB 地址
        """
        from common.zmq_helper import create_socket
        self._sub_socket = create_socket(zmq.SUB, bind=False, address=sub_addr)
        self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # subscribe all
        logger.info(f"VisionSubscriber connected to {sub_addr}")

    def read_frame(self, timeout: int = 1000):
        """读取一帧图像.
        
        Args:
            timeout: 接收超时时间 (毫秒)
            
        Returns:
            (frame_id, frame) 元组,如果超时返回 (None, None)
        """
        import cv2
        import numpy as np
        
        self._sub_socket.setsockopt(zmq.RCVTIMEO, timeout)
        
        try:
            parts = self._sub_socket.recv_multipart()
            if len(parts) == 2:
                frame_id = parts[0].decode()
                buf = parts[1]
                img = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
                return frame_id, img
            else:
                logger.warning(f"unexpected message parts: {len(parts)}")
                return None, None
        except zmq.Again:
            # 超时
            return None, None

    def read_loop(self, callback=None, display: bool = False):
        """持续读取图像帧.
        
        Args:
            callback: 每帧的回调函数,接收 (frame_id, frame) 参数
            display: 是否显示图像
        """
        import cv2
        
        logger.info("VisionSubscriber started reading")
        try:
            while True:
                frame_id, frame = self.read_frame(timeout=1000)
                if frame is not None:
                    if callback:
                        callback(frame_id, frame)
                    if display:
                        cv2.imshow('VisionSubscriber', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
        except KeyboardInterrupt:
            logger.info("VisionSubscriber interrupted")
        finally:
            if display:
                cv2.destroyAllWindows()


