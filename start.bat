@echo off

REM 获取当前脚本所在目录
set ROOT=%~dp0

echo Starting client...
start "CLIENT" cmd /k "cd /d %ROOT%client && npm run dev"

echo Starting app (Python + Conda)...
start "APP" cmd /k "cd /d %ROOT%app && call conda activate emobridge && python main.py"

echo Starting app (Python + Conda)...
start "Chroma" cmd /k "call conda activate emobridge && chroma run --path E:\chromadb\test"

echo Starting mcp (Spring Boot)...
start "MCP" cmd /k "cd /d %ROOT%mcp && mvn spring-boot:run"

echo All services started!
pause