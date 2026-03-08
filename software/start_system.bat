@echo off
chcp 65001 >nul
echo ==========================================
echo    HomeBot System Launcher
echo ==========================================
echo.

:: Check ports before starting
set PORTS_OCCUPIED=0

echo [Check] Checking required ports...
echo.

:: Check port 5000 (Web)
netstat -ano 2>nul | findstr ":5000" >nul
if %errorlevel% == 0 (
    echo [WARN] Port 5000 is occupied ^(Web Server^)
    set PORTS_OCCUPIED=1
) else (
    echo [OK] Port 5000 is available
)

:: Check port 5556 (Chassis)
netstat -ano 2>nul | findstr ":5556" >nul
if %errorlevel% == 0 (
    echo [WARN] Port 5556 is occupied ^(Chassis Service^)
    set PORTS_OCCUPIED=1
) else (
    echo [OK] Port 5556 is available
)

:: Check port 5560 (Vision)
netstat -ano 2>nul | findstr ":5560" >nul
if %errorlevel% == 0 (
    echo [WARN] Port 5560 is occupied ^(Vision Service^)
    set PORTS_OCCUPIED=1
) else (
    echo [OK] Port 5560 is available
)

echo.

:: If ports occupied, ask user what to do
if %PORTS_OCCUPIED% == 1 (
    echo ==========================================
    echo [WARNING] Some ports are already in use!
    echo.
    echo This may cause services to fail starting.
    echo.
    echo Options:
    echo   1. Kill occupying processes and continue
    echo   2. Continue anyway (may cause errors)
    echo   3. Exit
    echo ==========================================
    echo.
    
    choice /c 123 /n /m "Select option [1-3]: "
    
    if errorlevel 3 (
        echo [Exit] User cancelled.
        pause
        exit /b 1
    )
    
    if errorlevel 2 (
        echo [Continue] Starting with warnings...
        echo.
    )
    
    if errorlevel 1 (
        echo [Action] Killing processes on occupied ports...
        
        :: Kill processes on each port
        for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000"') do (
            echo   Killing PID %%a on port 5000...
            taskkill /F /PID %%a 2>nul
        )
        for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5556"') do (
            echo   Killing PID %%a on port 5556...
            taskkill /F /PID %%a 2>nul
        )
        for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5560"') do (
            echo   Killing PID %%a on port 5560...
            taskkill /F /PID %%a 2>nul
        )
        
        echo [OK] Cleanup complete
        timeout /t 2 /nobreak >nul
        echo.
    )
) else (
    echo [OK] All ports are available
    echo.
)

cd /d "%~dp0\src"

echo [Start] Starting Chassis Arbiter...
start "Chassis Arbiter" cmd /k python -m services.motion_service.chassis_service
timeout /t 2 /nobreak >nul

echo [Start] Starting Vision Service...
start "Vision Service" cmd /k python -m services.vision_service
timeout /t 2 /nobreak >nul

echo [Start] Starting Web Control...
start "Web Control" cmd /k python -m applications.remote_control

echo.
echo ==========================================
echo [OK] All services started!
echo.
echo Services:
echo   - Chassis Arbiter (ZeroMQ: tcp://127.0.0.1:5556)
echo   - Vision Service (Camera: tcp://127.0.0.1:5560)
echo   - Web Control (Flask: http://0.0.0.0:5000)
echo.
echo URL: http://localhost:5000
echo Video: http://localhost:5000/video_feed
echo ==========================================
pause
