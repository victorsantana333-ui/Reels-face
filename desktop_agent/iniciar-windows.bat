@echo off
cd /d "%~dp0\.."
if not exist .agent-venv\Scripts\python.exe (
  py -3 -m venv .agent-venv
  if errorlevel 1 goto error
)
.agent-venv\Scripts\python.exe -m pip install -r desktop_agent\requirements.txt
if errorlevel 1 goto error
.agent-venv\Scripts\python.exe -m desktop_agent.agent
if errorlevel 1 goto error
exit /b 0
:error
echo Instale Python 3.12 ou superior e Google Chrome. Confira a mensagem acima.
pause
