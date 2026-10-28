import unittest
from desktop_agent.policy import validate, origin

class DesktopPolicyTests(unittest.TestCase):
    def job(self, **changes):
        return {'version':1,'allowed_sites':['https://example.com'],'steps':[{'action':'open','url':'https://example.com/start'}],**changes}
    def test_authorized_navigation(self):
        self.assertEqual(validate(self.job()),{'https://example.com'})
    def test_invalid_origins(self):
        for url in ['http://example.com','file:///etc/passwd','https://u:p@example.com','https://localhost',None]:
            with self.subTest(url=url),self.assertRaises(ValueError):origin(url)
    def test_escape_and_unknown_actions(self):
        for step in [{'action':'open','url':'https://example.com.evil.test'}, {'action':'shell','selector':'x'},{'action':'open'}]:
            with self.subTest(step=step),self.assertRaises(ValueError):validate(self.job(steps=[step]))
    def test_invalid_documents(self):
        for job in [None,[],{},self.job(steps=[]),self.job(steps=[{'action':'click','selector':'button'}])]:
            with self.subTest(job=job),self.assertRaises(ValueError):validate(job)
    def test_bounded_wait(self):
        job=self.job();job['steps'].append({'action':'wait','seconds':61})
        with self.assertRaises(ValueError):validate(job)
