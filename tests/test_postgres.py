"""Run the same contract suite against an explicitly disposable local database.

REELS_TEST_DATABASE_URL must target loopback and a database ending in _test.
The test schema is recreated for each test; never point this at Supabase.
"""
import os
import unittest
from urllib.parse import urlsplit
import test_app as base
from app.database import Database, DatabaseConfigurationError
from pathlib import Path


class DatabaseSecurityTests(unittest.TestCase):
    def test_reject_insecure_remote_tls_without_leaking_credentials(self):
        secret='disposable-secret-not-for-logs'
        for url in [f'postgresql://user:{secret}@remote.example/db?sslmode=disable',
                    f'postgresql://user:{secret}@remote.example/db?sslmode=require',
                    f'https://user:{secret}@remote.example/db']:
            database=Database(Path('/tmp/not-used.sqlite'),url)
            with self.assertRaises(DatabaseConfigurationError) as exc:
                database.open()
            self.assertNotIn(secret,str(exc.exception))


@unittest.skipUnless(os.environ.get('REELS_TEST_DATABASE_URL'), 'Disposable PostgreSQL URL not provided')
class PostgresAppTests(base.AppTests):
    def setUp(self):
        import psycopg
        url=os.environ['REELS_TEST_DATABASE_URL']
        parsed=urlsplit(url)
        if parsed.hostname not in ('127.0.0.1','localhost','::1') or not parsed.path.endswith('_test'):
            raise RuntimeError('Refusing destructive tests on a nonlocal or nondisposable database')
        with psycopg.connect(url) as con:
            con.execute('DROP SCHEMA IF EXISTS reels_face CASCADE')
        self.test_database_url=url
        super().setUp()
