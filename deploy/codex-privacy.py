#!/usr/bin/env python3
"""Disable optional Codex analytics and feedback upload in the supplied config.toml.

Used by both ai-config installation modes; also safe to run on its own. The file is the
user's, so it is edited line by line in place, never re-serialised: comments, ordering
and other settings survive. The edit is checked by parsing the result; a config.toml that
is invalid before or after the edit is left untouched.
"""

import os
from pathlib import Path
import stat
import sys
import tempfile
import tomllib

# [table] -> key that must read false
SETTINGS = {"analytics": "enabled", "feedback": "enabled"}


def find_key(lines, table, key):
    """Index of `key = …` inside [table], or of a top-level `table.key = …`."""
    section = ""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped.split("#", 1)[0].strip()
            continue
        name, sep, _ = stripped.partition("=")
        name = name.strip()
        if sep and ((section == f"[{table}]" and name == key)
                    or (section == "" and name == f"{table}.{key}")):
            return i
    return None


def set_false(lines, table, key):
    index = find_key(lines, table, key)
    if index is not None:
        name = lines[index].split("=", 1)[0]
        lines[index] = f"{name.rstrip()} = false"
        return lines
    header = next((i for i, line in enumerate(lines)
                   if line.split("#", 1)[0].strip() == f"[{table}]"), None)
    if header is not None:
        lines.insert(header + 1, f"{key} = false")
        return lines
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return lines + ([""] if lines else []) + [f"[{table}]", f"{key} = false"]


def disable_analytics(path):
    path = path.resolve()
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    current = tomllib.loads(before)
    if all(current.get(table, {}).get(key) is False for table, key in SETTINGS.items()):
        print(f"Codex analytics and feedback are already disabled in {path}")
        return
    lines = before.split("\n")
    for table, key in SETTINGS.items():
        lines = set_false(lines, table, key)
    after = "\n".join(lines).rstrip("\n") + "\n"
    result = tomllib.loads(after)
    if not all(result.get(table, {}).get(key) is False for table, key in SETTINGS.items()):
        raise ValueError("could not place the settings; set "
                         + ", ".join(f"[{t}] {k} = false" for t, k in SETTINGS.items())
                         + " by hand")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            # Codex creates config.toml as 0600; keep whatever mode the file has.
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
            os.fchmod(output.fileno(), mode)
            output.write(after)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print(f"Disabled Codex analytics and feedback upload in {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: codex-privacy.py <config.toml>")
    try:
        disable_analytics(Path(sys.argv[1]))
    except (OSError, ValueError) as error:  # tomllib.TOMLDecodeError is a ValueError
        sys.exit(f"Error: could not configure Codex privacy: {error}")
