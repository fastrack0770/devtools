#!/usr/bin/env bash
# run_codex.sh — call codex as a headless subagent.
#
# Two modes:
#   default   --sandbox read-only     — review, research, second opinion; codex cannot
#                                       change anything, so no plan is required.
#   --write   --sandbox workspace-write — code-editing thread: codex creates/edits files
#                                       and runs commands inside --cwd. Only under a
#                                       validated parallel-dev plan, with --cwd set to
#                                       that thread's worktree.
#
# usage:
#   run_codex.sh [options] "<prompt>"
#   run_codex.sh [options] -            # prompt on stdin
#
# options:
#   --write          code-editing mode (default is read-only)
#   --cwd DIR        working root for the session (a thread worktree in --write mode)
#   --model NAME     override the codex model
#   --network        allow network access in --write mode (dependency downloads);
#                    ignored in read-only mode, where the sandbox has no network anyway
#   --out FILE       keep the agent's final message in FILE as well as on stdout
#
# stdout is ONLY the agent's final message — pipe it straight into
# `plan_tool.py done <plan> <thread-id>`. Progress output goes to stderr.
set -euo pipefail

SANDBOX="read-only"
CWD=""
MODEL=""
NETWORK=0
OUT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --write)   SANDBOX="workspace-write"; shift ;;
    --cwd)     CWD="${2:?--cwd needs a directory}"; shift 2 ;;
    --model)   MODEL="${2:?--model needs a name}"; shift 2 ;;
    --network) NETWORK=1; shift ;;
    --out)     OUT="${2:?--out needs a file}"; shift 2 ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    --)        shift; break ;;
    -)         break ;;
    -*)        echo "run_codex.sh: unknown option $1" >&2; exit 2 ;;
    *)         break ;;
  esac
done

PROMPT="${1-}"
[ -n "$PROMPT" ] || { echo "run_codex.sh: no prompt given" >&2; exit 2; }
[ "$PROMPT" = "-" ] && PROMPT="$(cat)"

if [ -n "$CWD" ] && [ ! -d "$CWD" ]; then
  echo "run_codex.sh: --cwd '$CWD' does not exist" >&2; exit 2
fi
if [ "$SANDBOX" = "workspace-write" ] && [ -z "$CWD" ]; then
  echo "run_codex.sh: --write requires --cwd (the thread's worktree)" >&2; exit 2
fi

LAST="$(mktemp)"
trap 'rm -f "$LAST"' EXIT

ARGS=(exec --sandbox "$SANDBOX" --output-last-message "$LAST" --color never)
[ -n "$CWD" ] && ARGS+=(--cd "$CWD")
[ -n "$MODEL" ] && ARGS+=(--model "$MODEL")
[ "$SANDBOX" = "workspace-write" ] && [ "$NETWORK" = 1 ] &&
  ARGS+=(--config sandbox_workspace_write.network_access=true)

# Approvals are non-interactive in `codex exec`: the sandbox is the only boundary,
# so a command codex cannot run is reported, never escalated to a prompt nobody sees.
codex "${ARGS[@]}" "$PROMPT" >&2

[ -s "$LAST" ] || { echo "run_codex.sh: codex returned no final message" >&2; exit 1; }
[ -n "$OUT" ] && cp "$LAST" "$OUT"
cat "$LAST"
