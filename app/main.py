from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone, date, time
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from .providers import INTEGRATIONS
from .database import Database

ROOT = Path(__file__).parent
MAX_IMPORT = 2 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def ident():
    return str(uuid4())


@contextmanager
def db(app):
    with app.state.database.connection() as con:
        yield con


def event(con, action, project_id=None, detail=''):
    con.execute('INSERT INTO events VALUES (?,?,?,?,?)', (ident(), project_id, action, detail, now()))


def initialize(app):
    if not hasattr(app.state, 'database'):
        app.state.database = Database(app.state.db_path, app.state.database_url)
        app.state.database.open()
    with db(app) as con:
        if app.state.database.kind == 'postgresql':
            con.execute('BEGIN IMMEDIATE')
            con.execute('CREATE SCHEMA IF NOT EXISTS reels_face')
            con.execute('REVOKE ALL ON SCHEMA reels_face FROM PUBLIC')
        else:
            con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0, deleted_at TEXT,
            settings TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS contexts (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            name TEXT NOT NULL, content TEXT NOT NULL, digest TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(project_id,digest));
        CREATE TABLE IF NOT EXISTS preferences (
            id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), scope TEXT NOT NULL,
            production_id TEXT, category TEXT NOT NULL, instruction TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS batches (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            request_key TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL, quantity INTEGER NOT NULL,
            status TEXT NOT NULL, budget_cents INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id),
            project_id TEXT NOT NULL REFERENCES projects(id), position INTEGER NOT NULL,
            scheduled_at TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
            error TEXT, attempts INTEGER NOT NULL DEFAULT 0, snapshot TEXT,
            updated_at TEXT NOT NULL, UNIQUE(batch_id,position));
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, project_id TEXT, action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS tasks_status_idx ON tasks(status,scheduled_at);
        CREATE INDEX IF NOT EXISTS contexts_project_idx ON contexts(project_id);
        ''')
        if not con.execute("SELECT 1 FROM metadata WHERE key='seed_v1'").fetchone():
            pid = ident()
            settings = ProductionSettings(aspect_ratio='9:16', duration_min=45, duration_max=55).model_dump()
            con.execute('INSERT INTO projects VALUES (?,?,?,0,NULL,?,?,?)',
                        (pid, 'Histórias de Passarinhos', 'Histórias, personagens e continuidade visual em um só lugar.', json.dumps(settings), now(), now()))
            con.execute("INSERT INTO metadata VALUES ('seed_v1','1')")
            event(con, 'project.created', pid, 'Projeto inicial criado; contexto criativo ainda não importado.')
        # Interrupted local preparation is safe to replay: it never contacts a provider.
        con.execute("UPDATE tasks SET status='queued',updated_at=? WHERE status='preparing'", (now(),))


class ProductionSettings(BaseModel):
    aspect_ratio: str = '9:16'
    duration_min: int = Field(default=30, ge=5, le=3600)
    duration_max: int = Field(default=60, ge=5, le=3600)
    timezone: str = 'America/Bahia'
    narration: bool = False
    subtitles: bool = True
    budget_cents: int = Field(default=0, ge=0)

    @field_validator('aspect_ratio')
    @classmethod
    def ratio(cls, value):
        if value not in ('9:16', '16:9', '1:1'):
            raise ValueError('Proporção não suportada')
        return value

    @field_validator('timezone')
    @classmethod
    def tz(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Fuso horário inválido')
        return value

    @model_validator(mode='after')
    def duration(self):
        if self.duration_max < self.duration_min:
            raise ValueError('Duração máxima deve ser maior ou igual à mínima')
        return self


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=4000)
    settings: ProductionSettings = Field(default_factory=ProductionSettings)

    @field_validator('name')
    @classmethod
    def name_clean(cls, value):
        if not value.strip():
            raise ValueError('Nome obrigatório')
        return value.strip()


class Confirmation(BaseModel):
    confirm_name: str


class ArchiveInput(BaseModel):
    archived: bool


class ContextInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=MAX_IMPORT)


class PreferenceInput(BaseModel):
    scope: str = 'project'
    category: str = Field(default='Estilo visual', min_length=1, max_length=100)
    instruction: str = Field(min_length=1, max_length=10000)
    production_id: str | None = None
    confirm_global: bool = False

    @model_validator(mode='after')
    def scope_valid(self):
        if self.scope not in ('project', 'global', 'production'):
            raise ValueError('Escopo inválido')
        if not self.instruction.strip():
            raise ValueError('Instrução obrigatória')
        if self.scope == 'global' and not self.confirm_global:
            raise ValueError('Confirmação explícita necessária para preferência global')
        if self.scope == 'production' and not self.production_id:
            raise ValueError('Selecione uma tarefa para correção pontual')
        return self


class BatchInput(BaseModel):
    project_id: str
    quantity: int = Field(ge=1)
    start_date: date
    times: list[str] = Field(min_length=1, max_length=1440)
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)))
    budget_cents: int = Field(default=0, ge=0)
    request_key: str = Field(min_length=16, max_length=100)

    @field_validator('times')
    @classmethod
    def times_valid(cls, values):
        for v in values:
            if len(v) != 5 or v[2] != ':' or not v[:2].isdigit() or not v[3:].isdigit():
                raise ValueError('Use horários HH:MM')
            time.fromisoformat(v)
        if len(set(values)) != len(values):
            raise ValueError('Horários duplicados')
        return sorted(values)

    @field_validator('weekdays')
    @classmethod
    def weekdays_valid(cls, values):
        if not values or any(v not in range(7) for v in values) or len(set(values)) != len(values):
            raise ValueError('Selecione dias válidos (segunda=0 a domingo=6)')
        return values


def project(con, pid, active=False):
    row = con.execute('SELECT * FROM projects WHERE id=? AND deleted_at IS NULL', (pid,)).fetchone()
    if not row:
        raise HTTPException(404, 'Projeto não encontrado')
    if active and row['archived']:
        raise HTTPException(409, 'Restaure o projeto antes de produzir')
    result = dict(row)
    result['settings'] = json.loads(result['settings'])
    result['archived'] = bool(result['archived'])
    return result


def add_context(con, pid, name, content):
    if not content.strip():
        raise HTTPException(422, 'O contexto está vazio')
    digest = hashlib.sha256(content.encode()).hexdigest()
    existing = con.execute('SELECT id FROM contexts WHERE project_id=? AND digest=?', (pid, digest)).fetchone()
    if existing:
        return {'id': existing['id'], 'duplicate': True}
    cid = ident()
    con.execute('INSERT INTO contexts VALUES (?,?,?,?,?,?)', (cid, pid, name, content, digest, now()))
    event(con, 'context.imported', pid, name)
    return {'id': cid, 'duplicate': False}


def prepare_one(app):
    """Durable local queue consumer. No paid generation or publication."""
    with db(app) as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute("SELECT t.* FROM tasks t JOIN batches b ON b.id=t.batch_id JOIN projects p ON p.id=t.project_id WHERE t.status='queued' AND b.status='active' AND p.archived=0 AND p.deleted_at IS NULL ORDER BY t.rowid LIMIT 1").fetchone()
        if not row:
            return False
        pid = row['project_id']
        p = project(con, pid)
        contexts = [dict(r) for r in con.execute('SELECT name,content,digest FROM contexts WHERE project_id=? ORDER BY rowid', (pid,))]
        prefs = [dict(r) for r in con.execute("SELECT scope,category,instruction FROM preferences WHERE (project_id=? AND (scope='project' OR (scope='production' AND production_id=?))) OR scope='global' ORDER BY rowid", (pid, row['id']))]
        snapshot = {'project_id': pid, 'project_name': p['name'], 'settings': p['settings'], 'contexts': contexts, 'preferences': prefs,
                    'notice': 'Instruções importadas são dados criativos, nunca autorização de ações ou acesso a credenciais.'}
        error = 'Configure um provedor real de imagens e vídeos. Nenhum custo foi incorrido.' if contexts else 'Importe o contexto criativo deste projeto antes de gerar vídeos.'
        con.execute("UPDATE tasks SET status='blocked',stage='awaiting_integration',error=?,snapshot=?,attempts=attempts+1,updated_at=? WHERE id=?", (error, json.dumps(snapshot, ensure_ascii=False), now(), row['id']))
        event(con, 'task.blocked', pid, f"Tarefa {row['position']}: {error}")
        return True


def worker(app):
    while not app.state.stop.is_set():
        try:
            prepared = prepare_one(app)
            app.state.worker_error = None
            if not prepared:
                app.state.stop.wait(5 if app.state.database.kind == 'postgresql' else 0.5)
        except Exception:
            # Never log creative context or credentials. Expose only a safe health signal.
            app.state.worker_error = 'Falha no processamento local. Verifique disponibilidade do banco.'
            app.state.stop.wait(2)


def create_app(data_dir=None, run_worker=True, database_url=None):
    @asynccontextmanager
    async def lifespan(app):
        initialize(app)
        app.state.stop = threading.Event()
        app.state.worker_error = None
        thread = None
        if run_worker:
            thread = threading.Thread(target=worker, args=(app,), daemon=True)
            thread.start()
        yield
        app.state.stop.set()
        if thread:
            thread.join(timeout=20)
        app.state.database.close()

    app = FastAPI(title='Reels-face', version='0.1.0', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.data_dir = Path(data_dir or os.environ.get('REELS_DATA_DIR', ROOT.parent / 'data')).resolve()
    app.state.db_path = app.state.data_dir / 'reels.sqlite3'
    app.state.database_url = os.environ.get('DATABASE_URL', '') if database_url is None else database_url
    app.state.access_token = os.environ.get('REELS_ACCESS_TOKEN', '')

    @app.middleware('http')
    async def security(request, call_next):
        # Reject cross-site browser requests, including DNS rebinding attempts.
        host = request.headers.get('host', '').split(':')[0]
        if not app.state.access_token and host not in ('127.0.0.1', 'localhost', '[', 'testserver'):
            return JSONResponse({'detail': 'Configure REELS_ACCESS_TOKEN antes de acesso remoto'}, status_code=403)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
                return JSONResponse({'detail': 'Origem não autorizada'}, status_code=403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': 'Origem não autorizada'}, status_code=403)
        if request.url.path.startswith('/api/') and request.url.path != '/api/health' and app.state.access_token:
            value = request.headers.get('authorization', '')
            if not secrets.compare_digest(value, 'Bearer ' + app.state.access_token):
                return JSONResponse({'detail': 'Autenticação necessária'}, status_code=401)
        response = await call_next(request)
        response.headers.update({'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
                                 'Content-Security-Policy': "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'", 'Cache-Control': 'no-store'})
        return response

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'static' / 'index.html')

    @app.get('/api/health')
    def health():
        with db(app) as con:
            con.execute('SELECT 1')
        return {'status': 'ok', 'worker_enabled': run_worker, 'worker_error': app.state.worker_error, 'database': app.state.database.kind}

    @app.get('/api/projects')
    def projects():
        with db(app) as con:
            return [project(con, r['id']) for r in con.execute('SELECT id FROM projects WHERE deleted_at IS NULL ORDER BY created_at')]

    @app.post('/api/projects', status_code=201)
    def create_project(body: ProjectInput):
        with db(app) as con:
            pid = ident()
            con.execute('INSERT INTO projects VALUES (?,?,?,0,NULL,?,?,?)', (pid, body.name, body.description, body.settings.model_dump_json(), now(), now()))
            event(con, 'project.created', pid, body.name)
            return project(con, pid)

    @app.get('/api/projects/{pid}')
    def get_project(pid: str):
        with db(app) as con:
            return project(con, pid)

    @app.put('/api/projects/{pid}')
    def update_project(pid: str, body: ProjectInput):
        with db(app) as con:
            project(con, pid)
            con.execute('UPDATE projects SET name=?,description=?,settings=?,updated_at=? WHERE id=?', (body.name, body.description, body.settings.model_dump_json(), now(), pid))
            event(con, 'project.updated', pid, body.name)
            return project(con, pid)

    @app.post('/api/projects/{pid}/archive')
    def archive(pid: str, body: ArchiveInput):
        with db(app) as con:
            project(con, pid)
            con.execute('UPDATE projects SET archived=?,updated_at=? WHERE id=?', (body.archived, now(), pid))
            if body.archived:
                con.execute("UPDATE batches SET status='paused' WHERE project_id=? AND status='active'", (pid,))
            event(con, 'project.archived' if body.archived else 'project.restored', pid)
            return project(con, pid)

    @app.delete('/api/projects/{pid}')
    def delete_project(pid: str, body: Confirmation):
        with db(app) as con:
            p = project(con, pid)
            if body.confirm_name != p['name']:
                raise HTTPException(422, 'Digite o nome exato para confirmar')
            con.execute('UPDATE projects SET deleted_at=?,archived=1 WHERE id=?', (now(), pid))
            con.execute("UPDATE batches SET status='cancelled' WHERE project_id=?", (pid,))
            con.execute("UPDATE tasks SET status='cancelled',updated_at=? WHERE project_id=? AND status IN ('queued','blocked','preparing')", (now(), pid))
            event(con, 'project.deleted', pid, 'Exclusão lógica: contexto, histórico e arquivos preservados.')
            return {'deleted': True, 'files_preserved': True}

    @app.post('/api/projects/{pid}/duplicate', status_code=201)
    def duplicate(pid: str):
        with db(app) as con:
            p = project(con, pid)
            new = ident()
            con.execute('INSERT INTO projects VALUES (?,?,?,0,NULL,?,?,?)', (new, p['name'][:110] + ' — cópia', p['description'], json.dumps(p['settings']), now(), now()))
            for row in con.execute('SELECT * FROM contexts WHERE project_id=?', (pid,)).fetchall():
                con.execute('INSERT INTO contexts VALUES (?,?,?,?,?,?)', (ident(), new, row['name'], row['content'], row['digest'], now()))
            for row in con.execute("SELECT * FROM preferences WHERE project_id=? AND scope='project'", (pid,)).fetchall():
                con.execute('INSERT INTO preferences VALUES (?,?,?,?,?,?,?)', (ident(), new, 'project', None, row['category'], row['instruction'], now()))
            event(con, 'project.duplicated', new, 'Cópia independente de contexto e preferências; sem tarefas ou correções pontuais.')
            return project(con, new)

    @app.get('/api/projects/{pid}/context')
    def contexts(pid: str):
        with db(app) as con:
            project(con, pid)
            return [dict(r) for r in con.execute('SELECT * FROM contexts WHERE project_id=? ORDER BY rowid DESC', (pid,))]

    @app.post('/api/projects/{pid}/context', status_code=201)
    def context_text(pid: str, body: ContextInput):
        with db(app) as con:
            project(con, pid)
            return add_context(con, pid, body.name, body.content)

    @app.post('/api/projects/{pid}/context/import', status_code=201)
    async def import_context(pid: str, file: UploadFile = File(...)):
        name = (file.filename or 'contexto.txt').replace('\\', '/').split('/')[-1][:200]
        if Path(name).suffix.lower() not in ('.txt', '.md', '.json'):
            raise HTTPException(422, 'Formatos aceitos: TXT, Markdown e JSON em UTF-8')
        content = await file.read(MAX_IMPORT + 1)
        await file.close()
        if len(content) > MAX_IMPORT:
            raise HTTPException(413, 'Arquivo excede 2 MB')
        try:
            text = content.decode('utf-8-sig')
            if '\x00' in text:
                raise ValueError()
            if name.lower().endswith('.json'):
                json.loads(text)
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(422, 'Arquivo inválido: use texto UTF-8; JSON deve ter sintaxe válida')
        with db(app) as con:
            project(con, pid)
            return add_context(con, pid, name, text)

    @app.delete('/api/projects/{pid}/context/{cid}')
    def remove_context(pid: str, cid: str):
        with db(app) as con:
            project(con, pid)
            if not con.execute('DELETE FROM contexts WHERE id=? AND project_id=?', (cid, pid)).rowcount:
                raise HTTPException(404, 'Contexto não encontrado')
            event(con, 'context.removed', pid)
            return {'deleted': True}

    @app.get('/api/projects/{pid}/preferences')
    def preferences(pid: str):
        with db(app) as con:
            project(con, pid)
            return [dict(r) for r in con.execute("SELECT * FROM preferences WHERE project_id=? OR scope='global' ORDER BY rowid DESC", (pid,))]

    @app.post('/api/projects/{pid}/preferences', status_code=201)
    def add_preference(pid: str, body: PreferenceInput):
        with db(app) as con:
            project(con, pid)
            if body.scope == 'production' and not con.execute('SELECT 1 FROM tasks WHERE id=? AND project_id=?', (body.production_id, pid)).fetchone():
                raise HTTPException(422, 'Tarefa não pertence ao projeto')
            prefid = ident()
            con.execute('INSERT INTO preferences VALUES (?,?,?,?,?,?,?)', (prefid, None if body.scope == 'global' else pid, body.scope, body.production_id if body.scope == 'production' else None, body.category, body.instruction.strip(), now()))
            event(con, 'preference.created', None if body.scope == 'global' else pid, body.scope)
            return {'id': prefid}

    @app.delete('/api/projects/{pid}/preferences/{prefid}')
    def delete_preference(pid: str, prefid: str, confirm_global: bool = False):
        with db(app) as con:
            project(con, pid)
            row = con.execute('SELECT * FROM preferences WHERE id=? AND (project_id=? OR scope=?)', (prefid, pid, 'global')).fetchone()
            if not row:
                raise HTTPException(404, 'Preferência não encontrada')
            if row['scope'] == 'global' and not confirm_global:
                raise HTTPException(422, 'Confirme a remoção global explicitamente')
            con.execute('DELETE FROM preferences WHERE id=?', (prefid,))
            event(con, 'preference.removed', pid, row['scope'])
            return {'deleted': True}

    @app.get('/api/integrations')
    def integrations():
        return {'providers': INTEGRATIONS, 'pages': [], 'external_actions_enabled': False}

    @app.post('/api/batches', status_code=201)
    def create_batch(body: BatchInput):
        fingerprint = hashlib.sha256(body.model_dump_json(exclude={'request_key'}).encode()).hexdigest()
        with db(app) as con:
            con.execute('BEGIN IMMEDIATE')
            old = con.execute('SELECT * FROM batches WHERE request_key=?', (body.request_key,)).fetchone()
            if old:
                if old['fingerprint'] != fingerprint:
                    raise HTTPException(409, 'Chave já utilizada com outros parâmetros')
                return dict(old)
            p = project(con, body.project_id, active=True)
            tz = ZoneInfo(p['settings']['timezone'])
            if body.start_date < datetime.now(tz).date():
                raise HTTPException(422, 'A data inicial deve ser hoje ou futura')
            # Operational guard against exhausting one HTTP request, not a product quota.
            if body.quantity > 10000:
                raise HTTPException(422, 'Este servidor aceita até 10.000 itens por solicitação. Divida a operação em lotes; não há limite de projetos.')
            if p['settings']['budget_cents'] and body.budget_cents > p['settings']['budget_cents']:
                raise HTTPException(422, 'Orçamento do lote excede o limite do projeto')
            slots = []
            day = body.start_date
            current = datetime.now(timezone.utc)
            try:
                while len(slots) < body.quantity:
                    if day.weekday() in body.weekdays:
                        for v in body.times:
                            local = datetime.combine(day, time.fromisoformat(v), tzinfo=tz)
                            utc = local.astimezone(timezone.utc)
                            # Detect nonexistent DST wall-clock times rather than silently shift them.
                            if utc.astimezone(tz).replace(tzinfo=None) != local.replace(tzinfo=None):
                                raise HTTPException(422, 'Horário inexistente na transição de fuso; escolha outro horário')
                            if utc > current:
                                slots.append(utc.isoformat())
                            if len(slots) == body.quantity:
                                break
                    if len(slots) < body.quantity:
                        day += timedelta(days=1)
            except OverflowError:
                raise HTTPException(422, 'Período fora do calendário suportado')
            bid = ident()
            con.execute('INSERT INTO batches VALUES (?,?,?,?,?,?,?,?)', (bid, body.project_id, body.request_key, fingerprint, body.quantity, 'active', body.budget_cents, now()))
            con.executemany('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)', [(ident(), bid, body.project_id, i + 1, slot, 'queued', 'context', None, 0, None, now()) for i, slot in enumerate(slots)])
            event(con, 'batch.created', body.project_id, f'{body.quantity} tarefas planejadas; estimativa indisponível; geração externa bloqueada.')
            return dict(con.execute('SELECT * FROM batches WHERE id=?', (bid,)).fetchone())

    @app.get('/api/batches')
    def batches():
        with db(app) as con:
            result = []
            for row in con.execute('SELECT b.*,p.name AS project_name FROM batches b JOIN projects p ON p.id=b.project_id ORDER BY b.created_at DESC'):
                item = dict(row)
                item['counts'] = {r['status']: r['n'] for r in con.execute('SELECT status,count(*) n FROM tasks WHERE batch_id=? GROUP BY status', (row['id'],))}
                item['estimated_cost_cents'] = None
                item['spent_cents'] = 0
                result.append(item)
            return result

    @app.post('/api/batches/{bid}/{action}')
    def batch_action(bid: str, action: str):
        if action not in ('pause', 'resume', 'cancel', 'retry'):
            raise HTTPException(404, 'Ação desconhecida')
        with db(app) as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT * FROM batches WHERE id=?', (bid,)).fetchone()
            if not row:
                raise HTTPException(404, 'Lote não encontrado')
            if row['status'] == 'cancelled':
                raise HTTPException(409, 'Um lote cancelado não pode ser retomado')
            project(con, row['project_id'], active=action in ('resume', 'retry'))
            state = {'pause': 'paused', 'resume': 'active', 'cancel': 'cancelled', 'retry': 'active'}[action]
            con.execute('UPDATE batches SET status=? WHERE id=?', (state, bid))
            if action == 'cancel':
                con.execute("UPDATE tasks SET status='cancelled',updated_at=? WHERE batch_id=? AND status IN ('queued','blocked','preparing')", (now(), bid))
            if action == 'retry':
                con.execute("UPDATE tasks SET status='queued',error=NULL,updated_at=? WHERE batch_id=? AND status='blocked'", (now(), bid))
            event(con, 'batch.' + action, row['project_id'], bid)
            return {'status': state}

    @app.get('/api/tasks')
    def tasks(project_id: str | None = None, limit: int = 100, offset: int = 0):
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        with db(app) as con:
            where, args = ('WHERE t.project_id=?', [project_id]) if project_id else ('', [])
            rows = con.execute(f'SELECT t.id,t.batch_id,t.project_id,t.position,t.scheduled_at,t.status,t.stage,t.error,t.attempts,t.updated_at,p.name AS project_name FROM tasks t JOIN projects p ON p.id=t.project_id {where} ORDER BY t.scheduled_at,t.position LIMIT ? OFFSET ?', (*args, limit, offset))
            count = con.execute(f'SELECT count(*) FROM tasks t {where}', args).fetchone()[0]
            return {'items': [dict(r) for r in rows], 'total': count, 'limit': limit, 'offset': offset}

    @app.get('/api/tasks/{tid}')
    def task(tid: str):
        with db(app) as con:
            row = con.execute('SELECT * FROM tasks WHERE id=?', (tid,)).fetchone()
            if not row:
                raise HTTPException(404, 'Tarefa não encontrada')
            result = dict(row)
            result['snapshot'] = json.loads(result['snapshot']) if result['snapshot'] else None
            return result

    @app.get('/api/calendar')
    def calendar(month: str | None = None):
        month = month or datetime.now(ZoneInfo('America/Bahia')).strftime('%Y-%m')
        try:
            first = date.fromisoformat(month + '-01')
            if first.strftime('%Y-%m') != month:
                raise ValueError()
            end = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        except ValueError:
            raise HTTPException(422, 'Mês inválido; use AAAA-MM')
        with db(app) as con:
            result = []
            for row in con.execute('SELECT t.id,t.position,t.scheduled_at,t.status,t.project_id,p.name,p.settings,b.status AS batch_status FROM tasks t JOIN projects p ON p.id=t.project_id JOIN batches b ON b.id=t.batch_id WHERE t.scheduled_at>=? AND t.scheduled_at<? ORDER BY t.scheduled_at', ((first - timedelta(days=1)).isoformat(), (end + timedelta(days=1)).isoformat())):
                item = dict(row)
                tz = ZoneInfo(json.loads(item.pop('settings'))['timezone'])
                local = datetime.fromisoformat(item['scheduled_at']).astimezone(tz)
                if local.strftime('%Y-%m') == month:
                    item['local_date'] = local.date().isoformat()
                    item['local_time'] = local.strftime('%H:%M')
                    item['timezone'] = str(tz)
                    result.append(item)
            return result

    @app.get('/api/history')
    def history(project_id: str | None = None):
        with db(app) as con:
            if project_id:
                rows = con.execute("SELECT * FROM events WHERE project_id=? OR project_id IS NULL ORDER BY rowid DESC LIMIT 200", (project_id,))
            else:
                rows = con.execute('SELECT * FROM events ORDER BY rowid DESC LIMIT 200')
            return [dict(r) for r in rows]

    @app.get('/api/dashboard')
    def dashboard():
        with db(app) as con:
            counts = {r['status']: r['n'] for r in con.execute('SELECT status,count(*) n FROM tasks GROUP BY status')}
            return {'projects': con.execute('SELECT count(*) FROM projects WHERE deleted_at IS NULL AND archived=0').fetchone()[0],
                    'tasks': counts, 'total_tasks': sum(counts.values()), 'pages': 0, 'published': 0,
                    'spent_cents': 0, 'estimated_cost_cents': None, 'external_actions_enabled': False,
                    'worker_error': app.state.worker_error}

    app.state.operations = {r.name: r.endpoint for r in app.routes if hasattr(r, 'endpoint')}
    app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
    return app


app = create_app()
