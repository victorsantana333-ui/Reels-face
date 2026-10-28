import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import create_app, db, prepare_one


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'REELS_ACCESS_TOKEN': ''})
        self.env.start()
        self.app = create_app(self.tmp.name, run_worker=False, database_url=getattr(self, 'test_database_url', ''))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.pid = self.client.get('/api/projects').json()[0]['id']

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.tmp.cleanup()

    def post(self, path, body):
        result = self.client.post('/api' + path, json=body)
        self.assertLess(result.status_code, 300, result.text)
        return result.json()

    def new_project(self, name='Outro projeto'):
        return self.post('/projects', {'name': name})

    def batch(self, pid=None, quantity=70, key='unique-test-batch-key'):
        return {'project_id': pid or self.pid, 'quantity': quantity,
                'start_date': (datetime.now(ZoneInfo('America/Bahia')) + timedelta(days=1)).date().isoformat(),
                'times': ['09:00', '18:00'], 'weekdays': list(range(7)), 'budget_cents': 0, 'request_key': key}

    def test_seed_once_and_defaults_not_shared(self):
        projects = self.client.get('/api/projects').json()
        self.assertEqual([p['name'] for p in projects], ['Histórias de Passarinhos'])
        self.assertEqual(projects[0]['settings']['duration_min'], 45)
        other = self.new_project()
        self.assertEqual(other['settings']['duration_min'], 30)
        from app.main import initialize
        initialize(self.app)
        self.assertEqual(len(self.client.get('/api/projects').json()), 2)

    def test_context_isolation_dedup_and_duplicate_independence(self):
        other = self.new_project()
        source = {'name': 'personagens', 'content': 'Corpo azul e peito branco'}
        self.post(f'/projects/{self.pid}/context', source)
        self.assertTrue(self.post(f'/projects/{self.pid}/context', source)['duplicate'])
        self.assertEqual(self.client.get(f"/api/projects/{other['id']}/context").json(), [])
        copy = self.post(f'/projects/{self.pid}/duplicate', {})
        rows = self.client.get(f"/api/projects/{copy['id']}/context").json()
        self.assertEqual(rows[0]['content'], source['content'])
        self.client.delete(f"/api/projects/{copy['id']}/context/{rows[0]['id']}")
        self.assertEqual(len(self.client.get(f'/api/projects/{self.pid}/context').json()), 1)

    def test_import_validation_and_untrusted_content(self):
        path = f'/api/projects/{self.pid}/context/import'
        response = self.client.post(path, files={'file': ('chat.md', '<script>alert(1)</script>'.encode(), 'text/plain')})
        self.assertEqual(response.status_code, 201)
        self.assertIn('<script>', self.client.get(f'/api/projects/{self.pid}/context').json()[0]['content'])
        for filename, content in [('bad.json', b'{'), ('bad.exe', b'x'), ('bad.txt', b'\xff'), ('empty.txt', b'  '), ('null.txt', b'a\x00b')]:
            self.assertEqual(self.client.post(path, files={'file': (filename, content)}).status_code, 422)
        self.assertEqual(self.client.post(path, files={'file': ('large.txt', b'x' * (2*1024*1024+1))}).status_code, 413)

    def test_preferences_global_explicit_and_production_ownership(self):
        other = self.new_project()
        path = f'/projects/{self.pid}/preferences'
        self.post(path, {'instruction': 'Azul', 'scope': 'project'})
        self.assertEqual(self.client.get(f"/api/projects/{other['id']}/preferences").json(), [])
        self.assertEqual(self.client.post('/api'+path, json={'instruction':'Global','scope':'global'}).status_code, 422)
        pref = self.post(path, {'instruction':'Global','scope':'global','confirm_global':True})
        self.assertEqual(len(self.client.get(f"/api/projects/{other['id']}/preferences").json()), 1)
        self.assertEqual(self.client.delete(f"/api{path}/{pref['id']}").status_code, 422)
        self.assertEqual(self.client.delete(f"/api{path}/{pref['id']}?confirm_global=true").status_code, 200)
        b = self.post('/batches', self.batch())
        task = self.client.get('/api/tasks').json()['items'][0]
        self.assertEqual(self.client.post(f"/api/projects/{other['id']}/preferences", json={'scope':'production','production_id':task['id'],'instruction':'Pontual'}).status_code, 422)

    def test_distribution_150_videos_30_days_and_idempotency(self):
        body = self.batch(quantity=150)
        body['times'] = ['09:00','12:00','15:00','18:00','21:00']
        b = self.post('/batches', body)
        again = self.post('/batches', body)
        self.assertEqual(b['id'], again['id'])
        tasks = self.client.get('/api/tasks?limit=500').json()
        self.assertEqual(tasks['total'], 150)
        dates = {datetime.fromisoformat(t['scheduled_at']).astimezone(ZoneInfo('America/Bahia')).date() for t in tasks['items']}
        self.assertEqual(len(dates), 30)
        self.assertEqual(len({t['id'] for t in tasks['items']}), 150)
        body['quantity'] = 151
        self.assertEqual(self.client.post('/api/batches',json=body).status_code, 409)
        month = body['start_date'][:7]
        entries = self.client.get('/api/calendar?month='+month).json()
        self.assertTrue(entries)
        self.assertTrue(all(t['local_time'] in body['times'] for t in entries))

    def test_weekdays_and_time_validation(self):
        body = self.batch(quantity=5)
        body['weekdays'] = [0]
        self.post('/batches',body)
        tasks = self.client.get('/api/tasks').json()['items']
        self.assertTrue(all(datetime.fromisoformat(t['scheduled_at']).astimezone(ZoneInfo('America/Bahia')).weekday()==0 for t in tasks))
        for times in [['25:00'], ['09:00','09:00'], ['9:00'], []]:
            invalid = {**body,'times':times,'request_key':'another-test-key-123'}
            self.assertEqual(self.client.post('/api/batches',json=invalid).status_code,422)
        self.assertEqual(self.client.get('/api/calendar?month=not-a-date').status_code,422)

    def test_worker_isolated_snapshot_and_no_fake_generation(self):
        other = self.new_project('Projeto privado')
        self.post(f"/projects/{other['id']}/context", {'name':'privado','content':'NUNCA VAZAR PARA OUTRO PROJETO'})
        self.post(f'/projects/{self.pid}/context', {'name':'storyboard','content':'História de pássaro'})
        self.post('/batches',self.batch(quantity=2))
        tasks=self.client.get('/api/tasks').json()['items']
        self.post(f'/projects/{self.pid}/preferences', {'scope':'production','production_id':tasks[0]['id'],'instruction':'SÓ NESTA TAREFA'})
        self.assertTrue(prepare_one(self.app))
        self.assertTrue(prepare_one(self.app))
        self.assertFalse(prepare_one(self.app))
        snapshots=[]
        for task in tasks:
            detail=self.client.get('/api/tasks/'+task['id']).json()
            self.assertEqual(detail['status'],'blocked')
            self.assertEqual(detail['attempts'],1)
            self.assertNotIn('NUNCA VAZAR',json.dumps(detail['snapshot']))
            snapshots.append(detail['snapshot'])
        self.assertEqual(sum('SÓ NESTA TAREFA' in json.dumps(s,ensure_ascii=False) for s in snapshots),1)
        d=self.client.get('/api/dashboard').json()
        self.assertEqual(d['published'],0)
        self.assertEqual(d['spent_cents'],0)
        self.assertFalse(d['external_actions_enabled'])

    def test_pause_resume_cancel_and_archive(self):
        b=self.post('/batches',self.batch(quantity=3))
        self.post(f"/batches/{b['id']}/pause",{})
        self.assertFalse(prepare_one(self.app))
        self.post(f"/batches/{b['id']}/resume",{})
        self.assertTrue(prepare_one(self.app))
        self.post(f'/projects/{self.pid}/archive',{'archived':True})
        self.assertFalse(prepare_one(self.app))
        self.assertEqual(self.client.post(f"/api/batches/{b['id']}/resume").status_code,409)
        self.post(f'/projects/{self.pid}/archive',{'archived':False})
        self.assertFalse(prepare_one(self.app))  # manual resume needed
        self.post(f"/batches/{b['id']}/retry",{})
        self.assertTrue(prepare_one(self.app))
        self.post(f"/batches/{b['id']}/cancel",{})
        self.assertTrue(all(t['status']=='cancelled' for t in self.client.get('/api/tasks').json()['items']))
        self.assertEqual(self.client.post(f"/api/batches/{b['id']}/resume").status_code,409)

    def test_soft_delete_preserves_history_context_and_stops_tasks(self):
        self.post(f'/projects/{self.pid}/context',{'name':'memo','content':'Preservar'})
        self.post('/batches',self.batch(quantity=1))
        path=f'/api/projects/{self.pid}'
        self.assertEqual(self.client.request('DELETE',path,json={'confirm_name':'Errado'}).status_code,422)
        self.assertEqual(self.client.request('DELETE',path,json={'confirm_name':'Histórias de Passarinhos'}).status_code,200)
        self.assertEqual(self.client.get(path).status_code,404)
        self.assertFalse(prepare_one(self.app))
        with db(self.app) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM contexts').fetchone()[0],1)
        self.assertTrue(self.client.get('/api/history').json())

    def test_security_auth_csrf_and_secret_never_in_html(self):
        self.assertEqual(self.client.post('/api/projects',json={'name':'x'},headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/projects',headers={'Host':'evil.example'}).status_code,403)
        self.app.state.access_token='test-secret-for-server-only'
        self.assertEqual(self.client.get('/api/projects').status_code,401)
        self.assertEqual(self.client.get('/api/projects',headers={'Authorization':'Bearer test-secret-for-server-only'}).status_code,200)
        page=self.client.get('/')
        self.assertNotIn('test-secret-for-server-only',page.text)
        self.assertIn("frame-ancestors 'none'",page.headers['content-security-policy'])

    def test_persistence_new_app(self):
        self.new_project('Persistido')
        with TestClient(create_app(self.tmp.name,run_worker=False,database_url=getattr(self, 'test_database_url', ''))) as client:
            self.assertEqual(len(client.get('/api/projects').json()),2)
            self.assertEqual(client.get('/api/projects').json()[-1]['name'],'Persistido')


if __name__ == '__main__':
    unittest.main()
