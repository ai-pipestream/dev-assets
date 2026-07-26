#!/usr/bin/env bash
# The dev stack as a kitty grid — two tabs, generated from process-compose.yaml:
#
#   tab 1 "stack": the 16 Quarkus services, native 4x4 grid, each window
#                  running dev-pane.sh with its own startup check.
#   tab 2 "ops":   infra helpers (dev-services, djl serving + models),
#                  the frontend build (pnpm dev), docker status, btop.
#
# Same source of truth and same pane runner as dev-grid.sh (tmux flavor).
# NOTE: alternative launcher to `process-compose` — don't run both at once.
set -euo pipefail

PCY="${HOME}/.pipeline/dev/process-compose.yaml"
PANE="${HOME}/.pipeline/dev/dev-pane.sh"
FE_DIR="${FRONTEND_DIR:-/work/main/frontend/pipestream-frontend}"
SESSION_FILE="$(mktemp /tmp/pipestream-kitty-session.XXXXXX)"

# Helpers live on the ops tab; everything else is a stack service.
OPS_PROCS="dev-services dev-djl-serving dev-djl-models"

{
    echo "new_tab stack"
    echo "layout grid"
    python3 -c "
import yaml
ops = set('$OPS_PROCS'.split())
d = yaml.safe_load(open('$PCY'))
for name in d['processes']:
    if name not in ops:
        print(f'launch --title {name} $PANE {name}')"

    echo ""
    echo "new_tab ops"
    echo "layout grid"
    for p in $OPS_PROCS; do
        echo "launch --title $p $PANE $p"
    done
    echo "launch --title frontend --cwd $FE_DIR bash -lc 'pnpm dev'"
    echo "launch --title docker bash -lc 'watch -n 5 \"docker ps --format \\\"table {{.Names}}\\t{{.Status}}\\\"\"'"
    echo "launch --title btop btop"
} > "$SESSION_FILE"

echo "session: $SESSION_FILE"
echo "  tab stack: $(python3 -c "
import yaml
ops = set('$OPS_PROCS'.split())
d = yaml.safe_load(open('$PCY'))
print(sum(1 for n in d['processes'] if n not in ops))") services (grid)"
echo "  tab ops:   $(echo $OPS_PROCS | wc -w) helpers + frontend + docker + btop"
# --detach: the grid is its own process group — closing the terminal you
# launched it from (Ghostty included) won't take the stack down with it.
exec kitty --detach --session "$SESSION_FILE"
