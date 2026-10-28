"""End-to-end smoke on an isolated real server and database, no external actions."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as data:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    url=f'http://127.0.0.1:{port}'
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env={**os.environ,'REELS_DATA_DIR':data,'REELS_ACCESS_TOKEN':'','DATABASE_URL':''},stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(60):
            try:
                with urlopen(url+'/api/health',timeout=1) as r:
                    if r.status==200:break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Server failed to start')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('BROWSER_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1100})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url)
            page.get_by_role('heading',name='Tudo começa com uma boa história.').wait_for()
            page.screenshot(path='/tmp/reels-face-dashboard.png',full_page=True)
            page.get_by_role('button',name='＋ Novo projeto').click()
            page.get_by_label('Nome do projeto').fill('Projeto de teste <seguro>')
            page.get_by_role('button',name='Criar projeto →').click()
            page.get_by_role('heading',name='Projeto de teste <seguro>',exact=True).wait_for()
            project_url=page.url
            page.get_by_role('button',name='Escrever contexto').click()
            page.get_by_label('Título',exact=True).fill('Storyboard')
            page.get_by_label('Storyboard, referências ou instruções').fill('<script>window.UNSAFE=true</script> Personagem azul.')
            page.get_by_role('button',name='Salvar contexto').click()
            page.get_by_role('heading',name='Storyboard',exact=True).wait_for()
            assert page.evaluate('window.UNSAFE') is None
            page.get_by_role('button',name='Memória e correções').click()
            page.get_by_role('button',name='＋ Registrar').click()
            page.get_by_label('Instrução',exact=True).fill('Peito branco, bico amarelo')
            page.get_by_role('button',name='Registrar preferência').click()
            page.get_by_text('Peito branco, bico amarelo',exact=True).wait_for()
            page.get_by_role('link',name='Operação em Massa').click()
            page.get_by_role('button',name='＋ Planejar lote').click()
            page.get_by_label('Quantidade de vídeos').fill('3')
            page.get_by_role('button',name='Criar planejamento →').click()
            page.get_by_role('heading',name='Projeto de teste <seguro> Em operação').wait_for()
            page.get_by_role('link',name='Produção',exact=True).click()
            page.get_by_role('button',name='Inspecionar').first.wait_for()
            page.get_by_role('button',name='Atualizar ↻').click()
            page.get_by_role('button',name='Inspecionar').first.click()
            page.get_by_role('heading',name='Tarefa 1').wait_for()
            page.get_by_text('Peito branco, bico amarelo',exact=False).wait_for()
            page.get_by_role('button',name='Fechar',exact=True).click()
            for route in ['calendar','integrations','desktop','history','settings','intelligence','projects']:
                page.goto(url+'/#'+route)
                page.get_by_role('heading',name={'calendar':'Calendário','integrations':'Integrações e Páginas','desktop':'Automação do Desktop','history':'Histórico','settings':'Configurações','intelligence':'Central de Inteligência','projects':'Projetos'}[route],exact=True).wait_for()
                assert not page.locator('.error-box').count(),route
            page.goto(project_url)
            page.get_by_role('button',name='Editar',exact=True).click()
            page.get_by_label('Descrição',exact=True).fill('Descrição editada no navegador')
            page.get_by_role('button',name='Salvar alterações →').click()
            page.get_by_text('Descrição editada no navegador',exact=True).wait_for()
            page.once('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='Arquivar',exact=True).click()
            page.get_by_role('button',name='Restaurar',exact=True).wait_for()
            page.get_by_role('button',name='Restaurar',exact=True).click()
            page.get_by_role('button',name='Arquivar',exact=True).wait_for()
            page.get_by_role('button',name='Excluir',exact=True).click()
            page.get_by_label('Digite o nome exato:',exact=False).fill('Projeto de teste <seguro>')
            page.get_by_role('button',name='Confirmar exclusão',exact=True).click()
            page.get_by_role('heading',name='Projetos',exact=True).wait_for()
            assert not page.get_by_role('heading',name='Projeto de teste <seguro>',exact=True).count()
            page.set_viewport_size({'width':390,'height':844})
            page.goto(url+'/#dashboard')
            page.get_by_role('heading',name='Tudo começa com uma boa história.').wait_for()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.wait_for_timeout(250)  # Sidebar resize transition is 200 ms.
            assert page.locator('.sidebar').evaluate("el => el.getBoundingClientRect().right <= 0")
            page.screenshot(path='/tmp/reels-face-mobile.png',full_page=True)
            page.get_by_role('button',name='Abrir navegação').click()
            page.get_by_role('link',name='Projetos',exact=True).click()
            page.get_by_role('heading',name='Projetos',exact=True).wait_for()
            assert not errors,errors
            browser.close()
        print('PASS: browser CRUD, context XSS escaping, preferences, batch, worker snapshot, routes and mobile layout')
    finally:
        proc.terminate()
        proc.wait(timeout=10)
