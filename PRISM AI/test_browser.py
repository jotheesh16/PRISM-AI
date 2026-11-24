"""Set PRISM_NODE and PRISM_PLAYWRIGHT to installed runtimes, then run this file."""
import os
import subprocess
from pathlib import Path
from test_regressions import RegressionTests

RegressionTests.setUpClass()
try:
    if os.getenv('PRISM_LIVE_TEST') == '1':
        os.environ['PRISM_CHAT_MODEL'] = 'qwen3:4b'
        os.environ['PRISM_API_BASE'] = 'http://127.0.0.1:11434/v1'
    env = dict(os.environ, PRISM_TEST_URL=RegressionTests.base)
    subprocess.run([env['PRISM_NODE'], str(Path(__file__).with_suffix('.cjs'))],
                   env=env, check=True, timeout=90)
finally:
    RegressionTests.tearDownClass()
