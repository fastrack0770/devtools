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
#   --log FILE       transcript destination (default: <git-dir>/parallel-dev/logs/…,
#                    or $TMPDIR/run-codex-logs-<uid>/… outside a repo). Give each concurrent
#                    thread its own path — the log dir's `last.log` link only ever
#                    points at the most recently *started* run, not at yours.
#
# stdout is ONLY the agent's final message — pipe it straight into
# `plan_tool.py done <plan> <thread-id>`. Progress and errors go to stderr AND are
# always written to the log file, so `2>/dev/null` (or a backgrounded call whose
# stderr goes nowhere) cannot destroy the diagnostics: the log survives regardless.
# Every failure exits non-zero and repeats the reason and the log path on stdout too,
# since on that path stdout carries no final message to protect.
set -euo pipefail
umask 077

SANDBOX="read-only"
CWD=""
MODEL=""
NETWORK=0
OUT=""
LOG=""
LAST=""
REPORTED=0

# Reported once, on whichever stream the caller kept: stderr always, and stdout too —
# on a failure path stdout holds no final message, so it is free to carry the pointer.
say_failure() {
  echo "run_codex.sh: $1" >&2
  echo "run_codex.sh: $1"
  REPORTED=1
}
die() { say_failure "$1"; exit "${2:-2}"; }                      # before the log exists
fail() {                                                          # after it exists
  echo "=== FAILED: $1" >> "$LOG" 2>/dev/null || true
  say_failure "$1 — see $LOG"
  exit "${2:-1}"
}
# Backstop: any command that fails without going through die/fail — mkdir, mktemp, a
# full disk on the final `cat` — still leaves the caller a pointer instead of a silent
# non-zero exit.
on_exit() {
  rc=$?
  [ -n "$LAST" ] && rm -f "$LAST"
  if [ "$rc" != 0 ] && [ "$REPORTED" = 0 ]; then
    if [ -n "$LOG" ]; then
      echo "=== FAILED: exit $rc" >> "$LOG" 2>/dev/null || true
      say_failure "failed with exit $rc — see $LOG"
    else
      say_failure "failed with exit $rc before the transcript was opened"
    fi
  fi
}
trap on_exit EXIT

while [ $# -gt 0 ]; do
  case "$1" in
    --write)   SANDBOX="workspace-write"; shift ;;
    --cwd)     CWD="${2:?--cwd needs a directory}"; shift 2 ;;
    --model)   MODEL="${2:?--model needs a name}"; shift 2 ;;
    --network) NETWORK=1; shift ;;
    --out)     OUT="${2:?--out needs a file}"; shift 2 ;;
    --log)     LOG="${2:?--log needs a file}"; shift 2 ;;
    -h|--help) sed -n '2,35p' "$0"; exit 0 ;;
    --)        shift; break ;;
    -)         break ;;
    -*)        die "unknown option $1" ;;
    *)         break ;;
  esac
done

PROMPT="${1-}"
[ -n "$PROMPT" ] || die "no prompt given"
[ "$PROMPT" = "-" ] && PROMPT="$(cat)"

[ -z "$CWD" ] || [ -d "$CWD" ] || die "--cwd '$CWD' does not exist"
if [ "$SANDBOX" = "workspace-write" ] && [ -z "$CWD" ]; then
  die "--write requires --cwd (the thread's worktree)"
fi

# --- transcript: written unconditionally, whatever the caller does with stderr ---
if [ -z "$LOG" ]; then
  GITDIR="$(git -C "${CWD:-$PWD}" rev-parse --git-common-dir 2>/dev/null || true)"
  if [ -n "$GITDIR" ]; then
    # relative (".git") resolves against --cwd; absolute (linked worktree) stands.
    LOGDIR="$(cd "${CWD:-$PWD}" && cd "$GITDIR" && pwd)/parallel-dev/logs"
  else
    LOGDIR="${TMPDIR:-/tmp}/run-codex-logs-$(id -u)"
  fi
  LOGNAME="codex-$(date +%Y%m%d-%H%M%S)-$$.log"
else
  LOGDIR="$(dirname "$LOG")"
  LOGNAME="$(basename "$LOG")"
fi
mkdir -p "$LOGDIR" || die "cannot create log directory $LOGDIR"
LOGDIR="$(cd "$LOGDIR" && pwd)"
OWNER="$(stat -c %u "$LOGDIR" 2>/dev/null || true)"
[ "$OWNER" = "$(id -u)" ] || die "log directory is not owned by the current user: $LOGDIR"
LOG="$LOGDIR/$LOGNAME"
[ ! -L "$LOG" ] || die "refusing symlink transcript path $LOG"
if [ -e "$LOG" ]; then
  [ -f "$LOG" ] || die "transcript path is not a regular file: $LOG"
  OWNER="$(stat -c %u "$LOG" 2>/dev/null || true)"
  [ "$OWNER" = "$(id -u)" ] || die "transcript is not owned by the current user: $LOG"
  chmod 600 "$LOG" || die "cannot make transcript private: $LOG"
fi
# Link target is a bare basename, so it resolves inside LOGDIR whatever --log looked
# like. It marks the most recently started run — with concurrent threads that is not
# necessarily yours, so pass a per-thread --log when it matters.
ln -sfn "$LOGNAME" "$LOGDIR/last.log" 2>/dev/null || true

{
  echo "=== run_codex.sh $(date -Is) pid=$$"
  echo "=== sandbox=$SANDBOX cwd=${CWD:-$PWD} model=${MODEL:-<default>} network=$NETWORK"
  echo "=== prompt:"
  printf '%s\n' "$PROMPT"
  echo "=== codex output:"
} >> "$LOG" || die "cannot write the transcript $LOG"
echo "run_codex.sh: transcript → $LOG" >&2

LAST="$(mktemp)" || fail "cannot create a temp file for the final message"

ARGS=(exec --sandbox "$SANDBOX" --output-last-message "$LAST" --color never)
[ -n "$CWD" ] && ARGS+=(--cd "$CWD")
[ -n "$MODEL" ] && ARGS+=(--model "$MODEL")
[ "$SANDBOX" = "workspace-write" ] && [ "$NETWORK" = 1 ] &&
  ARGS+=(--config sandbox_workspace_write.network_access=true)

# Approvals are non-interactive in `codex exec`: the sandbox is the only boundary,
# so a command codex cannot run is reported, never escalated to a prompt nobody sees.
set +e
codex "${ARGS[@]}" "$PROMPT" 2>&1 | tee -a "$LOG" >&2
PIPE=("${PIPESTATUS[@]}")
set -e
CODEX_STATUS="${PIPE[0]:-1}"
TEE_STATUS="${PIPE[1]:-0}"

[ "$CODEX_STATUS" = 0 ] || fail "codex exited $CODEX_STATUS" "$CODEX_STATUS"
[ "$TEE_STATUS" = 0 ] || fail "transcript write failed (tee exited $TEE_STATUS)" "$TEE_STATUS"
[ -s "$LAST" ] || fail "codex returned no final message"
if [ -n "$OUT" ]; then
  cp "$LAST" "$OUT" || fail "cannot write --out file $OUT"
fi
{ echo "=== final message:"; cat "$LAST"; } >> "$LOG" || fail "cannot append the final message to $LOG"
cat "$LAST" || fail "cannot write the final message to stdout"
