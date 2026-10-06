#!/usr/bin/env python3
"""Disable optional Claude Code telemetry in the supplied settings.json.

Used by both ai-config installation modes; also safe to run on user settings alone.
Other settings are preserved. Invalid JSON or an invalid env object is left untouched.
"""

import json
import os
from pathlib import Path
import stat
import sys
import tempfile


def disable_telemetry(path):
    path = path.resolve()
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    settings = json.loads(before) if before.strip() else {}
    if not isinstance(settings, dict) or not isinstance(settings.get("env", {}), dict):
        raise ValueError("settings and env must be JSON objects")
    settings.setdefault("env", {}).update({
        "DISABLE_TELEMETRY": "1",
        "DISABLE_ERROR_REPORTING": "1",
        "DISABLE_FEEDBACK_COMMAND": "1",
    })
    after = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
    if after == before:
        print(f"Claude Code telemetry is already disabled in {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            if path.exists():
                os.fchmod(output.fileno(), stat.S_IMODE(path.stat().st_mode))
            output.write(after)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print(f"Disabled Claude Code telemetry, error reporting and feedback in {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: claude-privacy.py <settings.json>")
    try:
        disable_telemetry(Path(sys.argv[1]))
    except (OSError, ValueError) as error:
        sys.exit(f"Error: could not configure Claude Code privacy: {error}")
