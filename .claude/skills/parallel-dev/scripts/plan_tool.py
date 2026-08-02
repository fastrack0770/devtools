#!/usr/bin/env python3
"""Mechanical bookkeeping of a parallel-dev run, so the orchestrator model spends its
context on decisions rather than on JSON surgery.

Commands (all mutating commands auto-backup the plan, see DURABILITY below):

  build <plan>
      Fill threads[].prompt from the plan's `prompt_template` + per-thread fields.
      The plan stores the boilerplate ONCE (template.intro / template.tail) and each
      thread stores only what is unique to it: `task`, `files`, `contract_ids`,
      `verify`. Threads that already carry a literal `prompt` are left untouched.

  launch <plan> <thread-id> <agent-id> [--worktree <path>] [--branch <name>]
      status=running, record agent_id and (when given) the thread's worktree
      path and branch.

  done <plan> <thread-id> [--report <file>] [--summary <text>]
      status=done. With --report (or a report piped to stdin) the agent's final
      message is parsed for the template's three sections: FILES CHANGED -> the
      thread's actual_files, SUMMARY -> summary, DEVIATIONS -> deviations
      (omitted when literally "none"). --summary overrides the parsed summary.

  fail <plan> <thread-id> [--note <text>]
      status=failed with an optional note — for an agent that was cancelled or
      returned unusable work; `build`/`launch` may then be reused to relaunch it.

  status <plan>
      One line per thread: id, executor, status, agent id, files counts.
      Exit code 1 while any thread is pending/running (usable as a wave gate).

  restore <plan>
      Copy the durable backup back to <plan> (after a scratchpad wipe).

DURABILITY: every mutating command writes a copy to <repo>/.git/parallel-dev/
(same basename). The .git directory survives scratchpad wipes and process
restarts and is never committed, which makes it the recovery point the
scratchpad turned out not to be. --repo defaults to the current directory's
git toplevel.

Prompt assembly (build): a thread prompt becomes

    {intro}\n{task}\n\n## File boundary (hard rule)\n...files...\n
    {## Contracts block from contract_ids, if any}\n{verify}\n{tail}

with the boundary and contracts wording fixed here so every run carries the
same non-negotiables without the orchestrator retyping them.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

BOUNDARY_HEADER = (
    "## File boundary (hard rule)\n\nYou may create or modify ONLY these files "
    "(paths relative to your worktree root):\n\n"
)
BOUNDARY_FOOTER = (
    "\n\nDo not touch any other file — especially gradle files, version catalogs, DI modules, "
    "navigation, and shared resources: editing outside this list breaks the merge of your branch. "
    "If the task seems to require editing a file outside this "
    "list, do not edit it: finish what you can and report the need under DEVIATIONS.\n"
)
CONTRACTS_HEADER = (
    "## Contracts\n\nThese signatures are fixed agreements with other threads. Implement against "
    "them exactly — package, names, parameter and return types. If a contract turns out to be "
    "unimplementable as written, do not change it unilaterally: implement your side as closely as "
    "possible and flag the deviation prominently under DEVIATIONS.\n\n"
)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def repo_root(args):
    if args.repo:
        return args.repo
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    return out.stdout.strip() or os.getcwd()


def backup_path(plan_path, args):
    return os.path.join(repo_root(args), ".git", "parallel-dev", os.path.basename(plan_path))


def save(plan, plan_path, args):
    body = json.dumps(plan, ensure_ascii=False, indent=1)
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(body)
    dst = backup_path(plan_path, args)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(body)


def thread_of(plan, thread_id):
    for t in plan.get("threads", []):
        if t.get("id") == thread_id:
            return t
    sys.exit(f"error: no thread with id '{thread_id}' in the plan")


def cmd_build(args):
    plan = load(args.plan)
    tpl = plan.get("prompt_template") or {}
    intro, tail = tpl.get("intro", ""), tpl.get("tail", "")
    contracts = {c.get("id"): c["definition"] for c in plan.get("contracts", []) if c.get("id")}
    built = 0
    for t in plan.get("threads", []):
        if t.get("prompt") or t.get("executor") != "agent":
            continue
        if not t.get("task"):
            sys.exit(f"error: thread '{t.get('id')}' has neither prompt nor task")
        parts = [intro, "\n" + t["task"].strip() + "\n"]
        parts.append("\n" + BOUNDARY_HEADER + "\n".join(t.get("files", [])) + BOUNDARY_FOOTER)
        ids = t.get("contract_ids", [])
        missing = [i for i in ids if i not in contracts]
        if missing:
            sys.exit(f"error: thread '{t['id']}' references unknown contracts: {missing}")
        if ids:
            parts.append("\n" + CONTRACTS_HEADER + "\n\n".join(contracts[i] for i in ids) + "\n")
        if t.get("verify"):
            parts.append("\n" + t["verify"].strip() + "\n")
        parts.append("\n" + tail)
        t["prompt"] = "".join(parts)
        built += 1
    save(plan, args.plan, args)
    print(f"build: {built} prompt(s) assembled")


def cmd_launch(args):
    plan = load(args.plan)
    t = thread_of(plan, args.thread)
    t["status"] = "running"
    t["agent_id"] = args.agent_id
    if args.worktree:
        t["worktree"] = args.worktree
    if args.branch:
        t["branch"] = args.branch
    save(plan, args.plan, args)
    print(f"launch: {args.thread} running (agent {args.agent_id})")


def _section(name):
    # Tolerate markdown decoration around the label: "## FILES CHANGED", "**SUMMARY:**", ...
    return rf"[*#]*\s*{name}\s*:?\s*[*#]*\s*"


SECTION_RE = re.compile(
    _section("FILES CHANGED") + r"(?P<files>.*?)"
    + _section("SUMMARY") + r"(?P<summary>.*?)"
    + _section("DEVIATIONS") + r"(?P<dev>.*)",
    re.S,
)


def cmd_done(args):
    plan = load(args.plan)
    t = thread_of(plan, args.thread)
    report = None
    if args.report:
        with open(args.report, encoding="utf-8") as f:
            report = f.read()
    elif not sys.stdin.isatty():
        report = sys.stdin.read()
    if report:
        m = SECTION_RE.search(report)
        if m:
            files = [
                ln.strip().lstrip("-* ").strip("`")
                for ln in m.group("files").splitlines()
                if ln.strip() and not ln.strip().startswith("```")
            ]
            t["actual_files"] = [f for f in files if f]
            t["summary"] = m.group("summary").strip()
            dev = m.group("dev").strip()
            if dev and dev.lower() not in ("none", "none."):
                t["deviations"] = dev
        else:
            print("warn: report did not match the three-section format; sections not parsed")
    if args.summary:
        t["summary"] = args.summary
    t["status"] = "done"
    save(plan, args.plan, args)
    print(f"done: {args.thread} ({len(t.get('actual_files', []))} file(s) recorded)")


def cmd_fail(args):
    plan = load(args.plan)
    t = thread_of(plan, args.thread)
    t["status"] = "failed"
    if args.note:
        t["note"] = args.note
    save(plan, args.plan, args)
    print(f"fail: {args.thread}")


def cmd_status(args):
    plan = load(args.plan)
    unfinished = 0
    for t in plan.get("threads", []):
        st = t.get("status", "pending")
        if st in ("pending", "running"):
            unfinished += 1
        print(
            f"{t.get('id', '?'):<16} {t.get('executor', '?'):<6} "
            f"{st:<8} agent={t.get('agent_id', '-'):<18} "
            f"files={len(t.get('files', []))} actual={len(t.get('actual_files', []))}"
        )
    sys.exit(1 if unfinished else 0)


def cmd_restore(args):
    src = backup_path(args.plan, args)
    if not os.path.exists(src):
        sys.exit(f"error: no backup at {src}")
    os.makedirs(os.path.dirname(os.path.abspath(args.plan)) or ".", exist_ok=True)
    shutil.copyfile(src, args.plan)
    print(f"restore: {src} -> {args.plan}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", help="git repository root (default: current toplevel)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("build"); s.add_argument("plan"); s.set_defaults(fn=cmd_build)
    s = sub.add_parser("launch"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("agent_id"); s.add_argument("--worktree"); s.add_argument("--branch"); s.set_defaults(fn=cmd_launch)
    s = sub.add_parser("done"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("--report"); s.add_argument("--summary"); s.set_defaults(fn=cmd_done)
    s = sub.add_parser("fail"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("--note"); s.set_defaults(fn=cmd_fail)
    s = sub.add_parser("status"); s.add_argument("plan"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("restore"); s.add_argument("plan"); s.set_defaults(fn=cmd_restore)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
