"""Portable evidence report: no server, external scripts, or model calls."""
import html
import json
from pathlib import Path


def write_report(report, out):
    out = Path(out)
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    rows = report['results']
    lines = ['# One task. Three environments.', '', report['scope'], '',
             f'AgentEnv instance: `{report.get("agentenv_instance_id")}`',
             f'Task SHA256: `{report["task_sha256"]}`',
             f'Inputs unchanged: **{report["task_unchanged"]}**', '',
             '| Environment | Attempt | Reward | Model status | Tool calls | Cost USD* | Seconds | Cleanup |',
             '|---|---|---:|---|---:|---:|---:|---|']
    for r in rows:
        a = r.get('agent', {})
        cost = 'Plan usage' if a.get('cost_usd') is None and a else f'{a.get("cost_usd", 0):.6f}'
        lines.append(f'| {r["profile"]} | {r["mode"]} | {r.get("reward", "ERROR")} | '
                     f'{a.get("status", "control")} | {a.get("tool_calls", "—")} | '
                     f'{cost} | {r["seconds"]} | {r["cleanup_ok"]} |')
    if report.get('billing'):
        lines += ['', report['billing'], '',
                  '| Environment | Model | Input tokens | Cached input | Output tokens |',
                  '|---|---|---:|---:|---:|']
        for r in rows:
            a = r.get('agent', {})
            lines.append(f'| {r["profile"]} | {a.get("model", "—")} | {a.get("input_tokens", 0)} | '
                         f'{a.get("cached_input_tokens", 0)} | {a.get("output_tokens", 0)} |')
        if any(r.get('agent', {}).get('status') == 'token_stop' for r in rows):
            lines += ['', 'Token-stop status means the controller interrupted at its cumulative '
                      'usage threshold. The patch was then graded independently. Input counts include '
                      'repeated context; timing includes model inference and container setup/verification.']
    if 'budget' in report:
        b = report['budget']
        lines += ['', f'Run API cost*: ${b["run_cost_usd"]:.6f}. Cumulative committed '
                  f'(including unresolved reservations): ${b["cumulative_committed_usd"]:.6f} / $1.00.',
                  '*Token usage × uncached list prices; conservative when caching applies. VM excluded.']
    lines += ['', '## What AgentEnv adds in this demo', '',
              'The existing AgentEnv task-step interface carries a Harbor-format task into the same '
              'task registry and persisted run context used by the other AgentEnv workflows. '
              'Profile and attempt mode are runtime overrides; the bundle and Harbor task remain unchanged.', '',
              'This adapter implements the Docker controls, budget guard, trace collection and report. '
              'Those are adapter features, not evidence that Harbor lacks them. Harbor already supports '
              'agents, sandbox backends and rollouts. No Harbor CLI comparison was run.', '',
              'Offline applies to the code sandbox. Model inference runs on the networked controller. '
              'Tests arrive only after candidate execution; the scripted solution never enters model trials. '
              'A model failure remains in the report. Single attempts cannot establish statistical differences.', '',
              'Open index.html for patches, verifier logs, and command-by-command evidence.']
    (out / 'summary.md').write_text('\n'.join(lines) + '\n')
    esc = lambda x: html.escape(str(x))
    cards = []
    for r in rows:
        a = r.get('agent', {})
        prefix = f'{r["profile"]}-{r["mode"]}'
        trace_path = out / f'{prefix}-trace.jsonl'
        trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
        tools = ''.join('<details><summary>Command ' + str(i + 1) + '</summary><pre>' +
                        esc(t['command']) + '</pre><pre>' + esc(json.dumps(t['result'], indent=2)) +
                        '</pre></details>' for i, t in enumerate(t for t in trace if t['event'] == 'tool'))
        verifier = out / f'{prefix}-verifier.log'
        status = 'PASS' if r.get('reward') == 1 else ('FAIL' if r.get('reward') == 0 else 'ERROR')
        if r['mode'] not in {'model', 'codex'}:
            status = 'PASS' if r.get('control_ok') else 'ERROR'
        label = 'CONTROL OK' if r['mode'] not in {'model', 'codex'} and status == 'PASS' else status
        cost = 'Plan usage' if a.get('cost_usd') is None and a else f'${a.get("cost_usd", 0):.4f}'
        cards.append(f'''<article><div class="eyebrow">{esc(r['profile'])} / {esc(r['mode'])}</div>
<h2 class="{status.lower()}">{label}</h2>
<p>{esc(r['settings']['network'])} network · {r['settings']['memory_mb']} MB · {r['settings']['cpus']} CPU</p>
<dl><div><dt>Time</dt><dd>{r['seconds']}s</dd></div><div><dt>Shell commands</dt><dd>{a.get('tool_calls', '—')}</dd></div>
<div><dt>Billing</dt><dd>{cost}</dd></div></dl>
<p>Agent: {esc(a.get('status', 'scripted control'))} · Cleanup: {esc(r['cleanup_ok'])}</p>
<p>{esc(a.get('model', ''))} · Input tokens: {a.get('input_tokens', 0)} · Output tokens: {a.get('output_tokens', 0)}</p>
<p>{esc(r.get('error', a.get('error', '')))}</p>
<details><summary>Observed runtime settings</summary><pre>{esc(json.dumps(r.get('observed', {}), indent=2))}</pre></details>
<details><summary>Inspect the patch</summary><pre>{esc(r.get('patch', 'No model patch recorded.'))}</pre></details>
<details><summary>Agent’s final response</summary><pre>{esc(a.get('final_message', 'No final response recorded.'))}</pre></details>
<details><summary>Hidden verifier output</summary><pre>{esc(verifier.read_text() if verifier.exists() else 'Unavailable')}</pre></details>
{tools}</article>''')
    b = report.get('budget', {})
    budget_text = (f'Run cost*: <strong>${b["run_cost_usd"]:.4f}</strong> · Cumulative budget committed: '
                   f'${b["cumulative_committed_usd"]:.4f} / $1.00' if b
                   else esc(report.get('billing', 'Scripted controls only. No model API calls.')))
    model_rows = [r for r in rows if r['mode'] in {'model', 'codex'}]
    result_text = (f'{sum(r.get("reward") == 1 for r in model_rows)} / {len(model_rows)} repairs passed the hidden verifier.'
                   if model_rows else 'Positive and negative controls verify the harness.')
    usage_note = ('ChatGPT plan usage is reported in tokens, not an inferred dollar cost. '
                  'Token-stop attempts are graded after interruption. Timing includes inference and setup.'
                  if report.get('codex') else '*API usage at uncached list prices (conservative); excludes VM cost.')
    document = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AgentEnv × Harbor · Experiment evidence</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#10161c;color:#eaf1f4;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1300px;margin:auto;padding:50px 24px}}.eyebrow{{text-transform:uppercase;letter-spacing:.14em;color:#77d9be;font-size:12px}}
h1{{font-size:clamp(34px,6vw,64px);line-height:1.05;max-width:850px;margin:16px 0}}h2{{font-size:34px;margin:12px 0}}
.intro{{max-width:800px;color:#b8c7d2}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin:30px 0}}
article,.note{{padding:24px;border:1px solid #33424b;border-radius:14px;background:#18232b}}article p{{font-size:14px;color:#b8c7d2}}
dl{{display:flex;flex-wrap:wrap;gap:22px}}dt{{font-size:12px;color:#b8c7d2}}dd{{margin:0;font-size:22px}}
.pass{{color:#7cdeb5}}.fail,.error{{color:#ffaf91}}details{{border-top:1px solid #33424b;padding:12px 0}}summary{{cursor:pointer;font-size:14px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,monospace;background:#10161c;padding:12px;border-radius:8px;max-height:500px;overflow:auto}}
code{{overflow-wrap:anywhere}}a{{color:#77d9be}}footer{{color:#9daeb9;font-size:13px;margin-top:24px}}.note p{{max-width:1000px}}
</style><main><div class="eyebrow">AgentEnv × Harbor / evidence, not a leaderboard</div>
<h1>Same repair.<br>Different environments.</h1><p class="intro">A Harbor-format Requests repair task, orchestrated through one AgentEnv task step. Expand each result to inspect what actually happened.</p>
<p><strong>{result_text}</strong></p><p>{esc(report['scope'])}</p><p>{budget_text}</p>
<section class="grid">{''.join(cards)}</section><section class="note"><div class="eyebrow">The integration benefit</div>
<h2>Bring the task into your workflow.</h2><p>AgentEnv supplies the task registry, custom step interface, runtime override seam and persisted run context. This adapter brings the Harbor task contract into that workflow and records a comparable result for every profile.</p>
<p>Harbor already supports coding agents, multiple sandbox backends and rollout logging. These trials demonstrate integration and reuse; they do not establish that AgentEnv is faster, cheaper or more capable than Harbor.</p>
<p>Docker controls, the budget ledger and this report are implemented by this adapter. Model inference stays on the controller even when the code sandbox is offline. One attempt per profile is exploratory evidence only.</p>
<p><a href="https://github.com/harbor-framework/harbor">Harbor capabilities</a> · <a href="https://developers.openai.com/api/docs/models/gpt-5.4-mini">Model pricing</a> · <a href="results.json">Raw results</a> · <a href="summary.md">Summary</a></p></section>
<footer>Task SHA256: <code>{esc(report['task_sha256'])}</code><br>Inputs unchanged: {esc(report['task_unchanged'])} · AgentEnv instance: {esc(report.get('agentenv_instance_id'))}<br>
{usage_note} No public deployment.</footer></main></html>'''
    (out / 'index.html').write_text(document)
