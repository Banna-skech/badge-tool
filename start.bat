@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   工牌照 ^& 座位牌 批量照片处理工具
echo ============================================
echo.

if not exist "venv" (
    echo [1/2] 正在创建虚拟环境并安装依赖，请稍候...
    py -m venv venv
    call venv\Scripts\activate.bat
    pip install --upgrade pip >nul 2>&1
    pip install -r requirements.txt
    echo.
    echo 依赖安装完成！
) else (
    echo [1/2] 虚拟环境已存在，激活中...
    call venv\Scripts\activate.bat
)

echo [2/2] 正在启动服务...
echo.
echo 浏览器将自动打开 http://localhost:8001
start http://localhost:8001
uvicorn backend.main:app --host 0.0.0.0 --port 8001

pause
