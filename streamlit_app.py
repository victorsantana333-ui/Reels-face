"""Free Community Cloud entrypoint, reusing the FastAPI business operations.

This is an additional UI, not a replacement for the existing web/API app.
There is no internal test client, hidden HTTP server or browser dependency.
"""
import asyncio
import atexit
import hashlib
import io
import os
import secrets
import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError

from app.main import (ArchiveInput, BatchInput, Confirmation, ContextInput,
                      PreferenceInput, ProductionSettings, ProjectInput,
                      create_app, initialize, worker)

st.set_page_config(page_title='Reels-face', page_icon='🐦', layout='wide')


def setting(name, default=''):
    try:
        return str(st.secrets.get(name, os.environ.get(name, default)))
    except FileNotFoundError:
        return os.environ.get(name, default)


class Workspace:
    def __init__(self, database_url):
        self.app = create_app(database_url=database_url)
        initialize(self.app)
        self.app.state.worker_error = None
        self.app.state.stop = threading.Event()
        self.thread = threading.Thread(target=worker, args=(self.app,), daemon=True)
        self.thread.start()
        atexit.register(self.close)

    def close(self):
        self.app.state.stop.set()
        self.thread.join(timeout=20)
        self.app.state.database.close()

    def call(self, name, **kwargs):
        return self.app.state.operations[name](**kwargs)


@st.cache_resource(show_spinner='Conectando ao seu workspace…')
def workspace(config_fingerprint, _database_url):
    # Only the digest is a cache key; the connection URI is never displayed.
    return Workspace(_database_url)


def login(token):
    if len(token) < 16:
        st.info('Configure uma chave pessoal REELS_ACCESS_TOKEN de pelo menos 16 caracteres em Settings → Secrets da hospedagem.')
        st.stop()
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    if st.session_state.get('authenticated_key') == fingerprint:
        return
    st.title('🐦 Reels-face')
    st.write('Seu contexto. Seu estilo. Sua operação.')
    with st.form('login', clear_on_submit=True):
        password = st.text_input('Chave de acesso do aplicativo', type='password')
        submitted = st.form_submit_button('Entrar', type='primary')
    if submitted:
        if time.monotonic() < st.session_state.get('login_after', 0):
            st.error('Aguarde um momento antes de tentar novamente.')
        elif secrets.compare_digest(password, token):
            st.session_state['authenticated_key'] = fingerprint
            st.session_state['login_failures'] = 0
            st.rerun()
        else:
            fails = st.session_state.get('login_failures', 0) + 1
            st.session_state['login_failures'] = fails
            st.session_state['login_after'] = time.monotonic() + (30 if fails >= 5 else 1)
            st.error('Chave de acesso incorreta.')
    st.stop()


def changed(message):
    st.session_state['notice'] = message
    st.rerun()


def project_editor(ws, p=None):
    cfg = ProductionSettings(**p['settings']) if p else ProductionSettings()
    with st.form('project_editor'):
        name = st.text_input('Nome do projeto', value=p['name'] if p else '', max_chars=120)
        desc = st.text_area('Descrição', value=p['description'] if p else '', max_chars=4000)
        c1,c2,c3 = st.columns(3)
        ratio = c1.selectbox('Proporção', ['9:16','16:9','1:1'], index=['9:16','16:9','1:1'].index(cfg.aspect_ratio))
        minimum = c2.number_input('Duração mínima (s)', 5, 3600, cfg.duration_min)
        maximum = c3.number_input('Duração máxima (s)', 5, 3600, cfg.duration_max)
        tz = st.text_input('Fuso horário', value=cfg.timezone)
        budget = st.number_input('Limite de gastos por lote (R$)', min_value=0., value=cfg.budget_cents/100, step=1.)
        subs = st.checkbox('Legendas quando o provedor estiver conectado', value=cfg.subtitles)
        narration = st.checkbox('Narração quando o provedor estiver conectado', value=cfg.narration)
        if st.form_submit_button('Salvar projeto', type='primary'):
            body = ProjectInput(name=name, description=desc, settings=ProductionSettings(aspect_ratio=ratio, duration_min=minimum, duration_max=maximum, timezone=tz, budget_cents=round(budget*100), subtitles=subs, narration=narration))
            if p:
                ws.call('update_project', pid=p['id'], body=body)
            else:
                ws.call('create_project', body=body)
            changed('Projeto salvo.')


def context_view(ws, p):
    st.subheader('Contexto de ' + p['name'])
    st.caption('Os dados deste projeto não são misturados aos demais. Links de chats não são sincronizados automaticamente.')
    with st.form('context_upload', clear_on_submit=True):
        file = st.file_uploader('Importar conversa, storyboard ou instruções', type=['txt','md','json'], max_upload_size=2)
        if st.form_submit_button('Importar arquivo'):
            if file is None:
                st.warning('Selecione um arquivo.')
            else:
                result = asyncio.run(ws.call('import_context', pid=p['id'], file=UploadFile(file=io.BytesIO(file.getvalue()),filename=file.name)))
                changed('Conteúdo já importado.' if result['duplicate'] else 'Contexto importado.')
    with st.expander('Escrever contexto manualmente'):
        with st.form('context_text', clear_on_submit=True):
            title = st.text_input('Título', max_chars=200)
            content = st.text_area('Storyboard, referências ou instruções', max_chars=2*1024*1024)
            if st.form_submit_button('Salvar contexto'):
                ws.call('context_text', pid=p['id'], body=ContextInput(name=title,content=content))
                changed('Contexto salvo.')
    contexts = ws.call('contexts', pid=p['id'])
    if not contexts:
        st.info('Importe o seu contexto criativo para começar.')
    for c in contexts:
        with st.expander(c['name']):
            st.code(c['content'], language=None)
            confirm = st.checkbox('Confirmo a remoção deste contexto', key='confirm_ctx_'+c['id'])
            if st.button('Remover contexto', key='remove_ctx_'+c['id'],disabled=not confirm):
                ws.call('remove_context', pid=p['id'], cid=c['id'])
                changed('Contexto removido; snapshots já preparados foram preservados.')
    st.subheader('Memória e correções')
    with st.form('preferences', clear_on_submit=True):
        category = st.text_input('Categoria', value='Personagens', max_chars=100)
        instruction = st.text_area('Preferência ou correção', max_chars=10000)
        scope_label = st.selectbox('Aplicar a', ['Somente este projeto','Uma tarefa específica','Todos os projetos'])
        production_id = st.text_input('ID da tarefa, somente para correção pontual')
        global_confirm = st.checkbox('Confirmo explicitamente a aplicação a TODOS os projetos')
        if st.form_submit_button('Registrar preferência'):
            scope={'Somente este projeto':'project','Uma tarefa específica':'production','Todos os projetos':'global'}[scope_label]
            ws.call('add_preference',pid=p['id'],body=PreferenceInput(scope=scope,category=category,instruction=instruction,production_id=production_id or None,confirm_global=global_confirm))
            changed('Preferência registrada no escopo escolhido.')
    for pref in ws.call('preferences',pid=p['id']):
        label={'global':'Global · explícita','project':'Só este projeto','production':'Uma tarefa'}[pref['scope']]
        with st.expander(pref['category']+' · '+label):
            st.text(pref['instruction'])
            if pref['production_id']:
                st.caption('Tarefa: '+pref['production_id'])
            confirm=st.checkbox('Confirmo remover esta preferência'+(' de TODOS os projetos' if pref['scope']=='global' else ''), key='pref_confirm_'+pref['id'])
            if st.button('Remover preferência',key='pref_remove_'+pref['id'],disabled=not confirm):
                ws.call('delete_preference',pid=p['id'],prefid=pref['id'],confirm_global=confirm)
                changed('Preferência removida.')


def projects_view(ws, projects):
    create=st.toggle('Criar novo projeto')
    if create:
        project_editor(ws)
        return
    if not projects:
        st.info('Crie um projeto para começar.')
        return
    pid=st.selectbox('Projeto', [p['id'] for p in projects],format_func=lambda pid:next(p['name']+(' · arquivado' if p['archived'] else '') for p in projects if p['id']==pid))
    p=next(p for p in projects if p['id']==pid)
    st.subheader(p['name'])
    st.text(p['description'])
    if st.button('Duplicar projeto'):
        ws.call('duplicate',pid=pid)
        changed('Cópia independente criada, sem tarefas duplicadas.')
    with st.expander('Editar nome e preferências de produção'):
        project_editor(ws,p)
    with st.expander('Arquivar ou excluir'):
        confirmation=st.checkbox('Confirmo '+('restaurar' if p['archived'] else 'arquivar e pausar os lotes ativos')+' deste projeto')
        if st.button('Restaurar' if p['archived'] else 'Arquivar',disabled=not confirmation):
            ws.call('archive',pid=pid,body=ArchiveInput(archived=not p['archived']))
            changed('Projeto atualizado. Lotes pausados precisam ser retomados manualmente.')
        with st.form('delete_project'):
            st.warning('Excluir oculta o projeto, preserva os dados e cancela suas tarefas pendentes.')
            name=st.text_input('Digite o nome exato do projeto para excluir')
            if st.form_submit_button('Confirmar exclusão'):
                ws.call('delete_project',pid=pid,body=Confirmation(confirm_name=name))
                changed('Projeto excluído; dados preservados no banco.')
    context_view(ws,p)


def batches_view(ws, projects):
    active=[p for p in projects if not p['archived']]
    st.info('Planejamento disponível. Geração, validação visual e publicação externa ainda não estão implementadas. Custo externo desta operação: R$ 0,00.')
    if active:
        with st.form('batch'):
            pid=st.selectbox('Projeto de produção',[p['id'] for p in active],format_func=lambda pid:next(p['name'] for p in active if p['id']==pid))
            qty=st.number_input('Quantidade de vídeos',1,10000,70)
            start=st.date_input('Início do planejamento',value=datetime.now(ZoneInfo('America/Bahia')).date()+timedelta(days=1))
            times=st.text_input('Horários separados por vírgula',value='09:00, 18:00')
            days=st.multiselect('Dias da semana',['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'],default=['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'])
            budget=st.number_input('Limite de gastos do lote (R$)',min_value=0.,value=0.,step=1.)
            if st.form_submit_button('Planejar lote',type='primary'):
                request_key=st.session_state.setdefault('batch_request_key',secrets.token_hex(24))
                ws.call('create_batch',body=BatchInput(project_id=pid,quantity=qty,start_date=start,times=[t.strip() for t in times.split(',')],weekdays=[['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'].index(d) for d in days],budget_cents=round(budget*100),request_key=request_key))
                st.session_state.pop('batch_request_key',None)
                changed('Lote planejado; nenhuma geração ou publicação externa foi executada.')
    else:
        st.warning('Crie ou restaure um projeto para planejar lotes.')
    for b in ws.call('batches'):
        with st.container(border=True):
            st.write(b['project_name']+' · '+str(b['quantity'])+' tarefas · '+b['status'])
            st.caption(' · '.join(f'{v} {k}' for k,v in b['counts'].items()))
            if b['status']=='cancelled':
                continue
            c1,c2,c3=st.columns(3)
            if c1.button('Retomar' if b['status']=='paused' else 'Pausar',key='pause_'+b['id']):
                ws.call('batch_action',bid=b['id'],action='resume' if b['status']=='paused' else 'pause')
                changed('Lote atualizado.')
            if c2.button('Repreparar bloqueadas',key='retry_'+b['id']):
                ws.call('batch_action',bid=b['id'],action='retry')
                changed('Tarefas bloqueadas voltaram à fila; nenhum provedor será chamado.')
            cancel=c3.checkbox('Confirmo cancelar',key='confirm_cancel_'+b['id'])
            if c3.button('Cancelar lote',key='cancel_'+b['id'],disabled=not cancel):
                ws.call('batch_action',bid=b['id'],action='cancel')
                changed('Lote cancelado.')


def run():
    token=setting('REELS_ACCESS_TOKEN')
    login(token)
    url=setting('DATABASE_URL')
    if not url and setting('REELS_ALLOW_LOCAL_UI')!='1':
        st.info('Configure DATABASE_URL em Settings → Secrets com a conexão Session pooler do Supabase. Não cole a senha no chat. Nenhum banco temporário será usado como substituto na nuvem.')
        st.stop()
    fingerprint=hashlib.sha256((url+'\0'+token).encode()).hexdigest()
    ws=workspace(fingerprint,_database_url=url)
    call=ws.call
    projects=call('projects')
    with st.sidebar:
        st.title('🐦 Reels-face')
        st.caption('Seu estúdio de conteúdo')
        page=st.radio('Workspace',['Dashboard','Projetos','Central de Inteligência','Operação em Massa','Produção','Calendário','Integrações e Páginas','Automação do Desktop','Histórico','Configurações'])
        st.caption('Banco externo persistente' if url else 'Banco local de desenvolvimento')
        if st.button('Sair'):
            st.session_state.pop('authenticated_key',None)
            st.rerun()
    st.title(page)
    if st.session_state.get('notice'):
        st.success(st.session_state.pop('notice'))
    if page=='Dashboard':
        d=call('dashboard')
        cols=st.columns(4)
        for col,label,value in zip(cols,['Projetos ativos','Tarefas planejadas','Aguardando configuração','Publicações'],[d['projects'],d['total_tasks'],d['tasks'].get('blocked',0),d['published']]):
            col.metric(label,value)
        st.subheader('Tudo começa com uma boa história.')
        st.write('Organize seus projetos, importe seu contexto e prepare lotes de conteúdo.')
        st.info('Esta versão organiza e planeja a produção. Muse AI, geração de vídeos e postagem no Facebook ainda não estão implementados.')
        for p in projects:
            with st.container(border=True):
                st.subheader(p['name'])
                st.text(p['description'])
                st.caption(f"{p['settings']['aspect_ratio']} · {p['settings']['duration_min']}–{p['settings']['duration_max']}s"+(' · arquivado' if p['archived'] else ''))
    elif page=='Projetos':
        projects_view(ws,projects)
    elif page=='Central de Inteligência':
        if projects:
            pid=st.selectbox('Selecione o projeto',[p['id'] for p in projects],format_func=lambda pid:next(p['name'] for p in projects if p['id']==pid))
            context_view(ws,next(p for p in projects if p['id']==pid))
        else:
            st.info('Crie um projeto primeiro.')
    elif page=='Operação em Massa':
        batches_view(ws,projects)
    elif page=='Produção':
        st.button('Atualizar fila')
        number=st.number_input('Página da fila',min_value=1,value=1)
        tasks=call('tasks',limit=100,offset=(number-1)*100)
        st.caption(f"{tasks['total']} tarefas · horários em UTC; veja o fuso do projeto no calendário")
        st.dataframe(tasks['items'],hide_index=True,use_container_width=True)
        if tasks['items']:
            tid=st.selectbox('Inspecionar tarefa',[t['id'] for t in tasks['items']],format_func=lambda tid:next(f"{t['project_name']} · vídeo {t['position']}" for t in tasks['items'] if t['id']==tid))
            st.json(call('task',tid=tid))
        if ws.app.state.worker_error:
            st.warning(ws.app.state.worker_error)
    elif page=='Calendário':
        selected=st.date_input('Mês para consultar',value=datetime.now(ZoneInfo('America/Bahia')).date())
        rows=call('calendar',month=selected.strftime('%Y-%m'))
        st.caption('Horários planejados no fuso de cada projeto; não são publicações confirmadas na Meta.')
        st.dataframe([{k:r[k] for k in ('local_date','local_time','timezone','name','status','batch_status')} for r in rows],hide_index=True,use_container_width=True)
    elif page=='Integrações e Páginas':
        for i in call('integrations')['providers']:
            with st.container(border=True):
                st.subheader(i['name'])
                st.caption(i['status'])
                st.text(i['detail'])
        st.info('Nenhuma página do Facebook conectada. OAuth ainda não implementado.')
    elif page=='Automação do Desktop':
        st.info('Não implementado. Nenhum computador conectado ou permissão concedida.')
    elif page=='Histórico':
        st.dataframe(call('history'),hide_index=True,use_container_width=True)
    elif page=='Configurações':
        st.write('Banco: '+ws.app.state.database.kind)
        st.write('Os contextos são persistidos no banco. A hospedagem gratuita pode suspender o aplicativo e interromper o processamento.')
        st.info('Esta versão não chama provedores pagos. Agendamento de postagem com o aplicativo desligado ainda não está implementado.')


try:
    run()
except HTTPException as exc:
    st.error(str(exc.detail))
except ValidationError as exc:
    st.error('; '.join(str(e['msg']) for e in exc.errors()))
except Exception:
    # Do not render driver exceptions, DSNs, imported context or credentials.
    st.error('Não foi possível concluir a operação. Confira a configuração segura do banco e tente novamente. Nenhuma credencial será exibida aqui.')
