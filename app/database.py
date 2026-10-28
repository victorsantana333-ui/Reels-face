"""Storage adapter: existing SQLite locally, PostgreSQL for persistent cloud data.

SQL is authored by the application, never supplied by users. PostgreSQL tables
live in a dedicated schema not exposed by Supabase's default public REST API.
"""
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import ssl
import tempfile


class DatabaseConfigurationError(RuntimeError):
    pass


def connection_diagnostic(error):
    """Return fixed text only; never echo a driver message or connection URI."""
    message = str(error).lower()
    state = getattr(error, 'sqlstate', None)
    if state == '28P01' or 'password authentication failed' in message:
        return 'DB-AUTH: O banco recusou a autenticação. Confira o usuário e a nova senha na conexão; caracteres especiais da senha precisam de codificação URL.'
    if 'tenant or user not found' in message:
        return 'DB-PROJECT: Usuário ou projeto não encontrado no pooler. Copie novamente a URI Session pooler do seu projeto Supabase.'
    if 'certificate' in message or 'ssl' in message:
        return 'DB-TLS: Falha na verificação TLS. Confira o host Session pooler e o certificado do Supabase; não desative a verificação.'
    if 'resolve' in message or 'translate host' in message:
        return 'DB-HOST: O endereço do banco não foi localizado. Confira o host copiado do Supabase.'
    if 'timeout' in message or 'timed out' in message or 'refused' in message or 'unreachable' in message:
        return 'DB-NETWORK: O banco não respondeu. Confira se o projeto Supabase está ativo e se está usando o Session pooler na porta 5432.'
    return 'DB-CONNECTION: Não foi possível conectar ao banco. Confira a URI Session pooler, a senha e o estado do projeto no Supabase.'


class Row(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


TABLE_COLUMNS = {
    'projects': 'id,name,description,archived,deleted_at,settings,created_at,updated_at',
    'contexts': 'id,project_id,name,content,digest,created_at',
    'preferences': 'id,project_id,scope,production_id,category,instruction,created_at',
    'batches': 'id,project_id,request_key,fingerprint,quantity,status,budget_cents,created_at',
    'tasks': 'id,batch_id,project_id,position,scheduled_at,status,stage,error,attempts,snapshot,updated_at',
    'events': 'id,project_id,action,detail,created_at',
    'metadata': 'key,value',
}


def postgres_sql(sql):
    """Translate the application's small, fixed SQL dialect; values stay bound."""
    sql = re.sub(r'\browid\b', '_sequence', sql)
    for table, columns in TABLE_COLUMNS.items():
        sql = re.sub(rf'INSERT INTO {table} VALUES', f'INSERT INTO {table} ({columns}) VALUES', sql, flags=re.I)
    return sql.replace('?', '%s')


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=None):
        if sql.startswith('PRAGMA'):
            raise RuntimeError('SQLite-only statement on PostgreSQL')
        if sql == 'BEGIN IMMEDIATE':
            # Serialize preparation and batch transitions across connections.
            return self.connection.execute('SELECT pg_advisory_xact_lock(173442871, 1)')
        values = None if params is None else tuple(int(v) if isinstance(v, bool) else v for v in params)
        return self.connection.execute(postgres_sql(sql), values)

    def executemany(self, sql, rows):
        cur = self.connection.cursor()
        cur.executemany(postgres_sql(sql), rows)
        return cur

    def executescript(self, script):
        for sql in script.split(';'):
            if not sql.strip():
                continue
            if 'CREATE TABLE' in sql:
                end = sql.rfind(')')
                sql = sql[:end] + ', _sequence BIGSERIAL UNIQUE' + sql[end:]
            self.connection.execute(sql)


class Database:
    def __init__(self, path: Path, url: str = ''):
        self.path = path
        self.kind = 'postgresql' if url else 'sqlite'
        self.pool = None
        self.url = url
        self.ca_bundle = None

    def open(self):
        if not self.url:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            return
        from psycopg.conninfo import conninfo_to_dict
        from psycopg.rows import class_row
        from psycopg_pool import ConnectionPool
        try:
            params = conninfo_to_dict(self.url)
            if not self.url.startswith(('postgresql://', 'postgres://')):
                raise ValueError()
            local = params.get('host') in ('127.0.0.1', 'localhost', '::1')
            if not local:
                if params.get('sslmode', 'verify-full') != 'verify-full':
                    raise ValueError()
                params.update(sslmode='verify-full', sslrootcert=params.get('sslrootcert', 'system'))
            host = params.get('host', '').lower()
            if (host.endswith('.pooler.supabase.com') or host.endswith('.supabase.co')) and params.get('sslrootcert') == 'system':
                # Trust the project CA supplied by the owner as well as public
                # roots used by shared poolers. Hostname verification stays on.
                trusted = Path(__file__).parent / 'certs' / 'supabase-prod-ca-2021.crt'
                pem = trusted.read_text()
                ssl.PEM_cert_to_DER_cert(pem)
                roots = ssl.get_default_verify_paths().cafile
                bundle = (Path(roots).read_text() if roots else '') + '\n' + pem
                with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as out:
                    self.ca_bundle = Path(out.name)
                    out.write(bundle)
                params['sslrootcert'] = str(self.ca_bundle)
            params.pop('options', None)
            params.update(connect_timeout=10)
        except Exception:
            raise DatabaseConfigurationError('DATABASE_URL inválida ou TLS inseguro. Use URI PostgreSQL e sslmode=verify-full; nunca exponha a senha.') from None
        # A single bounded preflight preserves a useful, sanitized cause instead
        # of hiding it behind pool retries and a generic timeout.
        from psycopg import connect
        try:
            with connect(**params) as probe:
                probe.execute('SELECT 1')
        except Exception as error:
            self.close()
            raise DatabaseConfigurationError(connection_diagnostic(error)) from None
        try:
            def configure(connection):
                connection.execute('SET search_path TO reels_face')
                connection.execute("SET statement_timeout TO '15s'")
                connection.execute("SET lock_timeout TO '10s'")
                connection.commit()

            self.pool = ConnectionPool(conninfo='', kwargs={**params, 'row_factory': class_row(Row)},
                                       configure=configure,
                                       min_size=1, max_size=4, timeout=12, open=False,
                                       check=ConnectionPool.check_connection)
            self.pool.open(wait=True, timeout=15)
        except Exception:
            self.close()
            raise DatabaseConfigurationError('Não foi possível conectar ao banco. Confira a conexão, a senha e o certificado nas configurações seguras da hospedagem.') from None

    def close(self):
        if self.ca_bundle:
            self.ca_bundle.unlink(missing_ok=True)
            self.ca_bundle = None
        if self.pool:
            self.pool.close()
            self.pool = None

    @contextmanager
    def connection(self):
        if self.kind == 'postgresql':
            if not self.pool:
                raise DatabaseConfigurationError('Banco não inicializado')
            with self.pool.connection() as con:
                yield PostgresConnection(con)
            return
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
