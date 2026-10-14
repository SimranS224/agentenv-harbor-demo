# Verified run — 2026-10-14 UTC

## Live Codex experiment: three successful repairs using ChatGPT login

Executed through the actual AgentEnv CLI, which reported **v1, unchanged**.
Model: `gpt-5.6-luna`, low reasoning, standard speed; `codex-cli 0.151.0`.
Account type was checked as `chatgpt`; API-key fallback was disabled.

| Environment | Reward | Hidden tests | Shell calls | Wall seconds | Input tokens | Cached input | Output tokens |
|---|---:|---|---:|---:|---:|---:|---:|
| Standard, 256 MB / 1 CPU | 1 | 6 passed | 7 | 17.821 | 35,817 | 20,992 | 1,025 |
| Offline, 256 MB / 1 CPU | 1 | 6 passed | 6 | 15.114 | 34,180 | 16,384 | 888 |
| Offline, 128 MB / 0.25 CPU | 1 | 6 passed | 5 | 15.747 | 31,807 | 14,592 | 657 |

Each fresh conversation independently changed the same line:
`return self._store[key][1]` → `return self._store[key.lower()][1]`.
All attempts reached the 32,000 cumulative-token stop threshold; the controller
interrupted them and then ran the verifier. Thresholds can be exceeded by the
last in-flight response. Input counts include repeated context. Offline and
constrained attempts emitted final responses before the interrupt; standard
did not. Successful verification is independent of the model's own claims.

The transcripts also show unavailable `git`/`pytest` tooling and focused Python
checks. These failed commands remain visible. The hidden six-test verifier
does not require pytest and passed every repaired checkout.

Published evidence: [results.json](evidence/results.json), source patches and
verifier logs in [evidence/](evidence/). Local controller and container IDs are
omitted. Fresh runs additionally produce complete tool traces and an HTML report.
All containers were removed.
The task SHA256 remains `59de22027b9f25de2ecc46e7211ce022bb5b82c8d8309758ac6654be5340f027`. No API spend ledger was
created. This consumed ChatGPT/Codex allowance, not an API-key budget; no exact
dollar cost is claimed. Existing VM costs are separate.

**What this demonstrates:** the same Harbor-format task can live in the existing
AgentEnv workflow with one task identity and persisted experiment metadata,
while the adapter swaps runtime profiles. The offline and smaller code sandbox
were sufficient for this repair. It does not show AgentEnv beating Harbor:
Harbor already supports agents, backends and traces, and no Harbor CLI baseline
was run. Model inference stayed outside the sandbox. Single attempts do not
support timing, cost or general robustness conclusions. AgentEnv still reports
unscored because rewards are stored in context rather than its eval score.

**Retained infrastructure failure:** the first Codex matrix,
`artifacts/20261014T050956Z-473b6049/`, made zero container tool calls and earned
reward 0 in each profile because the adapter disabled the code-mode dispatcher
required for dynamic tools. It was fixed and checked with a harmless echo call
before the corrected matrix above. That locally retained failure and the two diagnostic echo
probes also consumed plan usage; they are not included in the successful-run
token table. No API-key calls were made in either run.

Seventeen unit tests now cover both agent paths, including the dispatcher
regression, auth rejection, tool routing, trial isolation, interruption, budget
accounting and report escaping. The generated HTML report has automated escaping checks; browser visual
review was not completed.

