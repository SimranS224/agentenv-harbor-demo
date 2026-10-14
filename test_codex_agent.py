import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harbor_bridge.codex_agent import AppServer, MAX_TOOLS, MODEL, TOKEN_STOP, restricted_config, run_codex
from harbor_bridge.report import write_report


def tool_call(n=0, tool='sandbox_shell'):
    return {'id': 100 + n, 'method': 'item/tool/call', 'params': {
        'threadId': 'thread-test', 'turnId': 'turn-test', 'callId': f'call-{n}',
        'tool': tool, 'arguments': {'command': 'python -V'}}}


class FakeServer:
    config = {}
    def __init__(self, events):
        self.events = iter(events)
        self.requests = []
        self.responses = []
        self.closed = False

    def initialize(self):
        pass

    def call(self, method, params, timeout=20):
        self.requests.append((method, params))
        if method == 'thread/start':
            return {'thread': {'id': 'thread-test'}, 'model': MODEL}
        if method == 'turn/start':
            return {'turn': {'id': 'turn-test'}}
        return {}

    def receive(self, timeout):
        return next(self.events)

    def send(self, message):
        self.responses.append(message)

    def close(self):
        self.closed = True


class CodexContracts(unittest.TestCase):
    def run_fake(self, events):
        server = FakeServer(events)
        calls = []
        def execute(cmd, timeout):
            calls.append(cmd)
            return {'exit_code': 0, 'stdout': 'Python 3.12', 'stderr': ''}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'trace.jsonl'
            stats = run_codex('Repair the task', execute, path, server_factory=lambda cwd: server)
            trace = [json.loads(s) for s in path.read_text().splitlines()]
        self.assertTrue(server.closed)
        return stats, server, calls, trace

    def test_tool_roundtrip_usage_and_no_host_environment(self):
        events = [tool_call(), {'method': 'thread/tokenUsage/updated', 'params': {
            'tokenUsage': {'total': {'inputTokens': 123, 'outputTokens': 25,
                                    'cachedInputTokens': 10, 'totalTokens': 148}}}},
            {'method': 'item/completed', 'params': {'item': {'type': 'agentMessage', 'text': 'Fixed.'}}},
            {'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}}]
        stats, server, calls, trace = self.run_fake(events)
        self.assertEqual(stats['status'], 'completed')
        self.assertEqual(calls, ['python -V'])
        self.assertEqual(stats['input_tokens'], 123)
        self.assertEqual(stats['final_message'], 'Fixed.')
        self.assertIsNone(stats['cost_usd'])
        for method, params in server.requests:
            if method in {'thread/start', 'turn/start'}:
                self.assertEqual(params['environments'], [])
        self.assertEqual(server.requests[0][1]['sandbox'], 'read-only')
        self.assertFalse(server.requests[0][1]['allowProviderModelFallback'])
        self.assertEqual(server.responses[0]['result']['contentItems'][0]['type'], 'inputText')

    def test_tool_limit_interrupts(self):
        stats, server, calls, _ = self.run_fake([tool_call(i) for i in range(MAX_TOOLS + 1)])
        self.assertEqual(stats['status'], 'tool_limit')
        self.assertEqual(len(calls), MAX_TOOLS)
        self.assertEqual(server.requests[-1][0], 'turn/interrupt')

    def test_unexpected_tool_is_rejected(self):
        stats, server, calls, _ = self.run_fake([tool_call(tool='host_shell')])
        self.assertEqual(stats['status'], 'error')
        self.assertFalse(calls)
        self.assertIn('error', server.responses[0])

    def test_mismatched_trial_is_rejected(self):
        call = tool_call()
        call['params']['threadId'] = 'different-thread'
        stats, _, calls, _ = self.run_fake([call])
        self.assertEqual(stats['status'], 'error')
        self.assertFalse(calls)

    def test_token_stop_interrupts(self):
        stats, server, calls, _ = self.run_fake([{'method': 'thread/tokenUsage/updated', 'params': {
            'tokenUsage': {'total': {'inputTokens': TOKEN_STOP, 'outputTokens': 1,
                                    'cachedInputTokens': 0, 'totalTokens': TOKEN_STOP + 1}}}}])
        self.assertEqual(stats['status'], 'token_stop')
        self.assertEqual(server.requests[-1][0], 'turn/interrupt')

    def test_api_auth_is_rejected(self):
        server = AppServer.__new__(AppServer)
        server.call = lambda method, params: {'account': {'type': 'apiKey'}} if method == 'account/read' else {}
        server.send = lambda message: None
        with self.assertRaisesRegex(RuntimeError, 'API fallback is disabled'):
            server.initialize()

    def test_dynamic_dispatcher_enabled_while_host_tools_disabled(self):
        with patch.object(Path, 'exists', return_value=False):
            config = restricted_config()
        self.assertTrue(config['features.code_mode_host'])
        self.assertFalse(config['features.shell_tool'])
        self.assertFalse(config['features.apps'])
        self.assertFalse(config['features.plugins'])
        self.assertEqual(config['forced_login_method'], 'chatgpt')

    def test_subscription_report_does_not_invent_dollar_cost(self):
        row = {'profile': 'offline', 'mode': 'codex', 'reward': 1, 'seconds': 12,
               'settings': {'network': 'none', 'memory_mb': 256, 'cpus': 1},
               'cleanup_ok': True, 'agent': {'cost_usd': None, 'status': 'token_stop'}}
        with tempfile.TemporaryDirectory() as d:
            write_report({'results': [row], 'scope': 'test', 'task_sha256': 'abc',
                          'task_unchanged': True, 'codex': {'auth': 'chatgpt'},
                          'billing': 'ChatGPT plan usage'}, Path(d))
            html = (Path(d) / 'index.html').read_text()
            self.assertIn('1 / 1 repairs passed', html)
            self.assertIn('Plan usage', html)
            self.assertNotIn('$0.0000', html)
            self.assertNotIn('Scripted controls only', html)


if __name__ == '__main__':
    unittest.main()
