#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export XDG_STATE_HOME="$PWD/.trial-state"
export AGENT_ENV_CONFIG="$PWD/.agentenv/config.toml"
BIN="${AGENTENV_BIN:-agent-env}"
PY="${AGENTENV_PYTHON:-python3}"
MODE="${1:-controls}"
case "$MODE" in controls|codex) ;; *) echo 'Choose controls or codex'; exit 2;; esac
"$PY" -m lander_demo.prepare "$MODE"
"$PY" -m lander_demo.register "$(cat artifacts/latest-controller.txt)"
TASK_VERSION="$("$PY" -c 'import json; print(json.load(open("artifacts/registry.json"))["task_version"])')"
BATCH="$("$PY" -c 'import json; print(json.load(open("artifacts/registry.json"))["batch"])')"
for WORLD in earth moon mars; do
 "$BIN" task run --id worldswap-land-probe --version "$TASK_VERSION" --context-json "artifacts/seed-$WORLD.json" --output-dir "artifacts/contexts/$BATCH"
done
"$PY" -m lander_demo.collect
"$PY" -m lander_demo.viewer
