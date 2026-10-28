@echo off
setlocal
cd /d "%~dp0"
echo Reels-face - configurar Codex e conexao com Chrome
where node.exe >nul 2>&1
if errorlevel 1 goto node_missing
where npm.cmd >nul 2>&1
if errorlevel 1 goto node_missing
node -e "if(Number(process.versions.node.split('.')[0]) < 22) process.exit(1)"
if errorlevel 1 goto node_missing
where codex >nul 2>&1
if errorlevel 1 (
  call npm.cmd install -g @openai/codex
  if errorlevel 1 goto failed
)
if not exist "%~dp0operacao\downloads" mkdir "%~dp0operacao\downloads"
echo Conectando o servidor oficial Playwright em modo extensao.
call codex mcp add reels-face-browser -- cmd /c npx -y @playwright/mcp@0.0.83 --extension --output-dir "%~dp0operacao\downloads"
if errorlevel 1 goto failed
echo.
echo Configuracao gravada. Abra LEIA-ME.md para instalar a extensao oficial.
echo Depois execute 2-iniciar.cmd e entre com sua conta ChatGPT Pro.
echo Nao e necessario informar chave de API.
pause
exit /b 0
:node_missing
echo Instale Node.js LTS 22 ou superior em https://nodejs.org/
echo Depois feche esta janela e abra este arquivo novamente.
pause
exit /b 1
:failed
echo A configuracao falhou. Confira a mensagem acima. Nao envie senhas ou tokens.
pause
exit /b 1
