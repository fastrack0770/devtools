#!/usr/bin/env python3
"""Edit the agent-side wiring that the agentmemory CLI cannot edit itself.

Usage: agent-wiring.py <command>

  claude-settings-set    write env.AGENTMEMORY_INJECT_CONTEXT="true" and
                         autoMemoryEnabled=false to ~/.claude/settings.json
  claude-settings-unset  remove those keys again (and the env object if it empties)
  claude-hooks-ok        exit 0 if ~/.claude/settings.json carries live agentmemory hooks
  codex-hooks-ok         exit 0 if ~/.codex/hooks.json carries live agentmemory hooks
  codex-inject-set       prefix the agentmemory hook commands in ~/.codex/hooks.json
                         with AGENTMEMORY_INJECT_CONTEXT=true
  codex-inject-ok        exit 0 if every agentmemory hook command there carries it
  codex-memory-set       write memories=false under [features] in ~/.codex/config.toml
  codex-memory-ok        exit 0 if Codex's own memory is switched off there
  claude-unwire          strip agentmemory hooks, those keys and the MCP server
  codex-unwire           strip agentmemory hooks, the [mcp_servers.agentmemory] block
                         and the memories=false we wrote

`agentmemory connect` owns installation; this owns the gaps it leaves — the
settings keys it never writes, the switch that turns Codex's own memory off, the context-injection switch the Codex hooks
never receive, and removal, for which the CLI offers only the destructive
`agentmemory remove`.

Every command is idempotent and reports what it did on stdout. Exit codes:
0 = done or already in that state, 3 = deliberately skipped (the caller
prints the reason and carries on), 1 = the file is unreadable and a human
should look at it. Files are backed up next to themselves before a change
and rewritten atomically, so a crash mid-write cannot leave an agent with
half a config.

Entries are recognised by the '@agentmemory/agentmemory' substring in the
hook command rather than by a resolved plugin path: unwiring has to work
after the npm package is already gone, and the path form differs between a
plugin install (${CLAUDE_PLUGIN_ROOT}) and the standalone one (absolute).
Anything else in these files is somebody else's and is left untouched.
"""

import json
import os
import shutil
import sys
import time

HOME = os.path.expanduser("~")
CLAUDE_SETTINGS = os.path.join(HOME, ".claude", "settings.json")
CLAUDE_JSON = os.path.join(HOME, ".claude.json")
CODEX_HOOKS = os.path.join(HOME, ".codex", "hooks.json")
CODEX_TOML = os.path.join(HOME, ".codex", "config.toml")

ENV_KEY = "AGENTMEMORY_INJECT_CONTEXT"
ENV_VALUE = "true"
# Claude Code's own auto-memory writes and injects a second memory beside this
# one: two sets of notes competing for the same context window, neither aware
# of the other. agentmemory is only worth installing as the single one.
AUTO_KEY = "autoMemoryEnabled"
MARKER = "@agentmemory/agentmemory"
TOML_SECTIONS = ("[mcp_servers.agentmemory]", "[mcp_servers.agentmemory.env]")
# Codex's counterpart of autoMemoryEnabled: the `memories` feature keeps its
# own notes on disk (~/.codex/memories_*.sqlite). Off by default today, but a
# default is not a decision — written out, it survives a vendor flip.
FEATURES = "[features]"
MEMORY_KEY = "memories"

FORCE = os.environ.get("FORCE") == "1"


def load_json(path):
    """Parsed contents, or None when the file does not exist."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as err:
        print(f"cannot read {path}: {err}", file=sys.stderr)
        sys.exit(1)


def backup(path):
    dest = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, dest)
    return dest


def write_json(path, data):
    """Replace path with data, keeping a timestamped copy of what was there."""
    note = ""
    if os.path.exists(path):
        note = f" (backup: {backup(path)})"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
    return note


def is_ours(entry):
    return isinstance(entry, dict) and MARKER in str(entry.get("command", ""))


def strip_hooks(hooks):
    """Drop agentmemory entries from a Claude-shaped hooks object.

    Returns (cleaned, removed). Groups and events left empty are dropped too,
    so an uninstall does not leave a scaffold of empty arrays behind.
    """
    removed = 0
    cleaned = {}
    for event, groups in (hooks or {}).items():
        kept_groups = []
        for group in groups if isinstance(groups, list) else []:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
            entries = group.get("hooks", [])
            kept = [e for e in entries if not is_ours(e)]
            removed += len(entries) - len(kept)
            if kept:
                kept_groups.append({**group, "hooks": kept})
        if kept_groups:
            cleaned[event] = kept_groups
    return cleaned, removed


def live_hook_count(path):
    """agentmemory hook entries in `path` whose script actually exists.

    A path that no longer resolves means a stale wiring — after an npm
    upgrade, or a switch to another node version, since the standalone
    install bakes an absolute nvm path into every command. Counting those
    as installed would make the installer skip the repair.
    """
    data = load_json(path)
    if not isinstance(data, dict):
        return 0
    live = 0
    for groups in (data.get("hooks") or {}).values():
        for group in groups if isinstance(groups, list) else []:
            for entry in (group or {}).get("hooks", []) if isinstance(group, dict) else []:
                if not is_ours(entry):
                    continue
                # command looks like: node "/abs/path/to/scripts/foo.mjs"
                script = entry["command"].split('"')[1] if '"' in entry["command"] else ""
                if script and os.path.exists(script):
                    live += 1
    return live


def our_codex_entries(data):
    """agentmemory hook entries of a parsed ~/.codex/hooks.json, as live dicts."""
    found = []
    for groups in (data.get("hooks") or {}).values():
        for group in groups if isinstance(groups, list) else []:
            for entry in group.get("hooks", []) if isinstance(group, dict) else []:
                if is_ours(entry):
                    found.append(entry)
    return found


def codex_inject_set():
    """Turn context injection on for the Codex hooks.

    The hook scripts read AGENTMEMORY_INJECT_CONTEXT from their own process
    environment and nowhere else — not from ~/.agentmemory/.env. Claude Code
    hands it over through settings.json `env`; Codex has no such key, and a
    hook entry there has no `env` field either, so without this SessionStart
    registers the session and injects nothing. Codex runs hook commands through
    a shell, which leaves the command line itself as the one place to put it.
    `env VAR=… node …` rather than a bare `VAR=… node …`: it does not depend on
    which shell $SHELL happens to be.

    Every agentmemory entry gets it, not only the two scripts that read it
    today — the same blanket the settings.json key gives Claude. A changed
    command is a changed hook to Codex, which asks for trust again; the caller
    says so.
    """
    data = load_json(CODEX_HOOKS)
    entries = our_codex_entries(data) if isinstance(data, dict) else []
    if not entries:
        print(f"no agentmemory hooks in {CODEX_HOOKS}")
        return 3
    todo = [e for e in entries if f"{ENV_KEY}=" not in e["command"]]
    if not todo:
        print(f"{ENV_KEY} already set on the codex hooks")
        return 0
    for entry in todo:
        entry["command"] = f"env {ENV_KEY}={ENV_VALUE} {entry['command']}"
    print(f"{ENV_KEY}={ENV_VALUE} set on {len(todo)} codex hook command(s)"
          f"{write_json(CODEX_HOOKS, data)}")
    return 0


def codex_inject_ok():
    data = load_json(CODEX_HOOKS)
    entries = our_codex_entries(data) if isinstance(data, dict) else []
    ok = entries and all(f"{ENV_KEY}={ENV_VALUE}" in e["command"] for e in entries)
    return 0 if ok else 1


def claude_settings_set():
    """Write the two keys `agentmemory connect` leaves alone.

    A key someone else already set to another value is reported and left as
    is: a settings file is a user's, and a wiring step is not the place to
    overrule a deliberate choice. FORCE=1 overrules it anyway.
    """
    data = load_json(CLAUDE_SETTINGS) or {}
    env = data.get("env")
    if env is not None and not isinstance(env, dict):
        print(f'"env" in {CLAUDE_SETTINGS} is not an object — left alone')
        return 3
    env = dict(env or {})
    changed, skipped = [], False

    current = env.get(ENV_KEY)
    if current == ENV_VALUE:
        print(f"env.{ENV_KEY} already set")
    elif current is not None and not FORCE:
        print(f'env.{ENV_KEY} is "{current}" — left as is (FORCE=1 to set "{ENV_VALUE}")')
        skipped = True
    else:
        env[ENV_KEY] = ENV_VALUE
        changed.append(f"env.{ENV_KEY}")

    current = data.get(AUTO_KEY)
    if current is False:
        print(f"{AUTO_KEY} already false")
    elif current is not None and not FORCE:
        print(f"{AUTO_KEY} is {json.dumps(current)} — left as is (FORCE=1 to set false)")
        skipped = True
    else:
        data[AUTO_KEY] = False
        changed.append(AUTO_KEY)

    if changed:
        data["env"] = env
        print(f"{' and '.join(changed)} set{write_json(CLAUDE_SETTINGS, data)}")
    return 3 if skipped else 0


def read_toml_lines():
    if not os.path.exists(CODEX_TOML):
        return []
    try:
        with open(CODEX_TOML, encoding="utf-8") as fh:
            return fh.read().split("\n")
    except OSError as err:
        print(f"cannot read {CODEX_TOML}: {err}", file=sys.stderr)
        sys.exit(1)


def write_toml_lines(lines):
    note = f" (backup: {backup(CODEX_TOML)})" if os.path.exists(CODEX_TOML) else ""
    os.makedirs(os.path.dirname(CODEX_TOML), exist_ok=True)
    tmp = f"{CODEX_TOML}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip("\n") + "\n")
    os.replace(tmp, CODEX_TOML)
    return note


def memory_line(lines):
    """(index, value) of `memories = …` inside [features], or of a top-level
    `features.memories = …`; (None, None) when neither is there. Line-based,
    like the rest of this file's TOML handling: config.toml is the user's and
    is edited in place, never re-serialised."""
    section = ""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped
            continue
        key, sep, value = stripped.partition("=")
        key = key.strip()
        if sep and ((section == FEATURES and key == MEMORY_KEY)
                    or (section == "" and key == f"features.{MEMORY_KEY}")):
            return i, value.split("#", 1)[0].strip()
    return None, None


def codex_memory_set():
    """Switch Codex's own memory off, as claude-settings-set does for Claude.

    A value someone else already set is reported and left as is; FORCE=1
    overrules it."""
    lines = read_toml_lines()
    index, value = memory_line(lines)
    if value == "false":
        print(f"{MEMORY_KEY} already false in {CODEX_TOML}")
        return 0
    if index is not None:
        if not FORCE:
            print(f"{MEMORY_KEY} is {value} in {CODEX_TOML} — left as is (FORCE=1 to set false)")
            return 3
        key = lines[index].split("=", 1)[0]
        lines[index] = f"{key.rstrip()} = false"
    else:
        header = next((i for i, line in enumerate(lines) if line.strip() == FEATURES), None)
        if header is None:
            while lines and not lines[-1].strip():
                lines = lines[:-1]
            lines = lines + ([""] if lines else []) + [FEATURES, f"{MEMORY_KEY} = false"]
        else:
            lines.insert(header + 1, f"{MEMORY_KEY} = false")
    print(f"{MEMORY_KEY} = false set in {CODEX_TOML}{write_toml_lines(lines)}")
    return 0


def codex_memory_ok():
    return 0 if memory_line(read_toml_lines())[1] == "false" else 1


def drop_memory_line(lines):
    """Remove the memories=false we wrote, and a [features] table it leaves
    empty. A `true` there is somebody's own choice and stays."""
    index, value = memory_line(lines)
    if value != "false":
        return lines, False
    lines = lines[:index] + lines[index + 1:]
    header = next((i for i, line in enumerate(lines) if line.strip() == FEATURES), None)
    if header is not None:
        rest = lines[header + 1:]
        end = next((i for i, line in enumerate(rest) if line.strip().startswith("[")), len(rest))
        if not any(line.strip() for line in rest[:end]):
            lines = lines[:header] + rest[end:]
    return lines, True


def claude_settings_unset():
    data = load_json(CLAUDE_SETTINGS)
    if not isinstance(data, dict):
        print("nothing of ours in the settings")
        return 0
    removed = drop_settings(data)
    if removed:
        print(f"removed {' and '.join(removed)}{write_json(CLAUDE_SETTINGS, data)}")
    else:
        print("nothing of ours in the settings")
    return 0


def drop_settings(data):
    """Remove our two keys from a parsed settings object, in place.

    Returns the names removed. autoMemoryEnabled goes only when it still
    carries the value we wrote — a `true` there is somebody's own choice.
    """
    removed = []
    env = data.get("env")
    if isinstance(env, dict) and ENV_KEY in env:
        del env[ENV_KEY]
        if not env:
            del data["env"]
        removed.append(f"env.{ENV_KEY}")
    if data.get(AUTO_KEY) is False:
        del data[AUTO_KEY]
        removed.append(AUTO_KEY)
    return removed


def claude_unwire():
    settings = load_json(CLAUDE_SETTINGS)
    if isinstance(settings, dict):
        cleaned, removed = strip_hooks(settings.get("hooks"))
        keys = drop_settings(settings)
        if removed or keys:
            if removed:
                if cleaned:
                    settings["hooks"] = cleaned
                else:
                    settings.pop("hooks", None)
            note = write_json(CLAUDE_SETTINGS, settings)
            what = []
            if removed:
                what.append(f"{removed} hook entr{'y' if removed == 1 else 'ies'}")
            what += keys
            print(f"removed {' and '.join(what)} from {CLAUDE_SETTINGS}{note}")
        else:
            print(f"nothing of ours in {CLAUDE_SETTINGS}")

    config = load_json(CLAUDE_JSON)
    if isinstance(config, dict) and isinstance(config.get("mcpServers"), dict):
        servers = config["mcpServers"]
        entry = servers.get("agentmemory")
        if isinstance(entry, dict) and "@agentmemory/mcp" in str(entry.get("args", "")):
            del servers["agentmemory"]
            print(f"removed mcpServers.agentmemory{write_json(CLAUDE_JSON, config)}")
        else:
            print("no agentmemory MCP server in ~/.claude.json")
    return 0


def codex_unwire():
    data = load_json(CODEX_HOOKS)
    if isinstance(data, dict):
        cleaned, removed = strip_hooks(data.get("hooks"))
        if removed:
            if cleaned:
                data["hooks"] = cleaned
                print(f"removed {removed} hook entr(ies){write_json(CODEX_HOOKS, data)}")
            elif set(data) <= {"hooks"}:
                # The file exists only because agentmemory created it.
                print(f"removed {CODEX_HOOKS} (backup: {backup(CODEX_HOOKS)})")
                os.remove(CODEX_HOOKS)
            else:
                data.pop("hooks", None)
                print(f"removed {removed} hook entr(ies){write_json(CODEX_HOOKS, data)}")
        else:
            print(f"no agentmemory hooks in {CODEX_HOOKS}")
    else:
        print(f"no {CODEX_HOOKS}")

    if not os.path.exists(CODEX_TOML):
        print(f"no {CODEX_TOML}")
        return 0
    lines, memory_dropped = drop_memory_line(read_toml_lines())
    kept, skipping, removed = [], False, 0
    for line in lines:
        stripped = line.strip()
        if stripped in TOML_SECTIONS:
            skipping = True
            removed += 1
            continue
        if skipping and stripped.startswith("["):
            skipping = False
        if skipping:
            continue
        kept.append(line)
    if not removed and not memory_dropped:
        print("no [mcp_servers.agentmemory] block or memories=false in config.toml")
        return 0
    what = (["[mcp_servers.agentmemory]"] if removed else []) + ([f"{MEMORY_KEY} = false"] if memory_dropped else [])
    print(f"removed {' and '.join(what)} from config.toml{write_toml_lines(kept)}")
    return 0


COMMANDS = {
    "claude-settings-set": claude_settings_set,
    "claude-settings-unset": claude_settings_unset,
    "codex-hooks-ok": lambda: 0 if live_hook_count(CODEX_HOOKS) else 1,
    "codex-inject-set": codex_inject_set,
    "codex-inject-ok": codex_inject_ok,
    "codex-memory-set": codex_memory_set,
    "codex-memory-ok": codex_memory_ok,
    "claude-hooks-ok": lambda: 0 if live_hook_count(CLAUDE_SETTINGS) else 1,
    "claude-unwire": claude_unwire,
    "codex-unwire": codex_unwire,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]]())
