"""ZeroMQ socket helper utilities"""
import zmq
from typing import Any


def create_context() -> zmq.Context:
    return zmq.Context.instance()


def create_socket(socket_type: int, bind: bool, address: str) -> zmq.Socket:
    ctx = create_context()
    sock = ctx.socket(socket_type)
    if bind:
        sock.bind(address)
    else:
        sock.connect(address)
    return sock


def send_json(socket: zmq.Socket, payload: Any) -> None:
    socket.send_json(payload)


def recv_json(socket: zmq.Socket) -> Any:
    return socket.recv_json()
