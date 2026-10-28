"""Run with python -m desktop_agent.agent on Windows with Chrome installed."""
import hashlib
import json
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from uuid import uuid4
from .policy import origin, validate

def file_hash(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()

class Agent:
    def __init__(self,root):
        self.root=root;root.title('Reels-face · Agente local');root.geometry('800x650')
        self.messages=queue.Queue();self.stop=threading.Event();self.thread=None;self.job=None
        self.base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'ReelsFaceAgent'
        self.base.mkdir(parents=True,exist_ok=True)
        self.downloads=None
        tk.Label(root,text='Agente local do Reels-face',font=('Segoe UI',18)).pack(pady=10)
        tk.Label(root,text='Chrome separado • Somente sites aprovados • Sem acesso remoto ao computador').pack()
        controls=tk.Frame(root);controls.pack(pady=12)
        tk.Button(controls,text='1. Abrir tarefa JSON',command=self.load).pack(side='left',padx=5)
        tk.Button(controls,text='2. Pasta de downloads',command=self.folder).pack(side='left',padx=5)
        self.start_button=tk.Button(controls,text='3. Revisar e iniciar',command=self.start);self.start_button.pack(side='left',padx=5)
        tk.Button(controls,text='PARAR',bg='#bf3030',fg='white',command=self.cancel).pack(side='left',padx=5)
        self.log=scrolledtext.ScrolledText(root,wrap='word',height=24);self.log.pack(fill='both',expand=True,padx=15,pady=10)
        tk.Label(root,text='Faça o login manualmente no Chrome. CAPTCHA e verificações exigem sua intervenção.').pack(pady=5)
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.poll)

    def write(self,text):
        self.messages.put(('log',text))

    def audit(self,event,index=None):
        # Never record prompts, credentials, URLs with queries or downloaded contents.
        row={'at':time.strftime('%Y-%m-%dT%H:%M:%S'),'event':event,'step':index}
        with (self.base/'audit.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        self.write(f"{row['at']} · {event}"+(f' · etapa {index}' if index else ''))

    def poll(self):
        try:
            while True:
                kind,payload=self.messages.get_nowait()
                if kind=='log':self.log.insert('end',payload+'\n');self.log.see('end')
                elif kind=='question':
                    title,text,event,answer=payload
                    answer.append(False if self.stop.is_set() else messagebox.askokcancel(title,text));event.set()
                elif kind=='file':
                    event,answer=payload
                    answer.append('' if self.stop.is_set() else filedialog.askopenfilename(title='Selecione o vídeo exato para enviar',filetypes=[('Vídeo','*.mp4 *.mov *.webm')]))
                    event.set()
        except queue.Empty:pass
        if self.thread and not self.thread.is_alive():self.start_button.config(state='normal')
        self.root.after(100,self.poll)

    def ask(self,title,text):
        event=threading.Event();answer=[]
        self.messages.put(('question',(title,text,event,answer)))
        while not event.wait(.1):
            if self.stop.is_set():return False
        return bool(answer and answer[0]) and not self.stop.is_set()

    def load(self):
        if self.thread and self.thread.is_alive():return
        name=filedialog.askopenfilename(filetypes=[('Tarefa Reels-face','*.json')])
        if not name:return
        try:
            if Path(name).stat().st_size>1024*1024:raise ValueError('Tarefa excede 1 MB.')
            job=json.loads(Path(name).read_text(encoding='utf-8'));validate(job)
            self.job=job;self.write('Tarefa carregada: '+str(job.get('name','Sem nome'))[:200])
        except (OSError,ValueError,KeyError,TypeError):messagebox.showerror('Arquivo inválido','Use uma tarefa exportada da área Automação do Desktop.')

    def folder(self):
        if self.thread and self.thread.is_alive():return
        path=filedialog.askdirectory(title='Autorizar pasta para downloads')
        if path:self.downloads=Path(path);self.write('Pasta de downloads escolhida.')

    def cancel(self):
        self.stop.set();self.write('Parada solicitada; o navegador será fechado ao interromper a ação corrente ; downloads podem demorar mais).')

    def close(self):
        if self.thread and self.thread.is_alive():
            if not self.stop.is_set():self.cancel()
            self.root.after(250,self.close);return
        self.root.destroy()

    def start(self):
        if not self.job or not self.downloads:messagebox.showinfo('Configuração','Carregue uma tarefa e escolha a pasta de downloads.');return
        sites=validate(self.job)
        review='Sites autorizados:\n'+'\n'.join(sorted(sites))+'\n\nEtapas:\n'
        review+='\n'.join(f"{i}. {s['action']} — {s.get('selector',s.get('url','esperar'))}" for i,s in enumerate(self.job['steps'],1))
        review+='\n\nRevise as etapas. Cliques e prompts podem consumir créditos ou alterar dados. Publicação exige confirmação separada. Não prossiga se não reconhecer uma ação.'
        if not messagebox.askokcancel('Autorizar esta operação',review):return
        self.stop.clear();self.start_button.config(state='disabled')
        self.thread=threading.Thread(target=self.run,args=(self.job.copy(),sites),daemon=True);self.thread.start()

    def run(self,job,sites):
        context=None;uploaded=None
        try:
            from playwright.sync_api import sync_playwright
            self.audit('operation.started')
            with sync_playwright() as pw:
                context=pw.chromium.launch_persistent_context(str(self.base/'chrome-profile'),channel='chrome',headless=False,accept_downloads=True,service_workers="block")
                context.set_default_timeout(20000)
                def guard(route):
                    req=route.request
                    if req.is_navigation_request():
                        try:allowed=origin(req.url) in sites
                        except ValueError:allowed=False
                        if not allowed:route.abort();self.audit('navigation.blocked');return
                    route.continue_()
                context.route('**/*',guard)
                page=None
                for i,step in enumerate(job['steps'],1):
                    if self.stop.is_set():break
                    if i>1 and time.monotonic()-started>1800:raise RuntimeError('timeout')
                    if i==1:started=time.monotonic()
                    action=step['action'];self.audit('step.started',i)
                    if action=='open':
                        page=context.new_page();page.goto(step['url'],wait_until='domcontentloaded')
                        if not self.ask('Preparar página','Faça login manualmente, se necessário. Verifique se a página está pronta e clique OK para continuar.'):break
                    else:
                        if page is None or origin(page.url) not in sites:raise RuntimeError('page not authorized')
                        if action=='wait':
                            end=time.monotonic()+step['seconds']
                            while time.monotonic()<end and not self.stop.is_set():page.wait_for_timeout(200)
                        elif action=='fill':
                            loc=page.locator(step['selector'])
                            if loc.get_attribute('type')=='password':raise RuntimeError('manual login only')
                            loc.fill(step['text'])
                        elif action=='click':
                            # Generic selectors cannot reliably distinguish publish/delete/buy.
                            if not self.ask('Confirmar clique',f"Verifique a página antes de clicar em:\n{step['selector']}\n\nConfirme apenas se a ação corresponde ao seu pedido."):break
                            page.locator(step['selector']).click()
                        elif action=='download':
                            with page.expect_download(timeout=20000) as pending:page.locator(step['selector']).click()
                            download=pending.value
                            extension=Path(download.suggested_filename).suffix.lower()
                            if extension not in {'.mp4','.mov','.webm','.png','.jpg','.jpeg','.webp','.json','.txt'}:
                                download.cancel();raise RuntimeError('unsupported download')
                            destination=self.downloads/(uuid4().hex+extension)
                            download.save_as(str(destination));self.audit('download.saved',i)
                        elif action=='upload':
                            event=threading.Event();answer=[];self.messages.put(('file',(event,answer)))
                            while not event.wait(.1):
                                if self.stop.is_set():break
                            if self.stop.is_set() or not answer or not answer[0]:break
                            path=Path(answer[0])
                            if path.suffix.lower() not in {'.mp4','.mov','.webm'}:raise RuntimeError('invalid video')
                            digest=file_hash(path)
                            if not self.ask('Confirmar envio',f'Enviar {path.name} para {origin(page.url)}?\nSHA256: {digest}'):break
                            page.locator(step['selector']).set_input_files(str(path));uploaded=(path,digest)
                        elif action=='publish':
                            if not uploaded:raise RuntimeError('select video first')
                            path,digest=uploaded
                            if file_hash(path)!=digest:raise RuntimeError('video changed')
                            if not self.ask('Confirmar publicação',f'Confirme o vídeo {path.name}, a página/conta selecionada, a descrição e o horário visíveis no navegador.\nDestino: {origin(page.url)}\nSHA256: {digest}\n\nAutoriza o clique de publicação?'):break
                            page.locator(step['selector']).click();self.audit('publication.submitted_not_verified',i)
                    self.audit('step.finished',i)
                else:
                    self.audit('operation.steps_finished')
                    self.ask('Revisar resultado','Etapas executadas. Confira o resultado no navegador. Um clique não confirma publicação. Clique OK para encerrar o navegador.')
                self.audit('operation.ended')
                context.close();context=None
        except Exception:
            self.audit('operation.failed')
            self.write('A execução parou. Confira o site, os seletores e o Chrome. Não houve repetição automática de cliques ou publicação.')
        finally:
            if context:
                try:context.close()
                except Exception:pass

if __name__=='__main__':
    root=tk.Tk();Agent(root);root.mainloop()
