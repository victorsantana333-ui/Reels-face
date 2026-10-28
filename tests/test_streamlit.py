import os
from pathlib import Path
import subprocess
import sys
import unittest


class StreamlitUITests(unittest.TestCase):
    def test_login_project_context_batch_and_all_views(self):
        # Separate process owns all cache resources and its disposable worker.
        code = r'''
import os,tempfile
from streamlit.testing.v1 import AppTest

def no_errors(at):
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.error, [e.value for e in at.error]

def button(at,label):
    return next(b for b in at.button if b.label==label)

def text(at,label):
    return next(t for t in at.text_input if t.label==label)

with tempfile.TemporaryDirectory() as data:
    os.environ.update(REELS_ACCESS_TOKEN='local-test-key-not-real-credentials',REELS_ALLOW_LOCAL_UI='1',DATABASE_URL='',REELS_DATA_DIR=data)
    at=AppTest.from_file('streamlit_app.py',default_timeout=20).run()
    assert not at.metric
    at.text_input[0].input('incorrect')
    button(at,'Entrar').click().run()
    assert at.error
    assert not at.metric
    # The first failed attempt has a short retry delay.
    import time
    time.sleep(1.1)
    at.text_input[0].input('local-test-key-not-real-credentials')
    button(at,'Entrar').click().run()
    no_errors(at)
    assert any(m.label=='Projetos ativos' and m.value=='1' for m in at.metric)
    at.radio[0].set_value('Projetos').run()
    at.toggle[0].set_value(True).run()
    text(at,'Nome do projeto').input('Projeto de teste Streamlit')
    button(at,'Salvar projeto').click().run()
    no_errors(at)
    at.toggle[0].set_value(False).run()
    at.selectbox[0].select_index(1).run()
    text(at,'Título').input('Storyboard de teste')
    next(t for t in at.text_area if t.label=='Storyboard, referências ou instruções').input('Personagem com corpo azul.')
    button(at,'Salvar contexto').click().run()
    no_errors(at)
    assert any(c.value=='Personagem com corpo azul.' for c in at.code)
    at.radio[0].set_value('Operação em Massa').run()
    next(n for n in at.number_input if n.label=='Quantidade de vídeos').set_value(3)
    button(at,'Planejar lote').click().run()
    no_errors(at)
    for view in ['Produção','Calendário','Integrações e Páginas','Automação do Desktop','Histórico','Configurações','Central de Inteligência','Dashboard']:
        at.radio[0].set_value(view).run()
        no_errors(at)
    button(at,'Sair').click().run()
    assert not at.metric
    assert any(b.label=='Entrar' for b in at.button)
print('Streamlit end-to-end passed')
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

    def test_cloud_refuses_ephemeral_database(self):
        code=r'''
import os
from streamlit.testing.v1 import AppTest
os.environ.update(REELS_ACCESS_TOKEN='local-test-key-not-real-credentials',DATABASE_URL='',REELS_ALLOW_LOCAL_UI='')
at=AppTest.from_file('streamlit_app.py').run()
at.text_input[0].input('local-test-key-not-real-credentials')
at.button[0].click().run()
assert not at.metric
assert any('DATABASE_URL' in i.value for i in at.info)
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
