"""Opt-in real Docker integration with a fake API transport; zero model spend."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harbor_bridge import runner
from harbor_bridge.model_agent import run_agent


@unittest.skipUnless(os.environ.get('HARBOR_DOCKER_TEST') == '1', 'Set HARBOR_DOCKER_TEST=1 for Docker integration')
class DockerIntegration(unittest.TestCase):
    def test_unprivileged_agent_repairs_in_all_profiles_without_hidden_inputs(self):
        real_root = runner.ROOT
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shutil.copy(real_root / 'profiles.json', root / 'profiles.json')
            def fake_agent(instruction, execute, ledger, trial, trace_path, timeout):
                count = 0
                def request(payload, timeout):
                    nonlocal count
                    count += 1
                    if count == 1:
                        cmd = """python - <<'PY'
import os
from pathlib import Path
assert os.getuid() == 65534
assert not Path('/tests').exists()
assert not Path('/solution').exists()
assert not os.environ.get('OPENAI_API_KEY')
p = Path('/app/src/requests/structures.py')
s = p.read_text()
assert 'return self._store[key][1]' in s
p.write_text(s.replace('return self._store[key][1]', 'return self._store[key.lower()][1]'))
print('Unprivileged repair; no key, hidden tests, or oracle present')
PY"""
                        output = [{'type': 'function_call', 'name': 'shell', 'call_id': 'test1',
                                   'arguments': json.dumps({'command': cmd})}]
                    else:
                        output = []
                    return {'status': 'completed', 'output': output,
                            'usage': {'input_tokens': 0, 'output_tokens': 0}}
                return run_agent(instruction, execute, ledger, trial, trace_path, timeout, request)
            with patch.object(runner, 'ROOT', root), patch.object(runner, 'run_agent', fake_agent), \
                    patch.dict(os.environ, {'OPENAI_API_KEY': 'fake-transport-no-network'}):
                report, artifacts = runner.run_matrix('all', real_root / 'task', 'model', 'integration-test')
            self.assertTrue(report['task_unchanged'])
            self.assertEqual(len(report['results']), 3)
            self.assertEqual(report['budget']['run_cost_usd'], 0)
            for row in report['results']:
                self.assertEqual(row['reward'], 1)
                self.assertTrue(row['cleanup_ok'])
                self.assertIn('+        return self._store[key.lower()][1]', row['patch'])
                trace = (Path(artifacts) / f'{row["profile"]}-model-trace.jsonl').read_text()
                self.assertIn('Unprivileged repair; no key', trace)
            # Temporary mock artifacts are removed, never published as live results.


if __name__ == '__main__':
    unittest.main()
