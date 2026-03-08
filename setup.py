from setuptools import setup, find_packages

setup(
    name="homebot",
    version="0.1.0",
    description="HomeBot 家用机器人控制软件",
    packages=find_packages(where="software/src"),
    package_dir={"": "software/src"},
    install_requires=[
        "pyzmq",
        "opencv-python",
        "ftservo-python-sdk",
        "pyserial",
    ],
    include_package_data=True,
)
