#!/usr/bin/env bash
# The whole dev stack as a tmux grid — one pane per process-compose.yaml
# process, tiled (19 processes → 4x5), each pane running dev-pane.sh with
# its own startup check in the pane title.
#
#   dev-grid.sh            create (or attach to) the grid
#   dev-grid.sh kill       tear the session down (panes get SIGTERM)
#
# Run inside Ghostty for the single-window grid. Reattach after closing the
# terminal with `tmux attach -t pipestream` — the services keep running.
#
# NOTE: alternative launcher to `process-compose` — don't run both at once,
# they own the same ports. `bootstrap.sh dev-up` uses process-compose; this is
# the hands-on variant for when you want a shell per service.
#
# Source of truth: dev-assets/assets/dev/. `bootstrap.sh seed` copies these into
# ~/.pipeline/dev/ — edit them in the repo, not in ~/.pipeline (seed backs up a
# modified copy but the repo is what other machines get).
#
# Requires: tmux, python3 with PyYAML. PyYAML is the one dependency the
# bootstrap does not install, because only these two scripts need it.
set -euo pipefail

for tool in tmux python3; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "dev-grid.sh needs $tool on PATH." >&2; exit 1; }
done
python3 -c 'import yaml' 2>/dev/null || {
    echo "dev-grid.sh needs PyYAML to read process-compose.yaml:" >&2
    echo "  pip install --user pyyaml     (or: uv pip install --system pyyaml)" >&2
    echo "Or use the supported launcher instead: ./bootstrap.sh dev-up" >&2
    exit 1; }

SESSION="pipestream"
PCY="${HOME}/.pipeline/dev/process-compose.yaml"
PANE="${HOME}/.pipeline/dev/dev-pane.sh"

if [ "${1:-}" = "kill" ]; then
    tmux kill-session -t "$SESSION" 2>/dev/null && echo "killed $SESSION" || echo "no session"
    exit 0
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    exec tmux attach -t "$SESSION"
fi

mapfile -t PROCS < <(python3 -c "
import yaml; d = yaml.safe_load(open('$PCY'))
print('\n'.join(d['processes'].keys()))")
echo "grid: ${#PROCS[@]} processes from process-compose.yaml"

tmux new-session -d -s "$SESSION" -n stack -x "$(tput cols)" -y "$(tput lines)"
tmux set-option -t "$SESSION" pane-border-status top
tmux set-option -t "$SESSION" pane-border-format " #{pane_title} "
tmux set-option -t "$SESSION" remain-on-exit off
tmux set-option -t "$SESSION" mouse on
tmux set-option -t "$SESSION" history-limit 50000

first=1
for name in "${PROCS[@]}"; do
    if [ "$first" = 1 ]; then
        tmux respawn-pane -k -t "$SESSION:stack.0" "$PANE $name" 2>/dev/null \
            || tmux send-keys -t "$SESSION:stack.0" "exec $PANE $name" C-m
        first=0
    else
        tmux split-window -t "$SESSION:stack" "$PANE $name"
        tmux select-layout -t "$SESSION:stack" tiled
    fi
done
tmux select-layout -t "$SESSION:stack" tiled
tmux select-pane -t "$SESSION:stack.0"

exec tmux attach -t "$SESSION"
