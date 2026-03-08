"""
Vision Service 启动入口

Usage:
    python -m services.vision_service
    python -m services.vision_service --display
"""
import argparse
from services.vision_service import VisionService


def main():
    parser = argparse.ArgumentParser(description='HomeBot Vision Service')
    parser.add_argument('--display', action='store_true', help='Show video window')
    parser.add_argument('--addr', default=None, help='Publish address (default: tcp://*:5560)')
    args = parser.parse_args()
    
    service = VisionService(pub_addr=args.addr) if args.addr else VisionService()
    service.start(display=args.display)


if __name__ == '__main__':
    main()
