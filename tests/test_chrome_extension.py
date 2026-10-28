import json
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright

class ExtensionTests(unittest.TestCase):
    def test_current_page_fill_stop_and_confirmation(self):
        manifest=json.loads(Path('chrome_extension/manifest.json').read_text())
        self.assertEqual(set(manifest['permissions']),{'activeTab','scripting'})
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            context=browser.new_context()
            context.route('https://example.com/**',lambda r:r.fulfill(body='<textarea id="field"></textarea><input id="password" type="password"><button id="send" onclick="window.sent=(window.sent||0)+1">Enviar</button>',content_type='text/html'))
            page=context.new_page();page.goto('https://example.com/')
            # Expose closed shadow solely to the test harness; production retains closed mode.
            page.evaluate('''() => {const original=Element.prototype.attachShadow;Element.prototype.attachShadow=function(options){return original.call(this,{...options,mode:'open'});};}''')
            page.add_script_tag(path='chrome_extension/panel.js')
            page.locator('#prompt').fill('Prompt de teste')
            page.locator('#pick').click();page.locator('#field').click()
            self.assertEqual(page.locator('#field').input_value(),'Prompt de teste')
            self.assertIsNone(page.evaluate('window.sent'))
            task={'version':1,'target':'current_tab','origin':'https://example.com','steps':[{'action':'click','selector':'#send'}]}
            page.locator('#file').set_input_files({'name':'task.json','mimeType':'application/json','buffer':json.dumps(task).encode()})
            page.locator('#run').click();page.locator('#yes').click()
            page.locator('#question').filter(has_text='Elemento:').wait_for()
            self.assertIsNone(page.evaluate('window.sent'))
            page.locator('#stop').click()
            page.wait_for_timeout(100)
            self.assertIsNone(page.evaluate('window.sent'))
            page.locator('#run').click();page.locator('#yes').click();page.locator('#question').filter(has_text='Elemento:').wait_for();page.locator('#yes').click()
            page.wait_for_function('window.sent === 1')
            self.assertEqual(len(context.pages),1)
            page.locator('#pick').click();page.locator('#password').click()
            self.assertEqual(page.locator('#password').input_value(),'')
            self.assertIn('senha',page.locator('#log').inner_text())
            page.locator('#close').click()
            self.assertEqual(page.locator('#run').count(),0)
            browser.close()
