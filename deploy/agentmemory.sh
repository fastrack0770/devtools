#!/bin/bash
# Local memory stack for the coding agents: llama.cpp + iii-engine + agentmemory,
# in Docker, wired into Claude Code and Codex.
#
# Usage: deploy/agentmemory.sh [install|start|stop|uninstall]
#
#   install    lay the files down, sync versions, build, start, wire the agents
#   start      start an existing install and wire the agents (creates nothing)
#   stop       stop the containers and unwire the agents (deletes nothing)
#   uninstall  remove everything except the memory itself
#
# The four modes share their phases as functions, so `start` is literally a
# subset of `install` rather than a second implementation that can drift.
#
# Every mode is idempotent, which is the point: the common case is not a fresh
# machine but a stack that already runs with a piece missing — most often the
# Codex hooks, which the vendor CLI refuses to top up on its own (see
# wire_codex). Running install twice must be boring.
#
# What this owns, and what it must never touch, is spelled out in
# docs/adr/0005-agentmemory-file-ownership.md. The short version: the three
# files under agentmemory/llm/ belong to this repo, ~/llm/.env is generated,
# and everything holding memory — ~/llm/data/state_store.db, stream_store,
# all of ~/.agentmemory — belongs to the user and survives an uninstall.
#
# Knobs (environment):
#   FORCE=1         replace a hand-edited file (default: show the diff and stop)
#   WAIT=0          do not wait for the stack to come up
#   WAIT_TIMEOUT=N  seconds to wait for health (default 900; a first run pulls
#                   a CUDA image and 2.5 GB of weights and can exceed it)
#   KEEP_MODEL=1    uninstall keeps ~/llm/data/llama-cache (2.5 GB of weights)
#   PURGE_IMAGES=1  uninstall also removes the pulled llama.cpp and iii images
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/agentmemory"
WIRING="$SRC/agent-wiring.py"

LLM_DIR="$HOME/llm"
AM_DIR="$HOME/.agentmemory"
COMPOSE_FILE="$LLM_DIR/docker-compose.yml"
COMPOSE_ENV="$LLM_DIR/.env"

# Files this repo owns inside ~/llm. Kept as a list because three phases walk
# it: drift detection, installation and removal.
REPO_FILES=(docker-compose.yml Dockerfile.agentmemory iii-config.docker.yaml)

# Ports the stack binds on loopback. 3113 is the viewer, opened by the worker
# itself rather than published by compose.
STACK_PORTS=(8080 3111 3112 49134)

MODE="${1:-install}"
FORCE="${FORCE:-0}"
WAIT="${WAIT:-1}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-900}"
KEEP_MODEL="${KEEP_MODEL:-0}"
PURGE_IMAGES="${PURGE_IMAGES:-0}"
export FORCE

step() { printf '\n== %s\n' "$*"; }
note() { printf '   %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die()  { printf 'Error: %s\n' "$*" >&2; exit 1; }

stamp() { date +%Y%m%d-%H%M%S; }

# --- versions -----------------------------------------------------------
# One file feeds the container build, the host npm package and the model
# alias. Sourced rather than parsed: it is a repo file with three assignments.
load_versions() {
    [ -f "$SRC/versions.env" ] || die "$SRC/versions.env is missing"
    # shellcheck disable=SC1091  # path is computed, and the file is ours
    . "$SRC/versions.env"
    : "${AGENTMEMORY_VERSION:?versions.env: AGENTMEMORY_VERSION is empty}"
    : "${III_VERSION:?versions.env: III_VERSION is empty}"
    : "${LLM_MODEL:?versions.env: LLM_MODEL is empty}"
}

# --- small wrappers -----------------------------------------------------
compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

# Containers compose considers ours and currently running.
stack_ids() { compose ps -q 2>/dev/null; }

npm_root() { npm root -g 2>/dev/null; }
plugin_root() { echo "$(npm_root)/@agentmemory/agentmemory/plugin"; }

# The CLI, however it happens to be reachable. `command -v` covers the normal
# PATH case; the fallback covers a global prefix whose bin/ is not on PATH,
# which happens under nvm when make runs from a shell that never sourced it.
am() {
    if command -v agentmemory >/dev/null 2>&1; then
        agentmemory "$@"
    else
        node "$(npm_root)/@agentmemory/agentmemory/dist/cli.mjs" "$@"
    fi
}

host_pkg_version() {
    npm ls -g --depth=0 --json 2>/dev/null | python3 -c '
import json, sys
try:
    deps = json.load(sys.stdin).get("dependencies", {})
except ValueError:
    deps = {}
print(deps.get("@agentmemory/agentmemory", {}).get("version", ""))
'
}

# A listener on 127.0.0.1:$1, without needing root or ss/lsof.
port_taken() { (exec 3<>"/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1; }

backup_of() {
    local dest="$1.bak-$(stamp)"
    cp -p "$1" "$dest"
    echo "$dest"
}

# --- preflight ----------------------------------------------------------
preflight_common() {
    step "Preflight"
    command -v docker >/dev/null 2>&1 || die "docker is not installed"
    docker compose version >/dev/null 2>&1 \
        || die "the docker compose v2 plugin is required (docker-compose v1 will not do)"
    docker info >/dev/null 2>&1 \
        || die "cannot talk to the Docker daemon — is it running, and are you in the 'docker' group?"
    command -v node >/dev/null 2>&1 || die "node is not installed"
    command -v npm  >/dev/null 2>&1 || die "npm is not installed"
    command -v python3 >/dev/null 2>&1 || die "python3 is not installed"

    # A space or colon in $HOME breaks compose's volume syntax and the hook
    # commands the agentmemory CLI writes; better to say so than to install
    # something subtly broken.
    case "$HOME" in
        *" "*|*:*) die "\$HOME ('$HOME') contains a space or a colon — the stack cannot be wired from such a path" ;;
    esac
    note "docker, compose, node, npm, python3 present"
}

preflight_gpu() {
    docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"' \
        || die "the nvidia container runtime is not registered with Docker.
       Install nvidia-container-toolkit and restart the daemon; llama.cpp
       needs the GPU and this component does not fall back to CPU silently."
    note "nvidia container runtime registered"
}

# Ports are only a conflict when somebody else holds them. Our own running
# stack holding 3111 is the normal case, not a problem.
preflight_ports() {
    [ -z "$(stack_ids)" ] || { note "the stack already holds its ports"; return 0; }
    local port taken=()
    for port in "${STACK_PORTS[@]}"; do
        if port_taken "$port"; then taken+=("$port"); fi
    done
    [ ${#taken[@]} -eq 0 ] || die "ports already in use by something else: ${taken[*]}.
       A native agentmemory worker is the usual culprit — stop it with
       'agentmemory stop' (add --force if the pidfile is stale) and re-run."
    note "ports ${STACK_PORTS[*]} are free"
}

require_installed() {
    [ -f "$COMPOSE_FILE" ] || die "$COMPOSE_FILE is missing — run: make install agentmemory"
    [ -f "$COMPOSE_ENV" ]  || die "$COMPOSE_ENV is missing — run: make install agentmemory"
    local have; have="$(host_pkg_version)"
    [ "$have" = "$AGENTMEMORY_VERSION" ] \
        || die "the host has @agentmemory/agentmemory ${have:-(none)}, the stack expects $AGENTMEMORY_VERSION — run: make install agentmemory"
}

# --- files --------------------------------------------------------------
# Classify first, mutate second. A half-written set of configs is worse than
# none, and the drift report is only useful if it lists every drifted file
# rather than the first one.
materialize() {
    step "Files in $LLM_DIR and $AM_DIR"

    local tmp_env drift=() f
    tmp_env="$(mktemp)"
    render_compose_env "$tmp_env"

    for f in "${REPO_FILES[@]}"; do
        if [ -e "$LLM_DIR/$f" ] && ! cmp -s "$SRC/llm/$f" "$LLM_DIR/$f"; then
            drift+=("$f")
        fi
    done
    if [ -e "$COMPOSE_ENV" ] && ! cmp -s "$tmp_env" "$COMPOSE_ENV"; then
        drift+=(".env")
    fi

    if [ ${#drift[@]} -gt 0 ] && [ "$FORCE" != "1" ]; then
        printf '\n'
        for f in "${drift[@]}"; do
            printf -- '--- %s differs from the version this repo ships:\n' "$LLM_DIR/$f"
            if [ "$f" = ".env" ]; then
                diff -u "$COMPOSE_ENV" "$tmp_env" || true
            else
                diff -u "$LLM_DIR/$f" "$SRC/llm/$f" || true
            fi
            printf '\n'
        done
        rm -f "$tmp_env"
        die "the files above were changed after they were installed.
       Nothing has been touched. Re-run with FORCE=1 to replace them
       (each one is backed up first), or port your edits into
       $SRC/llm/ so they survive the next update."
    fi

    mkdir -p "$LLM_DIR/data/llama-cache" "$AM_DIR"

    for f in "${REPO_FILES[@]}"; do
        if [ ! -e "$LLM_DIR/$f" ]; then
            cp "$SRC/llm/$f" "$LLM_DIR/$f"
            note "created $f"
        elif cmp -s "$SRC/llm/$f" "$LLM_DIR/$f"; then
            note "$f up to date"
        else
            note "replaced $f (backup: $(backup_of "$LLM_DIR/$f"))"
            cp "$SRC/llm/$f" "$LLM_DIR/$f"
        fi
    done

    if [ ! -e "$COMPOSE_ENV" ]; then
        mv "$tmp_env" "$COMPOSE_ENV"
        note "created .env (generated)"
    elif cmp -s "$tmp_env" "$COMPOSE_ENV"; then
        rm -f "$tmp_env"
        note ".env up to date"
    else
        note "replaced .env (backup: $(backup_of "$COMPOSE_ENV"))"
        mv "$tmp_env" "$COMPOSE_ENV"
    fi
    chmod 0644 "$COMPOSE_ENV"

    install_user_config
}

render_compose_env() {
    cat > "$1" <<EOF
# Generated by deploy/agentmemory.sh — edits here are overwritten.
# Machine facts, plus the versions from agentmemory/versions.env. Compose
# picks this file up automatically because it sits next to docker-compose.yml,
# which is what keeps that file machine-independent.
HOST_HOME=$HOME
HOST_UID=$(id -u)
HOST_GID=$(id -g)
AGENTMEMORY_VERSION=$AGENTMEMORY_VERSION
III_VERSION=$III_VERSION
LLM_MODEL=$LLM_MODEL
EOF
}

# ~/.agentmemory holds the user's own configuration next to the memory itself,
# so these two are created when absent and never rewritten — not even under
# FORCE. A stale value here is reported by verify(), with the line to change.
install_user_config() {
    if [ -e "$AM_DIR/.env" ]; then
        note ".agentmemory/.env kept as is"
    else
        sed "s|@LLM_MODEL@|$LLM_MODEL|" "$SRC/home-agentmemory/env" > "$AM_DIR/.env"
        chmod 0600 "$AM_DIR/.env"
        note "created .agentmemory/.env (0600)"
    fi
    # Without this the worker would meet the first-run onboarding prompts, and
    # the container runs with tty:false and stdin closed.
    if [ -e "$AM_DIR/preferences.json" ]; then
        note ".agentmemory/preferences.json kept as is"
    else
        cp "$SRC/home-agentmemory/preferences.json" "$AM_DIR/preferences.json"
        note "created .agentmemory/preferences.json"
    fi
}

# --- host package -------------------------------------------------------
# The hooks in ~/.claude/settings.json and ~/.codex/hooks.json point at
# scripts inside the globally installed npm package by absolute path, so the
# host copy is not a duplicate of the container's — it is where the hooks
# live. The two versions must match or the worker and the hooks disagree
# about the wire format.
sync_npm_version() {
    step "Host package @agentmemory/agentmemory@$AGENTMEMORY_VERSION"
    local have; have="$(host_pkg_version)"
    if [ "$have" = "$AGENTMEMORY_VERSION" ]; then
        note "already installed"
        return 0
    fi
    if [ -n "$have" ]; then
        note "found $have, installing $AGENTMEMORY_VERSION over it"
    else
        note "not installed, installing"
    fi
    npm install -g "@agentmemory/agentmemory@$AGENTMEMORY_VERSION"
    [ "$(host_pkg_version)" = "$AGENTMEMORY_VERSION" ] \
        || die "npm reported success but the installed version is still $(host_pkg_version)"
}

# --- containers ---------------------------------------------------------
compose_up() {
    step "Containers"
    # `up -d` rather than `compose start`: after a `down` there are no
    # containers to start, and up recreates them from the built image.
    if [ "${1:-}" = "--build" ]; then
        compose up -d --build
    else
        compose up -d
    fi
}

wait_healthy() {
    step "Health"
    if [ "$WAIT" != "1" ]; then
        note "WAIT=0 — not waiting; check with: docker compose -f $COMPOSE_FILE ps"
        return 0
    fi
    local deadline=$(( $(date +%s) + WAIT_TIMEOUT ))
    note "waiting up to ${WAIT_TIMEOUT}s (a first run downloads the image and ~2.5 GB of weights)"
    while [ "$(date +%s)" -lt "$deadline" ]; do
        if health_ok; then
            note "llama healthy, REST answering on 3111"
            return 0
        fi
        sleep 5
    done
    # Not an error: the first run legitimately outlasts any timeout worth
    # blocking a terminal on, and everything else is already in place.
    warn "the stack is still coming up after ${WAIT_TIMEOUT}s.
         Watch it with:  docker compose -f $COMPOSE_FILE logs -f llama
         State:          docker compose -f $COMPOSE_FILE ps"
    return 0
}

health_ok() {
    [ "$(docker inspect -f '{{.State.Health.Status}}' llama 2>/dev/null)" = "healthy" ] || return 1
    # The engine answers 404 on every path we could guess, so any HTTP status
    # at all is the signal — it means the REST worker is accepting requests.
    # Probing a made-up route would only test our guess about its API.
    local code
    code="$(curl -s -o /dev/null -m 3 -w '%{http_code}' http://127.0.0.1:3111/ 2>/dev/null || true)"
    [ -n "$code" ] && [ "$code" != "000" ]
}

# --- agent wiring -------------------------------------------------------
wire_agents() {
    step "Agent wiring"
    local proot; proot="$(plugin_root)"
    [ -d "$proot" ] || die "$proot not found — the host package is not installed"
    wire_claude
    wire_codex
}

# The Claude adapter installs hooks even when the MCP server is already wired,
# and it only strips entries that point into its own plugin dir, so foreign
# hooks survive. Nothing for us to do beyond calling it and adding the two
# settings keys it never writes: the context-injection env key, and
# autoMemoryEnabled=false, which keeps Claude's built-in auto-memory from
# running a second, competing memory next to this one.
wire_claude() {
    am connect claude-code --with-hooks
    local rc=0
    python3 "$WIRING" claude-settings-set || rc=$?
    [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ] || die "failed to update ~/.claude/settings.json"
}

# The Codex adapter returns early when the MCP server is already wired — before
# it ever looks at --with-hooks. So on the common "stack works, hooks missing"
# machine, plain `connect codex --with-hooks` is a no-op, and only --force
# reaches the hook installer. --force also rewrites the [mcp_servers.agentmemory]
# block in config.toml, hence the extra backup of our own: the vendor makes one
# too, but a config.toml is not a file to be casual about.
wire_codex() {
    if python3 "$WIRING" codex-hooks-ok; then
        note "codex hooks already installed and resolvable"
        return 0
    fi
    local toml="$HOME/.codex/config.toml"
    if [ -f "$toml" ]; then note "backed up config.toml to $(backup_of "$toml")"; fi
    am connect codex --with-hooks --force
    warn "Codex only runs hooks it has been shown: start 'codex' (the TUI) once and
         choose \"Trust all and continue\" at the \"Hooks need review\" prompt.
         'codex exec' never shows that prompt, so until then the hooks stay inert."
}

unwire_agents() {
    step "Agent wiring removal"
    python3 "$WIRING" claude-unwire
    python3 "$WIRING" codex-unwire
}

# --- verification -------------------------------------------------------
verify() {
    step "Verification"
    local ok=1

    local running; running="$(stack_ids | grep -c . || true)"
    if [ "$running" -eq 3 ]; then
        note "containers: 3/3 running"
    else
        note "containers: $running/3 running — docker compose -f $COMPOSE_FILE ps"
        ok=0
    fi

    if python3 "$WIRING" claude-hooks-ok; then
        note "claude hooks: installed, scripts resolve"
    else
        note "claude hooks: MISSING or pointing at scripts that no longer exist"
        ok=0
    fi
    if python3 "$WIRING" codex-hooks-ok; then
        note "codex hooks: installed, scripts resolve (approve them once in the codex TUI)"
    else
        note "codex hooks: MISSING or pointing at scripts that no longer exist"
        ok=0
    fi

    # A model name that disagrees with llama's --alias makes every LLM call
    # fail with a 404 from /v1/models. We never rewrite this file, so the most
    # we can do is point at the line.
    local configured
    configured="$(sed -n 's/^OPENAI_MODEL=//p' "$AM_DIR/.env" 2>/dev/null | tail -1)"
    if [ -n "$configured" ] && [ "$configured" != "$LLM_MODEL" ]; then
        warn "$AM_DIR/.env has OPENAI_MODEL=$configured, the stack serves $LLM_MODEL.
         The container overrides it, but the host CLI (status, doctor) does not.
         Fix by hand:  OPENAI_MODEL=$LLM_MODEL"
    fi

    # State written by another engine version may simply not load.
    if [ -e "$LLM_DIR/data/state_store.db" ]; then
        note "memory state present in $LLM_DIR/data (pinned engine: iii $III_VERSION)"
    fi

    [ "$ok" -eq 1 ] || note "some checks did not pass — see above"
}

# --- modes --------------------------------------------------------------
do_install() {
    preflight_common
    preflight_gpu
    preflight_ports
    materialize
    sync_npm_version
    compose_up --build
    wait_healthy
    wire_agents
    verify
    step "Done"
    note "viewer: http://localhost:3113   REST: http://127.0.0.1:3111"
    note "restart Claude Code and Codex to pick up the wiring"
}

do_start() {
    preflight_common
    require_installed
    compose_up
    wait_healthy
    wire_agents
    verify
    step "Done"
    note "restart Claude Code and Codex to pick up the wiring"
}

do_stop() {
    step "Containers"
    if [ -f "$COMPOSE_FILE" ]; then
        # `stop`, not `down`: the containers stay, and restart:unless-stopped
        # is cleared, so an explicit stop survives a reboot.
        compose stop
        note "stopped"
    else
        note "$COMPOSE_FILE is missing — nothing to stop"
    fi
    unwire_agents
    step "Done"
    note "nothing was deleted; 'make start' brings it all back"
}

do_uninstall() {
    # Unwire first: the hook entries are identified by the npm package path,
    # and the package is about to go.
    unwire_agents

    step "Containers and images"
    if [ -f "$COMPOSE_FILE" ]; then
        compose down --rmi local || warn "docker compose down reported an error; continuing"
        if [ "$PURGE_IMAGES" = "1" ]; then
            docker image rm "ghcr.io/ggml-org/llama.cpp:server-cuda" "iiidev/iii:$III_VERSION" \
                2>/dev/null || warn "could not remove every pulled image (still in use?)"
            note "pulled images removed"
        else
            note "pulled images kept (PURGE_IMAGES=1 removes them)"
        fi
    else
        note "$COMPOSE_FILE is missing — nothing to bring down"
    fi

    step "Files"
    local f
    for f in "${REPO_FILES[@]}"; do
        if [ -e "$LLM_DIR/$f" ]; then rm -f "${LLM_DIR:?}/$f"; note "removed $f"; fi
    done
    if [ -e "$COMPOSE_ENV" ]; then rm -f "$COMPOSE_ENV"; note "removed .env"; fi

    if [ "$KEEP_MODEL" = "1" ]; then
        note "kept data/llama-cache (KEEP_MODEL=1)"
    elif [ -d "$LLM_DIR/data/llama-cache" ]; then
        rm -rf "${LLM_DIR:?}/data/llama-cache"
        note "removed data/llama-cache (re-downloaded on the next install; KEEP_MODEL=1 to keep it)"
    fi

    # Runtime leftovers only. A stale pidfile makes the CLI think an engine is
    # running and confuses the next install's preflight.
    for f in iii.pid worker.pid worker.out engine-state.json standalone.json; do
        if [ -e "$AM_DIR/$f" ]; then rm -f "${AM_DIR:?}/$f"; note "removed .agentmemory/$f"; fi
    done

    step "Host package"
    if [ -n "$(host_pkg_version)" ]; then
        npm uninstall -g @agentmemory/agentmemory
        note "removed @agentmemory/agentmemory"
    else
        note "not installed"
    fi

    if rmdir "$LLM_DIR" 2>/dev/null; then note "removed empty $LLM_DIR"; fi

    step "Kept"
    note "$LLM_DIR/data/state_store.db, $LLM_DIR/data/stream_store — the memory itself"
    note "$AM_DIR/.env, preferences.json, snapshots/, backups/ — config and snapshots"
    note "$LLM_DIR/*.bak-* — copies of files you had edited, and anything else there"
    note "'make install agentmemory' installs straight back on top of it"
}

load_versions
case "$MODE" in
    install)   do_install ;;
    start)     do_start ;;
    stop)      do_stop ;;
    uninstall) do_uninstall ;;
    *) die "unknown mode '$MODE' — expected install, start, stop or uninstall" ;;
esac
