import ssl
import unittest
from pathlib import Path
from unittest.mock import patch
from app.database import Database, DatabaseConfigurationError

class CertificateTests(unittest.TestCase):
    def test_supabase_uses_project_ca_and_keeps_hostname_verification(self):
        ca=Path(__file__).resolve().parents[1]/'app/certs/supabase-prod-ca-2021.crt'
        context=ssl.create_default_context(cafile=str(ca))
        self.assertTrue(context.check_hostname)
        observed={}
        def connect(**kwargs):
            observed.update(kwargs)
            observed['pem']=Path(kwargs['sslrootcert']).read_text()
            raise OSError('deliberate test stop')
        database=Database(Path('/tmp/unused'),'postgresql://user:dummy@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=verify-full&sslrootcert=system')
        with patch('psycopg.connect',side_effect=connect):
            with self.assertRaises(DatabaseConfigurationError):
                database.open()
        self.assertEqual(observed['sslmode'],'verify-full')
        self.assertIn(ca.read_text().strip(),observed['pem'])
        self.assertFalse(Path(observed['sslrootcert']).exists())
