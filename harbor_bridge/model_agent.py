"""Small, bounded Responses agent. Credentials never enter the task container."""
from __future__ import annotations

import fcntl
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = 'gpt-5.4-mini-2026-03-17'
MAX_CALLS = 8
MAX_OUTPUT = 2048
MAX_PAYLOAD_BYTES = 32000
# USD per million tokens, verified 2026-10-13. No paid hosted tools.
INPUT_RATE = 0.75
OUTPUT_RATE = 4.50
CAP_USD = 1.0
TOOLS = [{
    'type': 'function', 'name': 'shell',
    'description': 'Run a shell command in the task sandbox at /app. Output is truncated. Each command has a 15 second limit.',
    'strict': True,
    'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}},
                   'required': ['command'], 'additionalProperties': False},
}]
SYSTEM = ('You are repairing a repository in a disposable Linux sandbox. Read /instruction.md '
          'and inspect the source. Use the shell tool to implement and locally test a minimal repair. '
          'Only source files under /app/src are writable; /tmp is available for scratch work. '
          'Do not change tests or attempt to access hidden verification files. Dependencies are '
          'preinstalled. You have at most 8 model turns and 60 seconds total. '
          'When finished, briefly describe your repair and tests.')


class BudgetExceeded(RuntimeError):
    pass


class Ledger:
    """Exclusive experiment lock; persist reservations before any network I/O.

    Crashes/uncertain API outcomes retain their full reservation. Re-running the
    demo uses the SAME ledger, not another $1 allowance. No automatic reset.
    """
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = self.path.with_suffix('.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.data = (json.loads(self.path.read_text()) if self.path.exists()
                         else {'cap_usd': CAP_USD, 'entries': []})
            if self.data['cap_usd'] != CAP_USD:
                raise ValueError('Unexpected ledger cap')
        except BaseException:
            self.lock.close()
            raise
        return self

    def __exit__(self, *_):
        self.lock.close()

    @property
    def committed(self):
        return sum(e.get('cost_usd', e['reserved_usd']) for e in self.data['entries'])

    def save(self):
        tmp = self.path.with_suffix('.tmp')
        with tmp.open('w') as f:
            json.dump(self.data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.path)

    def reserve(self, payload, trial):
        if self.data.get('halted'):
            raise BudgetExceeded('Ledger halted after usage accounting mismatch')
        # For text-only BPE input, UTF-8 bytes upper-bound content tokens.
        # Count the entire serialized body (including tool schema) plus 4096
        # tokens for framing. Reject large contexts rather than truncate them.
        size = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        if size > MAX_PAYLOAD_BYTES:
            raise BudgetExceeded('Context byte limit reached')
        bound = (size + 4096) * INPUT_RATE / 1e6 + MAX_OUTPUT * OUTPUT_RATE / 1e6
        if self.committed + bound > CAP_USD:
            raise BudgetExceeded('Cumulative $1 experiment budget reached')
        entry = {'trial': trial, 'reserved_usd': bound, 'input_token_bound': size + 4096,
                 'status': 'reserved', 'model': MODEL}
        self.data['entries'].append(entry)
        self.save()
        return entry

    def settle(self, entry, usage):
        # Charge cached input at full price: reported cost is conservative.
        i, o = usage['input_tokens'], usage['output_tokens']
        if not isinstance(i, int) or not isinstance(o, int) or min(i, o) < 0:
            raise ValueError('Invalid API usage')
        if i > entry['input_token_bound'] or o > MAX_OUTPUT:
            self.data['halted'] = True
            self.save()
            raise RuntimeError('Usage exceeded reservation bounds; stop experiment')
        entry.update(usage=usage, cost_usd=(i * INPUT_RATE + o * OUTPUT_RATE) / 1e6,
                     status='settled')
        self.save()


def api_request(payload, timeout):
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('OPENAI_API_KEY is not configured on the controller')
    request = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
        method='POST')
    try:
        # No retries: ambiguous outcomes keep their reservation in the ledger.
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'OpenAI HTTP {exc.code}; no automatic retry') from None


def run_agent(instruction, execute, ledger, trial, trace_path, timeout=60, request=api_request):
    history = [{'role': 'user', 'content': instruction}]
    deadline = time.monotonic() + timeout
    stats = {'model': MODEL, 'calls': 0, 'tool_calls': 0, 'input_tokens': 0,
             'output_tokens': 0, 'cost_usd': 0.0, 'status': 'turn_limit'}
    start_entries = len(ledger.data['entries'])
    with Path(trace_path).open('w') as log:
        def event(kind, **data):
            log.write(json.dumps({'event': kind, **data}) + '\n')
            log.flush()
        event('start', model=MODEL, instruction=instruction, system=SYSTEM)
        try:
            for turn in range(MAX_CALLS):
                left = deadline - time.monotonic()
                if left <= 1:
                    stats['status'] = 'time_limit'
                    break
                payload = {'model': MODEL, 'instructions': SYSTEM, 'input': history,
                           'tools': TOOLS, 'parallel_tool_calls': False,
                           'reasoning': {'effort': 'low'}, 'max_output_tokens': MAX_OUTPUT,
                           'store': False, 'service_tier': 'default'}
                entry = ledger.reserve(payload, trial)
                stats['calls'] += 1
                response = request(payload, timeout=min(30, left))
                # Save the received response before parsing/settling it.
                event('response', turn=turn + 1, response=response)
                ledger.settle(entry, response['usage'])
                stats['input_tokens'] += response['usage']['input_tokens']
                stats['output_tokens'] += response['usage']['output_tokens']
                output = response['output']
                history.extend(output)
                calls = [item for item in output if item['type'] == 'function_call']
                if response.get('status') != 'completed':
                    stats['status'] = 'incomplete_response'
                    break
                if not calls:
                    stats['status'] = 'completed'
                    break
                for call in calls:
                    if call['name'] != 'shell':
                        raise ValueError('Unexpected tool name')
                    cmd = json.loads(call['arguments'])['command']
                    if not isinstance(cmd, str) or len(cmd) > 16000:
                        raise ValueError('Invalid shell command')
                    left = deadline - time.monotonic()
                    if left <= 1:
                        stats['status'] = 'time_limit'
                        break
                    result = execute(cmd, min(15, left))
                    stats['tool_calls'] += 1
                    event('tool', command=cmd, result=result)
                    history.append({'type': 'function_call_output', 'call_id': call['call_id'],
                                    'output': json.dumps(result)})
                if stats['status'] == 'time_limit':
                    break
        except BudgetExceeded as exc:
            stats.update(status='budget_limit', error=str(exc))
        except Exception as exc:
            stats.update(status='error', error=str(exc))
        finally:
            entries = ledger.data['entries'][start_entries:]
            stats['cost_usd'] = sum(e.get('cost_usd', 0) for e in entries)
            stats['unresolved_reserved_usd'] = sum(e['reserved_usd'] for e in entries if e['status'] == 'reserved')
            event('end', **stats)
    return stats
