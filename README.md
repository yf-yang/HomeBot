# HomeBot

HomeBot 是一个面向家庭场景的轻量级机器人控制软件，基于 ZeroMQ 实现模块间消息传输。

## 项目结构

```
Homebot/
├── configs/                # 配置文件
├── docs/                   # 文档
├── src/                    # 源代码
│   ├── common/             # 公共工具、消息定义、配置类
│   ├── applications/       # 应用层模块（遥控、语音、跟随等）
│   ├── services/           # 服务层（运动、视觉、语音等）
│   ├── hal/                # 硬件抽象层（摄像头、底盘、机械臂、音频）
│   └── tests/              # 测试代码
├── models/                 # 机器学习模型
├── tools/                  # 数据采集、训练脚本
├── requirements.txt
├── pyproject.toml
├── setup.py
└── README.md
```

## 特性

- 采用分层模块化架构、ZeroMQ 作为通信总线
- 支持多种应用：手机遥控、语音交互、模仿学习、人跟随
- 硬件抽象层可适配不同传感器与执行器
- Python 配置类和 JSON 配置模板方便部署
- 可展示实时摄像头数据并严格控制帧率

## 安装

```bash
# 在项目根目录
python -m pip install -e .
```

依赖项已列在 `requirements.txt`。

## 快速开始

```bash
# 启动摄像头发布
python -c "from hal.camera.publisher import CameraPublisher; CameraPublisher().start()"

# 启动视觉服务并显示画面
python -c "from services.vision_service.vision import VisionService; VisionService().listen(display=True)"
```

## 配置

配置类位于 `src/common/config.py`，也可通过 JSON 文件加载并覆盖默认值。

## 开发规范

- 使用 `pytest` 编写并运行测试
- 避免将非源码文件加入 Git（已配置 `.gitignore`）

## 扩展

可以在后续迭代中添加 MQTT 桥接、多机器人协同、SLAM 等特性。

---

*Generated on 2026-03-05 by HomeBot development team.*