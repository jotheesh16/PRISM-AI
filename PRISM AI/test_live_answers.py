"""Live Ollama smoke test using temporary reports, never user history."""
import json
import os
import time
from test_regressions import RegressionTests

RegressionTests.setUpClass()
os.environ['PRISM_CHAT_MODEL'] = 'qwen3:4b'
os.environ['PRISM_API_BASE'] = 'http://127.0.0.1:11434/v1'
import research
original_chat = research.chat
def traced_chat(*args, **kwargs):
    result = original_chat(*args, **kwargs)
    print('MODEL: ' + json.dumps(result), flush=True)
    return result
research.chat = traced_chat
try:
    # A second report makes the comparison test require two independent sources.
    second = RegressionTests.request('/api/documents/upload?name=prior-year.txt',
                                     b'Research revenue was 30 million in 2024. This is the prior audited annual report.')
    for _ in range(100):
        if RegressionTests.request('/api/documents/' + second['id'])['state'] == 'ready':
            break
        time.sleep(.05)
    for route, payload in [
        ('/api/chat/ask', {'question': 'What was the revenue in 2025?'}),
        ('/api/chat/compare', {'question': 'Compare research revenue in 2024 and 2025. What is the increase in millions? Cite both reports.'}),
        ('/api/evaluation/run', {'questions': ['What was the revenue in 2025?']}),
    ]:
        import urllib.request
        start = time.monotonic()
        req = urllib.request.Request(RegressionTests.base + route, data=json.dumps(payload).encode())
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.load(response)
        answer = result[0] if isinstance(result, list) else result
        print(json.dumps({'route': route, 'seconds': round(time.monotonic()-start, 2), 'result': answer}), flush=True)
        assert answer['status'] == 'answer' and '42' in answer['answer'] and answer['evidence'], answer
        if route.endswith('compare'):
            assert '30' in answer['answer'] and '12' in answer['answer'], answer
            assert len({e['document_id'] for e in answer['evidence']}) == 2, answer
finally:
    RegressionTests.tearDownClass()
