#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export XDG_STATE_HOME="$PWD/.trial-state"
export AGENT_ENV_CONFIG="$PWD/.agentenv/config.toml"
export RESCUE_MODE="${1:-controls}"
case "$RESCUE_MODE" in controls|codex) ;; *) exit 2;; esac
exec "${AGENTENV_BIN:-agent-env}" run "$PWD/bundle"
