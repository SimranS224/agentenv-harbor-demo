#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export XDG_STATE_HOME="$PWD/.trial-state"
export AGENT_ENV_CONFIG="$PWD/.agentenv/config.toml"
export HARBOR_DEMO_PROFILE="${1:-all}"
export HARBOR_DEMO_MODE="${2:-controls}"
case "$HARBOR_DEMO_MODE" in controls|model|codex) ;; *) echo 'Choose controls, model, or codex'; exit 2;; esac
case "$HARBOR_DEMO_PROFILE" in all|standard|offline|constrained) ;; *) echo 'Choose all, standard, offline, constrained'; exit 2;; esac
AGENTENV_BIN="${AGENTENV_BIN:-agent-env}"
exec "$AGENTENV_BIN" run "$PWD/bundle"
