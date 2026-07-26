#!/usr/bin/env bash
# One pane of the dev grid: runs a single process from process-compose.yaml
# with its own startup check driving the tmux pane title.
#
#   ⏳ name        waiting on dependencies / starting
#   ✓ name         readiness probe passing
#   ✗ name (rc)    process exited
#
# Usage: dev-pane.sh <process-name>
set -uo pipefail

NAME="${1:?usage: dev-pane.sh <process-name>}"
PCY="${HOME}/.pipeline/dev/process-compose.yaml"
ENVF="${HOME}/.pipeline/dev/.env"

# Same env contract as process-compose: ~/.pipeline/dev/.env overrides.
set -a
# shellcheck disable=SC1090
[ -f "$ENVF" ] && . "$ENVF"
set +a

# Terminal-agnostic status: tmux pane title when under tmux, OSC2 window
# title otherwise (kitty shows it in the tab bar / window list), plus an
# in-pane banner on health transitions so terminals without per-pane title
# bars (kitty grid layout) still show state at a glance.
title() {
    if [ -n "${TMUX:-}" ]; then
        tmux select-pane -T "$1" 2>/dev/null || true
    else
        printf '\033]2;%s\033\\' "$1"
    fi
    case "$1" in
        "✓ "*) printf '\033[1;32m── %s ──\033[0m\n' "$1" ;;
        "✗ "*) printf '\033[1;31m── %s ──\033[0m\n' "$1" ;;
    esac
}

# probe_process <name>: exit 0 iff <name>'s readiness probe passes right now.
# Parses the yaml fresh each call so this file is the only logic.
probe_process() {
    python3 - "$PCY" "$1" <<'PY'
import subprocess, sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
p = d["processes"][sys.argv[2]]
probe = p.get("readiness_probe") or {}
http = probe.get("http_get") or {}
ex = (probe.get("exec") or {}).get("command", "")
# Expansion goes through bash: the yaml uses ${VAR:-default} forms that
# python's expandvars can't handle, and bash inherits the sourced .env.
if http.get("port"):
    url = 'http://%s:%s%s' % (http.get("host", "localhost"), http["port"], http.get("path", "/q/health"))
    r = subprocess.run(["bash", "-c", 'curl -sf --max-time 4 "%s"' % url], capture_output=True)
elif ex:
    r = subprocess.run(["bash", "-c", ex], capture_output=True)
else:
    sys.exit(0)  # no probe declared: treat as healthy
sys.exit(r.returncode)
PY
}

# Extract this process's definition as KEY=VALUE material.
spec_json=$(python3 - "$PCY" "$NAME" <<'PY'
import sys, json, yaml
d = yaml.safe_load(open(sys.argv[1]))
p = d["processes"].get(sys.argv[2])
if p is None:
    sys.exit("unknown process: " + sys.argv[2])
# Both dependency conditions matter. Collecting only process_healthy silently
# dropped module-embedder's `dev-djl-models: process_completed_successfully`,
# so the embedder started before its models were registered and failed for a
# reason that looked like a model bug.
deps_healthy = []
deps_done = []
for dep, cond in (p.get("depends_on") or {}).items():
    condition = (cond or {}).get("condition", "")
    if condition.startswith("process_healthy"):
        deps_healthy.append(dep)
    elif condition.startswith("process_completed"):
        deps_done.append(dep)
    else:
        deps_healthy.append(dep)   # unknown condition: wait, never skip
print(json.dumps({
    "command": p.get("command", ""),
    "working_dir": p.get("working_dir", ""),
    "is_daemon": bool(p.get("is_daemon", False)),
    "deps": " ".join(deps_healthy),
    "deps_done": " ".join(deps_done),
    "has_probe": bool(p.get("readiness_probe")),
    "env": p.get("environment") or [],
}))
PY
) || { title "✗ $NAME"; echo "failed to parse $NAME from $PCY"; exec bash; }

jget() { python3 -c "import json,sys; print(json.loads(sys.argv[1])['$1'])" "$spec_json"; }

CMD=$(jget command)
WD=$(eval echo "$(jget working_dir)")
IS_DAEMON=$(jget is_daemon)
DEPS=$(jget deps)
DEPS_DONE=$(jget deps_done)
HAS_PROBE=$(jget has_probe)

# Completion markers for `process_completed_successfully` dependencies. A
# one-shot has no readiness probe, so probe_process would call it healthy the
# instant it is asked — which is how that dependency used to get dropped. The
# pane that RUNS a probe-less process records its exit code here; panes that
# depend on it wait for a 0.
STATE_DIR="${HOME}/.pipeline/dev/.state"
mkdir -p "$STATE_DIR"
marker_for() { printf '%s/%s.rc' "$STATE_DIR" "$1"; }

# Per-process environment entries from the yaml ("KEY=VALUE" list form).
while IFS= read -r kv; do
    [ -n "$kv" ] && export "$(eval echo "$kv")"
done < <(python3 -c "import json,sys; [print(e) for e in json.loads(sys.argv[1])['env']]" "$spec_json")

# Decentralized version of process-compose's depends_on/process_healthy:
# block until every dependency's own probe passes.
for dep in $DEPS; do
    title "⏳ $NAME ← $dep"
    until probe_process "$dep"; do sleep 3; done
done

title "⏳ $NAME"

# Wherever the run ends — service exit, crash, or Ctrl-C in any of the
# loops — land in an interactive shell IN THE SERVICE DIRECTORY with a
# one-key restart. The pane never just dies.
drop_shell() {
    kill "${WATCHER:-0}" 2>/dev/null
    trap - INT TERM
    local rc="${1:-?}"
    title "✗ $NAME ($rc)"
    local rcfile
    rcfile=$(mktemp /tmp/dev-pane-rc.XXXXXX)
    cat > "$rcfile" <<RC
[ -f ~/.bashrc ] && . ~/.bashrc
PS1='[$NAME] \w \$ '
r()       { exec "$0" "$NAME"; }
restart() { exec "$0" "$NAME"; }
echo
echo "── $NAME stopped (rc=$rc) — type r to restart, or use the shell ──"
RC
    cd "${WD:-$HOME}" 2>/dev/null
    exec bash --rcfile "$rcfile" -i
}
trap 'drop_shell INT' INT TERM

# `process_completed_successfully` dependencies. A stale marker from a previous
# run would let this pane start immediately, so only markers written after this
# pane started count; dev-grid.sh starts every pane together, which makes
# "newer than my start" the right window.
PANE_START=$(date +%s)
for dep in $DEPS_DONE; do
    title "⏳ $NAME ← $dep (must complete)"
    while true; do
        m="$(marker_for "$dep")"
        if [ -f "$m" ] && [ "$(stat -c %Y "$m" 2>/dev/null || echo 0)" -ge "$PANE_START" ]; then
            dep_rc="$(cat "$m" 2>/dev/null || echo 1)"
            [ "$dep_rc" = "0" ] && break
            echo "dependency $dep exited $dep_rc; $NAME will not start" >&2
            drop_shell "dep:$dep=$dep_rc"
        fi
        sleep 3
    done
done

# Background watcher flips the title when this process's probe starts passing.
(
    until probe_process "$NAME"; do sleep 3; done
    title "✓ $NAME"
) &
WATCHER=$!

[ -n "$WD" ] && cd "$WD"
echo "── $NAME ── $CMD  (wd: ${WD:-.})"
# Disable the quarkus dev interactive console + continuous testing in grid
# panes: while a service runs, keystrokes go to quarkus — where r/e/o mean
# "run tests / edit args / toggle output". One stray keypress fired full
# test suites against the live shared stack (2026-06-12). The grid contract
# is: Ctrl-C first, THEN r restarts via our shell.
export QUARKUS_TEST_CONTINUOUS_TESTING=disabled
export QUARKUS_CONSOLE_DISABLED=true
bash -c "$CMD"
RC=$?
kill "$WATCHER" 2>/dev/null

# Publish the exit code for panes that depend on this one completing. Only
# probe-less processes are one-shots; writing markers for probed services would
# just be noise nobody reads.
if [ "$HAS_PROBE" != "True" ]; then
    printf '%s' "$RC" > "$(marker_for "$NAME")"
fi

if [ "$IS_DAEMON" = "true" ] && [ "$RC" -eq 0 ]; then
    # Daemon launchers (dev-services, djl) exit after starting containers;
    # keep the pane as a live status heartbeat (Ctrl-C drops to the shell).
    while true; do
        if probe_process "$NAME"; then title "✓ $NAME"; else title "⏳ $NAME"; fi
        sleep 20
    done
fi

echo; echo "── $NAME exited with $RC ──"
drop_shell "$RC"
