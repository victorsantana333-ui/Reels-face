@echo off
setlocal
cd /d "%~dp0"
where codex >nul 2>&1
if errorlevel 1 goto missing
call codex mcp get reels-face-browser >nul 2>&1
if errorlevel 1 goto missing
echo Entre com Sign in with ChatGPT se solicitado.
echo Na primeira conexao, selecione a aba do Muse na extensao Playwright.
echo Para interromper: Ctrl+C. Para desconectar: extensao Playwright.
echo Mantenha esta janela aberta durante a operacao.
call codex -C "%~dp0operacao" --sandbox workspace-write --ask-for-approval on-request "Leia AGENTS.md. Primeiro teste somente a conexao: use reels-face-browser para observar a aba escolhida por mim, relate o titulo e os controles relevantes, sem enviar prompts, gerar, baixar ou publicar. Se o conector estiver indisponivel, explique o erro sem tentar abrir outro perfil. Depois aguarde minha ordem nesta janela."
pause
exit /b 0
:missing
echo Execute primeiro 1-configurar.cmd e confira se terminou sem erros.
pause
exit /b 1
