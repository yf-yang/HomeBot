@echo off
chcp 65001 >nul
echo ==========================================
echo    HomeBot 底盘服务启动器
echo ==========================================
echo.
echo 串口从 configs/config.py 读取，默认 COM3
echo 可通过 --port 参数临时覆盖
echo.

cd /d "%~dp0\src"

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python
    pause
    exit /b 1
)

:: 查找串口
echo [信息] 可用串口:
mode | findstr "COM" || echo   未检测到串口
echo.

:: 解析可选参数
set EXTRA_ARGS=

:parse_args
if "%~1"=="" goto :done_parsing
set EXTRA_ARGS=%EXTRA_ARGS% %~1
shift
goto :parse_args
:done_parsing

if not "%EXTRA_ARGS%"=="" (
    echo [命令行参数] %EXTRA_ARGS%
)

echo [启动] 正在启动底盘服务...
echo [提示] 按Ctrl+C停止
echo.

python -m services.motion_service.chassis_service %EXTRA_ARGS%

pause
