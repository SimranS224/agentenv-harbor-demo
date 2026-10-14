"""ChatGPT-authenticated Codex, with one client-executed Docker tool.

Uses the supported app-server protocol, never reads or copies auth tokens.
No API-key fallback and no host environment exposed to the model.
"""
from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import tempfile
import threading
import time
import tomllib
from collections import deque
from pathlib import Path

MODEL = 'gpt-5.6-luna'
MAX_TOOLS = 8
TOKEN_STOP = 32000  # Stop at the next usage event; not a billing/token hard cap.
SYSTEM = ('You are a coding agent repairing a repository in a disposable Linux container. '
          'Your only environment tool is sandbox_shell. It executes at /app inside that container. '
          'Read the task instruction, inspect the source, implement the smallest correct repair, '
          'and run your own focused checks. Only /app/src and scratch space are writable. '
          'Do not change tests or try to obtain hidden tests or solutions. Dependencies are '
          'preinstalled; no network is needed. You have 8 shell calls and 60 seconds. '
          'Finish with a short description of the change and your checks.')
TOOL = {
    'type': 'function', 'name': 'sandbox_shell',
    'description': 'Run a shell command in the task container at /app. Maximum 15 seconds per command. Output is truncated.',
    'inputSchema': {'type': 'object', 'properties': {'command': {'type': 'string'}},
                    'required': ['command'], 'additionalProperties': False},
}


def restricted_config():
    config = {'forced_login_method': 'chatgpt', 'model_provider': 'openai',
              'web_search': 'disabled', 'project_doc_max_bytes': 0,
              'developer_instructions': '', 'tools.view_image': False}
    for name in ['shell_tool', 'apps', 'plugins', 'multi_agent', 'computer_use',
                 'browser_use', 'image_generation', 'view_image', 'hooks', 'memories',
                 'shell_snapshot', 'skill_search', 'unbounded_connection_retries']:
        config['features.' + name] = False
    config['features.skip_host_skill_discovery'] = True
    # Modern models route dynamic tools through the code-mode host. It is a
    # restricted JS tool dispatcher, not shell access. Disabling it breaks all
    # dynamic calls. Host environment access is separately disabled below.
    config['features.code_mode_host'] = True
    # Disable configured MCPs explicitly; an empty merged table would not do so.
    home = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))
    path = home / 'config.toml'
    if path.exists():
        for name in tomllib.loads(path.read_text()).get('mcp_servers', {}):
            config['mcp_servers.' + json.dumps(name) + '.enabled'] = False
    return config


class AppServer:
    def __init__(self, cwd):
        self.cwd = str(cwd)
        self.config = restricted_config()
        args = ['codex', 'app-server']
        for key, value in self.config.items():
            args += ['-c', key + '=' + json.dumps(value)]
        env = {k: v for k, v in os.environ.items()
               if k not in {'OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_ORG_ID', 'OPENAI_PROJECT_ID'}}
        self.process = subprocess.Popen(args, cwd=self.cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, start_new_session=True)
        self.messages = queue.Queue()
        self.pending = deque()
        self.next_id = 0
        def read():
            try:
                for line in self.process.stdout:
                    try:
                        self.messages.put(json.loads(line))
                    except ValueError:
                        continue
            finally:
                self.messages.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def receive(self, timeout):
        item = self.pending.popleft() if self.pending else self.messages.get(timeout=max(.01, timeout))
        if item is None:
            raise RuntimeError('Codex app-server exited unexpectedly')
        return item

    def call(self, method, params, timeout=20):
        self.next_id += 1
        request_id = self.next_id
        self.send({'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + timeout
        deferred = []
        try:
            while True:
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError(f'Codex {method} timed out')
                item = self.receive(left)
                if item.get('id') == request_id and 'method' not in item:
                    if 'error' in item:
                        raise RuntimeError(f'Codex {method}: {item["error"].get("message", "error")}')
                    return item['result']
                deferred.append(item)
        finally:
            self.pending.extendleft(reversed(deferred))

    def initialize(self):
        self.call('initialize', {'clientInfo': {'name': 'agentenv_harbor', 'version': '1.0'},
                                 'capabilities': {'experimentalApi': True}})
        self.send({'method': 'initialized'})
        account = self.call('account/read', {}).get('account') or {}
        if account.get('type') != 'chatgpt':
            raise RuntimeError('Codex must be signed in with ChatGPT; API fallback is disabled')
        models = self.call('model/list', {'includeHidden': False, 'limit': 100})['data']
        if not any(m['model'] == MODEL for m in models):
            raise RuntimeError(f'{MODEL} is not in this account’s available model list')

    def close(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=3)
        self.reader.join(timeout=1)
        self.process.stdin.close()
        self.process.stdout.close()


def preflight():
    with tempfile.TemporaryDirectory(prefix='ae-codex-') as cwd:
        server = AppServer(cwd)
        try:
            server.initialize()
        finally:
            server.close()
    return {'model': MODEL, 'auth': 'chatgpt', 'api_key_fallback': False,
            'cli_version': subprocess.check_output(['codex', '--version'], text=True).strip()}


def run_codex(instruction, execute, trace_path, timeout=60, server_factory=AppServer):
    stats = {'model': MODEL, 'auth': 'chatgpt', 'tool_calls': 0, 'status': 'error',
             'cost_usd': None, 'billing': 'ChatGPT plan usage; dollar cost unavailable',
             'input_tokens': 0, 'output_tokens': 0, 'cached_input_tokens': 0,
             'api_key_fallback': False, 'host_environment_access': False}
    with Path(trace_path).open('w') as log, tempfile.TemporaryDirectory(prefix='ae-codex-') as cwd:
        def event(kind, **data):
            log.write(json.dumps({'event': kind, **data}) + '\n')
            log.flush()
        event('start', model=MODEL, instruction=instruction, system=SYSTEM, auth='chatgpt')
        server = None
        thread_id = turn_id = None
        try:
            server = server_factory(cwd)
            server.initialize()
            started = server.call('thread/start', {
                'model': MODEL, 'modelProvider': 'openai', 'allowProviderModelFallback': False,
                'ephemeral': True, 'cwd': cwd, 'sandbox': 'read-only', 'approvalPolicy': 'never',
                'environments': [], 'dynamicTools': [TOOL], 'baseInstructions': SYSTEM,
                'developerInstructions': '', 'config': server.config,
            })
            thread_id = started['thread']['id']
            stats['thread_id'] = thread_id
            if started['model'] != MODEL:
                raise RuntimeError('Codex changed the requested model')
            event('thread', thread_id=thread_id, model=started['model'], environments=[],
                  sandbox='read-only', dynamic_tools=[TOOL['name']])
            deadline = time.monotonic() + timeout
            turn = server.call('turn/start', {'threadId': thread_id,
                                            'input': [{'type': 'text', 'text': instruction}],
                                            'effort': 'low', 'environments': [],
                                            'serviceTierForTurn': 'default'}, timeout=min(20, timeout))
            turn_id = turn['turn']['id']
            stats['turn_id'] = turn_id
            stats['status'] = 'time_limit'
            while time.monotonic() < deadline:
                try:
                    message = server.receive(deadline - time.monotonic())
                except queue.Empty:
                    break
                method = message.get('method', '')
                params = message.get('params', {})
                if 'id' in message and method:
                    if method != 'item/tool/call' or params.get('tool') != TOOL['name']:
                        server.send({'id': message['id'], 'error': {'code': -32601,
                                     'message': 'Only sandbox_shell is allowed'}})
                        raise RuntimeError(f'Unexpected Codex request: {method}')
                    if params.get('threadId') != thread_id or params.get('turnId') != turn_id:
                        raise RuntimeError('Tool call belongs to a different trial')
                    if stats['tool_calls'] >= MAX_TOOLS:
                        stats['status'] = 'tool_limit'
                        break
                    args = params['arguments']
                    cmd = args.get('command') if isinstance(args, dict) else None
                    if not isinstance(cmd, str) or len(cmd) > 16000:
                        raise RuntimeError('Invalid sandbox command')
                    left = deadline - time.monotonic()
                    if left <= 1:
                        break
                    result = execute(cmd, min(15, left))
                    stats['tool_calls'] += 1
                    event('tool', command=cmd, result=result, call_id=params['callId'])
                    server.send({'id': message['id'], 'result': {
                        'contentItems': [{'type': 'inputText', 'text': json.dumps(result)}],
                        'success': True}})
                elif method == 'thread/tokenUsage/updated':
                    usage = params['tokenUsage']['total']
                    stats.update(input_tokens=usage['inputTokens'], output_tokens=usage['outputTokens'],
                                 cached_input_tokens=usage['cachedInputTokens'])
                    event('usage', usage=usage)
                    if usage['totalTokens'] >= TOKEN_STOP:
                        stats['status'] = 'token_stop'
                        break
                elif method in {'item/started', 'item/completed'}:
                    item = params['item']
                    # Environment access is disabled; fail closed if that contract changes.
                    if item['type'] in {'commandExecution', 'fileChange', 'mcpToolCall',
                                        'webSearch', 'imageGeneration', 'collabAgentToolCall'}:
                        raise RuntimeError('Unexpected built-in tool: ' + item['type'])
                    if method == 'item/completed':
                        event('item', item=item)
                        if item['type'] == 'agentMessage':
                            stats['final_message'] = item.get('text', '')
                elif method == 'turn/completed':
                    final = params['turn']
                    stats['status'] = 'completed' if final['status'] == 'completed' else 'error'
                    if final.get('error'):
                        stats['error'] = final['error'].get('message', 'Turn failed')
                    event('turn_completed', turn=final)
                    break
                elif method == 'error':
                    event('error', message=params.get('message', params.get('error', 'Codex error')))
        except Exception as exc:
            stats.update(status='error', error=str(exc))
        finally:
            if server:
                if thread_id and turn_id and stats['status'] != 'completed':
                    try:
                        server.call('turn/interrupt', {'threadId': thread_id, 'turnId': turn_id}, timeout=2)
                    except Exception:
                        pass
                server.close()
            event('end', **stats)
    return stats
