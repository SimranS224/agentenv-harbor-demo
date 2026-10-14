from __future__ import annotations

import hashlib
import json
import os
import difflib
import subprocess
import time
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from .model_agent import Ledger, run_agent
from .report import write_report
from .codex_agent import preflight as codex_preflight, run_codex

ROOT = Path(__file__).resolve().parents[1]


def command(args, *, check=True, timeout=90):
    p = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f'{args[:3]} exited {p.returncode}: {p.stderr[-3000:]}')
    return p


def manifest(task):
    return {str(p.relative_to(task)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(task.rglob('*')) if p.is_file()}


def task_hash(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def reward(text):
    text = text.strip()
    if text not in {'0', '1'}:
        raise ValueError(f'Missing or invalid binary reward: {text!r}')
    return int(text)


def run_matrix(profile='all', task=None, mode='controls', instance_id=None):
    if mode not in {'controls', 'model', 'codex'}:
        raise ValueError('Choose controls, model, or codex')
    if mode == 'codex':
        account = codex_preflight()
        return _run_matrix(profile, task, mode, instance_id, codex_account=account)
    if mode == 'model':
        if not os.environ.get('OPENAI_API_KEY'):
            raise RuntimeError('Set OPENAI_API_KEY on the controller; no API calls made')
        with Ledger(ROOT / '.spend-ledger.json') as ledger:
            return _run_matrix(profile, task, mode, instance_id, ledger)
    return _run_matrix(profile, task, mode, instance_id)


def source_snapshot(container):
    with TemporaryDirectory() as d:
        command(['docker', 'cp', f'{container}:/app/src', d])
        root = Path(d) / 'src'
        return {str(p.relative_to(root)): p.read_text(errors='replace')
                for p in sorted(root.rglob('*.py')) if p.is_file() and not p.is_symlink()}


def source_diff(before, after):
    return ''.join(''.join(difflib.unified_diff(
        before.get(p, '').splitlines(True), after.get(p, '').splitlines(True),
        fromfile='before/' + p, tofile='after/' + p)) for p in sorted(before.keys() | after.keys()))


def _run_matrix(profile, task, mode, instance_id, ledger=None, codex_account=None):
    task = Path(task or ROOT / 'task').resolve()
    cfg = tomllib.loads((task / 'task.toml').read_text())
    # Deliberately narrow support: one Dockerfile, shell oracle, binary reward.
    if not (task / 'environment/Dockerfile').is_file():
        raise ValueError('This adapter requires a single-container Dockerfile task')
    profiles = json.loads((ROOT / 'profiles.json').read_text())
    if profile != 'all':
        profiles = {profile: profiles[profile]}
    files = manifest(task)
    identity = task_hash(files)
    image = f'agentenv-harbor-demo:{identity[:12]}'
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    out = ROOT / 'artifacts' / run_id
    out.mkdir(parents=True)
    built = command(['docker', 'build', '-t', image, str(task / 'environment')],
                    check=False, timeout=int(cfg['environment']['build_timeout_sec']))
    (out / 'build.log').write_text(built.stdout + built.stderr)
    if built.returncode:
        raise RuntimeError(f'Image build failed; see {out / "build.log"}')
    image_id = command(['docker', 'image', 'inspect', image, '--format', '{{.Id}}']).stdout.strip()
    results = []
    for name, settings in profiles.items():
        for attempt in (['noop', 'oracle'] if mode == 'controls' else [mode]):
            container = f'ae-harbor-{uuid.uuid4().hex[:12]}'
            row = dict(profile=name, mode=attempt, settings=settings, task_sha256=identity,
                       image_id=image_id, container=container)
            start = time.monotonic()
            try:
                command(['docker', 'run', '-d', '--name', container,
                         '--network', settings['network'], '--memory', f'{settings["memory_mb"]}m',
                         '--memory-swap', f'{settings["memory_mb"]}m', '--cpus', str(settings['cpus']),
                         '--pids-limit', '64', '--cap-drop', 'ALL',
                         '--security-opt', 'no-new-privileges', image_id])
                info = json.loads(command(['docker', 'inspect', container]).stdout)[0]['HostConfig']
                row['observed'] = {k: info[k] for k in ['NetworkMode', 'Memory', 'NanoCpus']}
                assert info['NetworkMode'] == settings['network']
                assert info['Memory'] == settings['memory_mb'] * 1024 * 1024
                assert info['NanoCpus'] == int(settings['cpus'] * 1e9)
                # Neither tests nor oracle are available during a candidate's work.
                command(['docker', 'cp', str(task / 'instruction.md'), f'{container}:/instruction.md'])
                if attempt in {'model', 'codex'}:
                    before = source_snapshot(container)
                    command(['docker', 'exec', container, 'chmod', '-R', 'a+rwX', '/app/src'])
                    def execute(cmd, timeout):
                        # Agent commands run unprivileged, with a container-side timeout.
                        # Controller credentials/environment are never passed through.
                        p = command(['docker', 'exec', '--user', '65534:65534', '-w', '/app',
                                     container, 'timeout', '-s', 'KILL', str(max(1, int(timeout))),
                                     'sh', '-c', cmd], check=False, timeout=timeout + 3)
                        return {'exit_code': p.returncode, 'stdout': p.stdout[:10000],
                                'stderr': p.stderr[:2000],
                                'truncated': len(p.stdout) > 10000 or len(p.stderr) > 2000}
                    if attempt == 'codex':
                        row['agent'] = run_codex((task / 'instruction.md').read_text(), execute,
                                                 out / f'{name}-codex-trace.jsonl',
                                                 timeout=int(cfg['agent']['timeout_sec']))
                    else:
                        row['agent'] = run_agent((task / 'instruction.md').read_text(), execute,
                                                 ledger, f'{run_id}/{name}',
                                                 out / f'{name}-model-trace.jsonl',
                                                 timeout=int(cfg['agent']['timeout_sec']))
                    # Stop any background candidate processes before grading.
                    command(['docker', 'stop', '-t', '1', container])
                    command(['docker', 'start', container])
                    patch = source_diff(before, source_snapshot(container))
                    (out / f'{name}-{attempt}.patch').write_text(patch)
                    row['patch'] = patch
                if attempt == 'oracle':
                    command(['docker', 'cp', str(task / 'solution'), f'{container}:/solution'])
                    solved = command(['docker', 'exec', container, 'sh', '/solution/solve.sh'],
                                     check=False, timeout=int(cfg['agent']['timeout_sec']))
                    (out / f'{name}-{attempt}-solution.log').write_text(solved.stdout + solved.stderr)
                    if solved.returncode:
                        raise RuntimeError(f'Oracle exited {solved.returncode}')
                command(['docker', 'cp', str(task / 'tests'), f'{container}:/tests'])
                verified = command(['docker', 'exec', container, 'sh', '/tests/test.sh'],
                                   check=False, timeout=int(cfg['verifier']['timeout_sec']))
                (out / f'{name}-{attempt}-verifier.log').write_text(verified.stdout + verified.stderr)
                if verified.returncode:
                    raise RuntimeError(f'Verifier infrastructure exited {verified.returncode}')
                row['reward'] = reward(command(['docker', 'exec', container, 'cat',
                                               '/logs/verifier/reward.txt']).stdout)
                if attempt in {'model', 'codex'}:
                    row['control_ok'] = row['agent']['status'] != 'error'
                else:
                    row['expected'] = 1 if attempt == 'oracle' else 0
                    row['control_ok'] = row['reward'] == row['expected']
            except Exception as e:
                row.update(error=str(e), control_ok=False)
            finally:
                try:
                    cleaned = command(['docker', 'rm', '-f', container], check=False)
                    row['cleanup_ok'] = cleaned.returncode == 0
                except Exception as e:
                    row.update(cleanup_ok=False, cleanup_error=str(e))
                row['seconds'] = round(time.monotonic() - start, 3)
            results.append(row)
            print(f'{name:12} {attempt:6} reward={row.get("reward", "ERROR")} '
                  f'control_ok={row["control_ok"]}', flush=True)
    unchanged = manifest(task) == files
    report = dict(run_id=run_id, mode=mode, agentenv_instance_id=instance_id,
                  source=cfg['metadata'], task_sha256=identity, files=files,
                  task_unchanged=unchanged, image_id=image_id, results=results,
                  scope=('Synthetic regression. One model attempt per environment; exploratory demo, not a benchmark.'
                         if mode != 'controls' else 'Synthetic regression. Scripted controls; NOT a model evaluation.'))
    if codex_account:
        report['codex'] = codex_account
        report['billing'] = 'ChatGPT plan usage. No API-key calls or API fallback. Dollar cost unavailable; VM charges excluded.'
    if ledger:
        report['budget'] = {'cap_usd': 1.0, 'cumulative_committed_usd': ledger.committed,
                            'run_cost_usd': sum(r.get('agent', {}).get('cost_usd', 0) for r in results),
                            'pricing': 'Uncached list prices; cached input charged at full price (conservative).'}
    write_report(report, out)
    print(f'Artifacts: {out}', flush=True)
    if not unchanged or not all(r['control_ok'] and r['cleanup_ok'] for r in results):
        raise RuntimeError(f'Matrix controls failed; inspect {out}')
    return report, str(out)
