#!/usr/bin/env python3
"""
prefer_read.py — PreToolUse hook (matcher: Bash).

Blocks Bash commands that merely read a file — cat/head/tail, less/more,
sed -n 'N,Mp' — and tells Claude to use the Read tool instead. Only pure
reads are blocked: as soon as the command pipes, redirects, chains, uses a
heredoc or actually edits, it is data processing that Read cannot replace,
so the hook stays silent. When unsure, it errs toward allowing.

Complements the CLAUDE.md rule "Read files with the Read tool" — the rule
sets the norm, this hook enforces it.

Input: JSON on stdin (tool_name, tool_input.command). Output: JSON with
hookSpecificOutput.permissionDecision = "deny" + reason, or nothing (allow).
"""

import json
import re
import shlex
import sys

# 'N,Mp' / 'Np' / 'N,$p' — sed's print-a-line-range form and nothing else.
SED_PRINT_RANGE = re.compile(r"^\d+(,(\d+|\$))?p$")

# head/tail options that take a value in the next token.
VALUE_OPTS = {"-n", "-c"}


def is_pure_read(tokens):
    cmd = tokens[0]
    args = tokens[1:]

    if cmd in ("less", "more"):
        return True  # interactive pagers hang a non-tty session anyway

    if cmd == "cat":
        files = [a for a in args if not a.startswith("-")]
        return bool(files)

    if cmd in ("head", "tail"):
        if cmd == "tail" and any(a in ("-f", "-F") or a.startswith("--follow") for a in args):
            return False  # follow mode watches a file; Read cannot do that
        files, skip = [], False
        for a in args:
            if skip:
                skip = False
                continue
            if a in VALUE_OPTS:
                skip = True
            elif not a.startswith("-"):
                files.append(a)
        return bool(files)

    if cmd == "sed":
        opts = [a for a in args if a.startswith("-")]
        rest = [a for a in args if not a.startswith("-")]
        # Only the pure print form: sed -n 'N,Mp' file…  Everything else
        # (s///, -i, address regexes) is editing/processing — leave it alone.
        return (
            opts == ["-n"]
            and len(rest) >= 2
            and SED_PRINT_RANGE.match(rest[0]) is not None
        )

    return False


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if data.get("tool_name") != "Bash":
        return
    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        return

    # Pipes, redirects, heredocs, chains, substitutions: data processing,
    # not plain reading — Read cannot replace those, let them through.
    if any(ch in command for ch in ("|", ">", "<", ";", "&", "`", "$(", "\n")):
        return

    try:
        tokens = shlex.split(command)
    except ValueError:
        return
    if not tokens:
        return

    if is_pure_read(tokens):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Use the Read tool instead of `{tokens[0]}` to read files "
                    "(offset/limit cover line ranges)."
                ),
            }
        }))


if __name__ == "__main__":
    main()
