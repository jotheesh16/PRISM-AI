"""Run: python -m unittest test_regressions -v (uses only temporary data)."""
import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory()
os.environ['PRISM_DATA'] = TEMP.name
os.environ['PRISM_EMBED_MODEL'] = ''
os.environ['PRISM_VISION_MODEL'] = ''
os.environ['PRISM_CHAT_MODEL'] = 'test-model'

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models
import store
import research
import ingest
import server
from reportlab.pdfgen import canvas


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.init()
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.http.server_port}'
        buf = io.BytesIO()
        pdf = canvas.Canvas(buf)
        pdf.drawString(50, 750, 'Research revenue was 42 million in 2025. This is the audited annual report.')
        pdf.save()
        cls.pdf = buf.getvalue()
        cls.doc = cls.request('/api/documents/upload?name=sample.pdf', cls.pdf)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            rows = cls.request('/api/documents')
            if rows[0]['state'] in ('ready', 'failed'):
                break
            time.sleep(.05)
        assert rows[0]['state'] == 'ready', rows
        cls.source = research.retrieve('revenue', [cls.doc['id']])[0]

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    @classmethod
    def request(cls, path, body=None):
        req = urllib.request.Request(cls.base + path, data=body)
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)

    def test_duplicate_upload(self):
        self.assertEqual(self.doc['id'], self.request('/api/documents/upload?name=duplicate.pdf', self.pdf)['id'])
        self.assertEqual(len(self.request('/api/documents')), 1)

    def test_import_formats(self):
        import zipfile
        import pdfplumber
        from PIL import Image
        from file_import import to_pdf
        fixtures = [('note.txt', b'Text import sample'), ('data.csv', b'name,value\nRevenue,42'), ('data.json', b'{"revenue":42}')]
        image = io.BytesIO()
        Image.new('RGB', (100, 100), 'white').save(image, format='PNG')
        fixtures.append(('scan.png', image.getvalue()))
        office = {
            'report.docx': ('word/document.xml', '<document><body><p><t>Word sample</t></p></body></document>'),
            'slides.pptx': ('ppt/slides/slide1.xml', '<slide><t>Slide sample</t></slide>'),
            'book.xlsx': ('xl/worksheets/sheet1.xml', '<worksheet><row><c r="A1"><v>42</v></c></row></worksheet>'),
        }
        for name, (member, xml) in office.items():
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr(member, xml)
            fixtures.append((name, buffer.getvalue()))
        for name, data in fixtures:
            with self.subTest(name=name):
                result = to_pdf(name, data)
                with pdfplumber.open(io.BytesIO(result)) as pdf:
                    self.assertGreaterEqual(len(pdf.pages), 1)
                    if not name.endswith('.png'):
                        self.assertTrue(pdf.pages[0].extract_text())
        with self.assertRaises(ValueError):
            to_pdf('program.exe', b'binary')

    def test_text_upload_preserves_original(self):
        other = self.request('/api/workspaces', b'{"name":"Import test"}')['id']
        data = b'The import test contains readable document evidence.'
        result = self.request('/api/documents/upload?space=' + other + '&name=notes.txt', data)
        with urllib.request.urlopen(self.base + '/api/documents/' + result['id'] + '/original?space=' + other) as response:
            self.assertEqual(response.read(), data)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            doc = self.request('/api/documents/' + result['id'] + '?space=' + other)
            if doc['state'] in ('ready', 'failed'):
                break
            time.sleep(.05)
        self.assertEqual(doc['state'], 'ready')
        self.assertIn('converted PDF', doc['notes'])

    def test_conversation_clear_history_and_resume(self):
        old = self.request('/api/conversations', b'{}')['id']
        question = 'Quote the passage containing "revenue"'
        self.request('/api/chat/ask', json.dumps({'question': question, 'conversation': old}).encode())
        new = self.request('/api/conversations', b'{}')['id']
        self.assertEqual(self.request('/api/history?conversation=' + new), [])
        past = self.request('/api/history?conversation=' + old)
        self.assertEqual(len(past), 1)
        self.assertEqual(past[0]['question'], question)
        saved = self.request('/api/conversations')
        self.assertEqual(next(c for c in saved if c['id'] == old)['messages'], 1)
        self.request('/api/chat/ask', json.dumps({'question': question, 'conversation': old}).encode())
        self.assertEqual(len(self.request('/api/history?conversation=' + old)), 2)
        store.init()
        self.assertEqual(len(self.request('/api/history?conversation=' + old)), 2)

    def test_new_conversation_does_not_leak_context(self):
        old = self.request('/api/conversations', b'{}')['id']
        new = self.request('/api/conversations', b'{}')['id']
        research.ask('main', 'Quote the passage containing "revenue"', conversation=old)
        with patch('research.chat', return_value={'status': 'refuse', 'answer': 'Insufficient evidence'}) as chat:
            research.ask('main', 'What was revenue?', conversation=new)
            self.assertEqual(json.loads(chat.call_args.args[2])['previous_question'], '')
            research.ask('main', 'What was revenue?', conversation=old)
            self.assertIn('Quote the passage', json.loads(chat.call_args.args[2])['previous_question'])

    def test_conversation_workspace_isolation(self):
        other = self.request('/api/workspaces', b'{"name":"Other workspace"}')['id']
        ident = self.request('/api/conversations?space=' + other, b'{}')['id']
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/history?conversation=' + ident)
        self.assertEqual(error.exception.code, 400)

    def test_existing_history_survives_migration(self):
        import sqlite3
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'old.sqlite3'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE results(id TEXT PRIMARY KEY,space TEXT,mode TEXT,payload TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP)')
                db.execute('INSERT INTO results(id,space,mode,payload) VALUES(?,?,?,?)', ('old', 'main', 'chat', '{"question":"Original question"}'))
            db.close()
            with patch.object(store, 'DB', path):
                store.init()
                store.init()
                with store.connect() as db:
                    row = db.execute('SELECT conversation,payload FROM results').fetchone()
                    self.assertEqual(row['conversation'], 'legacy')
                    self.assertEqual(json.loads(row['payload'])['question'], 'Original question')

    def test_literal_ask_http(self):
        result = self.request('/api/chat/ask', json.dumps({'question': 'Quote the passage containing "revenue"'}).encode())
        self.assertEqual(result['status'], 'answer')
        self.assertIn('42 million', result['answer'])

    def test_verified_ask_http(self):
        draft = {'status': 'answer', 'answer': '42 million.', 'citations': [{'id': self.source['id'], 'quote': '42 million'}]}
        with patch('research.chat', side_effect=[draft, {'supported': True}]):
            result = self.request('/api/chat/ask', json.dumps({'question': 'What was revenue?'}).encode())
        self.assertEqual(result['status'], 'answer')
        self.assertEqual(result['evidence'][0]['quote'], '42 million')

    def test_invalid_citations_refused(self):
        for citations in ([], [{'id': self.source['id'], 'quote': 'invented value'}], [{'id': -1, 'quote': '42 million'}]):
            with self.subTest(citations=citations), patch('research.chat', return_value={'status': 'answer', 'answer': '99 million', 'citations': citations}):
                result = research.ask('main', 'What was revenue?')
                self.assertEqual(result['status'], 'refuse')
                self.assertIsNone(result['doc'])

    def test_native_chat_disables_thinking(self):
        with patch.dict(os.environ, {'PRISM_API_BASE': 'http://127.0.0.1:11434/v1'}), patch('models.call', return_value={'message': {'content': '{"supported":true}'}}) as call:
            self.assertEqual(models.chat('qwen3:4b', 'Return JSON', 'question'), {'supported': True})
            self.assertFalse(call.call_args.args[1]['think'])
            self.assertEqual(call.call_args.args[0], 'api/chat')

    def test_review_schema_sent_to_model(self):
        with patch.dict(os.environ, {'PRISM_API_BASE': 'http://127.0.0.1:11434/v1'}), patch('models.call', return_value={'message': {'content': '{"supported":true}'}}) as call:
            models.chat('qwen3:4b', 'Verify JSON', 'question', schema=research.REVIEW_SCHEMA)
            self.assertEqual(call.call_args.args[1]['format'], research.REVIEW_SCHEMA)

    def test_malformed_verdict_is_error_not_refusal(self):
        draft = {'status': 'answer', 'answer': '42 million', 'citations': [{'id': self.source['id'], 'quote': '42 million'}]}
        with patch('research.chat', side_effect=[draft, {'question': 'echoed input'}]):
            with self.assertRaises(models.ServiceError):
                research.ask('main', 'What was revenue?')

    def test_partial_output_rejected(self):
        with patch('models.call', return_value={'message': {'content': '{"answer":"partial', 'reasoning': '{"answer":"secret"}'}}), patch.dict(os.environ, {'PRISM_API_BASE': 'http://127.0.0.1:11434/v1'}):
            with self.assertRaises(models.ServiceError):
                models.chat('qwen3:4b', 'JSON', 'question')

    def test_keyless_remote_embeddings_use_configured_model(self):
        with patch.dict(os.environ, {'PRISM_EMBED_MODEL': 'nomic-embed-text', 'PRISM_API_KEY': ''}), patch('models.get_minilm') as local, patch('models.call', return_value={'data': [{'index': 0, 'embedding': [1., 0.]}]}):
            self.assertEqual(models.embed(['test']).shape, (1, 2))
            local.assert_not_called()

    def test_embedding_outage_preserves_search(self):
        with store.connect() as db:
            db.execute("UPDATE evidence SET model='test',vector=?", (b'1234',))
        with patch.dict(os.environ, {'PRISM_EMBED_MODEL': 'test'}), patch('research.embed', side_effect=models.ServiceError('offline')):
            self.assertTrue(research.retrieve('revenue', [self.doc['id']]))

    def test_vision_one_call_per_page(self):
        from types import SimpleNamespace
        from PIL import Image
        page = SimpleNamespace(images=[{'x0': 0, 'top': 0, 'x1': 100, 'bottom': 100, 'width': 100, 'height': 100}] * 4, width=200, height=200, curves=[], lines=[], rects=[])
        with patch('ingest.chat', return_value={'evidence': 'Chart value 42'}) as chat:
            items = list(ingest.visuals(page, Image.new('RGB', (200, 200))))
        self.assertEqual(chat.call_count, 1)
        self.assertEqual(len(items), 1)


if __name__ == '__main__':
    unittest.main()
