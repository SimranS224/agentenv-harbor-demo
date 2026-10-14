import json
import tempfile
import unittest
from pathlib import Path

from harbor_bridge.model_agent import BudgetExceeded, Ledger, MAX_CALLS, run_agent
from harbor_bridge.runner import source_diff
from harbor_bridge.report import write_report


class ModelContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_reservations_survive_restart_and_enforce_cap(self):
        path = self.root / 'ledger.json'
        with Ledger(path) as ledger:
            count = 0
            while True:
                try:
                    ledger.reserve({'input': 'x' * 30000}, 'trial')
                    count += 1
                except BudgetExceeded:
                    break
            self.assertGreater(count, 0)
            self.assertLessEqual(ledger.committed, 1)
        with Ledger(path) as ledger:
            with self.assertRaises(BudgetExceeded):
                ledger.reserve({'input': 'x' * 30000}, 'retry')

    def test_ledger_lock_excludes_concurrent_runs(self):
        with Ledger(self.root / 'ledger.json'):
            with self.assertRaises(BlockingIOError):
                with Ledger(self.root / 'ledger.json'):
                    self.fail('Concurrent ledger accepted')

    def test_agent_tool_loop_and_usage(self):
        seen = []
        def request(payload, timeout):
            seen.append(payload)
            output = ([{'type': 'function_call', 'name': 'shell', 'call_id': 'call_1',
                        'arguments': json.dumps({'command': 'python -V'})}] if len(seen) == 1
                      else [{'type': 'message', 'role': 'assistant', 'content': []}])
            return {'status': 'completed', 'output': output,
                    'usage': {'input_tokens': 100, 'output_tokens': 10}}
        commands = []
        def execute(cmd, timeout):
            commands.append(cmd)
            return {'exit_code': 0, 'stdout': 'Python 3.12', 'stderr': ''}
        with Ledger(self.root / 'ledger.json') as ledger:
            stats = run_agent('Fix it', execute, ledger, 'test', self.root / 'trace', request=request)
            self.assertEqual(stats['status'], 'completed')
            self.assertEqual(commands, ['python -V'])
            self.assertEqual(stats['calls'], 2)
            self.assertAlmostEqual(ledger.committed, .00024)
            self.assertEqual(seen[1]['input'][-2]['type'], 'function_call_output')

    def test_api_failure_is_not_retried_and_keeps_reservation(self):
        def fail(*args, **kwargs):
            raise TimeoutError('API timeout')
        with Ledger(self.root / 'ledger.json') as ledger:
            stats = run_agent('Fix it', None, ledger, 'test', self.root / 'trace', request=fail)
            self.assertEqual(stats['calls'], 1)
            self.assertEqual(stats['status'], 'error')
            self.assertGreater(stats['unresolved_reserved_usd'], 0)
            self.assertGreater(ledger.committed, 0)

    def test_oversize_context_stops_before_api_call(self):
        def unexpected(*args, **kwargs):
            self.fail('API should not be called')
        with Ledger(self.root / 'ledger.json') as ledger:
            stats = run_agent('x' * 40000, None, ledger, 'test', self.root / 'trace', request=unexpected)
            self.assertEqual(stats['status'], 'budget_limit')
            self.assertEqual(ledger.committed, 0)

    def test_patch_records_additions_deletions_and_changes(self):
        diff = source_diff({'old.py': 'old\n', 'x.py': 'a\n'}, {'new.py': 'new\n', 'x.py': 'b\n'})
        for text in ['-old', '+new', '-a', '+b']:
            self.assertIn(text, diff)

    def test_report_escapes_untrusted_patch(self):
        row = {'profile': 'offline', 'mode': 'model', 'reward': 0,
               'settings': {'network': 'none', 'memory_mb': 128, 'cpus': .25},
               'seconds': 1, 'cleanup_ok': True, 'patch': '<script>alert(1)</script>'}
        write_report({'results': [row], 'scope': 'test', 'task_sha256': 'abc', 'task_unchanged': True}, self.root)
        html = (self.root / 'index.html').read_text()
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)


if __name__ == '__main__':
    unittest.main()
