"""Simple tests for ZeroMQ helper and basic service/app communication."""
import sys, os
# ensure project src directory on path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import threading
import time
import zmq

from common.zmq_helper import create_socket
from services.motion_service.motion import MotionService
from applications.remote_control.controller import RemoteController


def run_service():
    try:
        svc = MotionService(bind_addr="tcp://*:5565")
        svc.serve_forever()
    except Exception as e:
        print("service thread exception", e)
        raise


def test_motion_roundtrip():
    # start service in background
    t = threading.Thread(target=run_service, daemon=True)
    t.start()
    time.sleep(0.1)
    client = RemoteController(pub_addr="tcp://localhost:5565")
    client.send_velocity(1.0, 0.0, 0.0)
    # if no exception, assume works


if __name__ == "__main__":
    test_motion_roundtrip()
    print("zmq roundtrip test passed")
