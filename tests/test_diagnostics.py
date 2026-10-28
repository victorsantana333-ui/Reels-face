import unittest
from app.database import connection_diagnostic

class DiagnosticTests(unittest.TestCase):
    def test_errors_classified_without_disclosing_input(self):
        for cause,code in [('password authentication failed','DB-AUTH'),('Tenant or user not found','DB-PROJECT'),('certificate verify failed','DB-TLS'),('could not translate host name','DB-HOST'),('connection timed out','DB-NETWORK'),('unknown failure','DB-CONNECTION')]:
            result=connection_diagnostic(Exception(cause+' postgresql://private-user:private-password@private-host/db'))
            self.assertIn(code,result)
            for secret in ['private-user','private-password','private-host','postgresql://']:
                self.assertNotIn(secret,result)
