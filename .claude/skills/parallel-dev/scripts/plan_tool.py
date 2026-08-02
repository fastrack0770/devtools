#!/usr/bin/env python3
"""Mechanical bookkeeping of a parallel-dev run, so the orchestrator model spends its
context on decisions rather than on JSON surgery.

Commands (all mutating commands auto-backup the plan, see DURABILITY below):

  build <plan> [--rebuild THREAD ...]
      Fill threads[].prompt from the plan's `prompt_template` + per-thread fields.
      The plan stores the boilerplate ONCE (template.intro / template.tail) and each
      thread stores only what is unique to it: `task`, `files`, `contract_ids`,
      `verify`. Threads that already carry a literal `prompt` are left untouched and
      reported as skipped; --rebuild <thread-id> (repeatable) discards the stored
      prompt of that thread first, so an edited `task` takes effect.

  launch <plan> <thread-id> <agent-id> [--worktree <path>] [--branch <name>]
      status=running, record agent_id, worktree and branch. When --worktree is
      omitted the worktree is CREATED here: path <plan-dir>/wt-<thread-id>, branch
      --branch or pd/<thread-id>, branched off the repo's current HEAD. Either way
      the files listed in the plan's optional `worktree_seed_files` (repo-relative;
      e.g. local.properties) are copied into the worktree when absent — untracked
      per-machine config that a fresh worktree otherwise lacks.

  done <plan> <thread-id> [--report <file>] [--summary <text>]
      status=done. With --report (or a report piped to stdin) the agent's final
      message is parsed for the template's three sections: FILES CHANGED -> the
      thread's actual_files, SUMMARY -> summary, DEVIATIONS -> deviations
      (omitted when literally "none"). --summary overrides the parsed summary.
      If the thread has a worktree with uncommitted changes, their full diff
      (including untracked files) is saved to .git/parallel-dev/patches/<thread>.patch
      — insurance against losing an agent's uncommitted work to a scratchpad wipe.

  fail <plan> <thread-id> [--note <text>]
      status=failed with an optional note — for an agent that was cancelled or
      returned unusable work.

  reset <plan> <thread-id>
      Back to status=pending for a relaunch: clears prompt, summary, deviations,
      note, agent_id, actual_files, worktree and branch. Follow with `build`
      (the cleared prompt is reassembled from the thread's `task`) and `launch`.

  merged <plan> <thread-id> [--commit <sha>]
      status=merged (+ merge_commit) — recorded by the orchestrator right after
      `git merge` of the thread branch, so a recovery never has to re-derive
      "what already landed" from the git log.

  status <plan> [-v] [--no-gate]
      One line per thread: id, executor, status, agent id, files counts.
      -v adds per-thread detail: planned-but-unreported / reported-outside file
      names, worktree, merge commit, deviations and notes.
      Exit code 1 while any thread is pending/running (usable as a wave gate);
      --no-gate always exits 0 (for use inside && chains that must not break).

  mirror <plan>
      Re-copy the plan to the durable backup. plan_tool's own commands mirror on
      every write, but a hand edit of the JSON does not — run this after one.

  restore <plan> [--force]
      Copy the durable backup back to <plan> (after a scratchpad wipe). Refuses
      to overwrite a <plan> that is NEWER than the backup (likely hand-edited and
      never mirrored) unless --force is given.

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

# Fields `reset` clears so a relaunch starts from a clean thread record.
RESET_FIELDS = ("prompt", "summary", "deviations", "note", "agent_id", "merge_commit")


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
    rebuild = set(args.rebuild or [])
    unknown = rebuild - {t.get("id") for t in plan.get("threads", [])}
    if unknown:
        sys.exit(f"error: --rebuild names unknown thread(s): {sorted(unknown)}")
    built, kept = 0, []
    for t in plan.get("threads", []):
        if t.get("executor") != "agent":
            continue
        if t.get("id") in rebuild:
            t.pop("prompt", None)
        if t.get("prompt"):
            kept.append(t.get("id"))
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
    if kept:
        print(f"build: kept existing prompt(s) for: {', '.join(kept)} "
              f"(use --rebuild <id> to reassemble after editing `task`)")


def seed_worktree(plan, worktree, root):
    for rel in plan.get("worktree_seed_files", []):
        src, dst = os.path.join(root, rel), os.path.join(worktree, rel)
        if os.path.isfile(src) and not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            shutil.copyfile(src, dst)
            print(f"launch: seeded {rel}")


def cmd_launch(args):
    plan = load(args.plan)
    t = thread_of(plan, args.thread)
    root = repo_root(args)
    worktree, branch = args.worktree, args.branch
    if not worktree:
        branch = branch or f"pd/{args.thread}"
        worktree = os.path.join(
            os.path.dirname(os.path.abspath(args.plan)), f"wt-{args.thread}"
        )
        if not os.path.isdir(worktree):
            res = subprocess.run(
                ["git", "-C", root, "worktree", "add", worktree, "-b", branch],
                capture_output=True, text=True,
            )
            if res.returncode != 0:
                sys.exit(f"error: git worktree add failed:\n{res.stderr.strip()}")
            print(f"launch: worktree created at {worktree} (branch {branch})")
    if os.path.isdir(worktree):
        seed_worktree(plan, worktree, root)
    t["status"] = "running"
    t["agent_id"] = args.agent_id
    t["worktree"] = worktree
    if branch:
        t["branch"] = branch
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


def snapshot_worktree(t, thread_id, args):
    """Save the worktree's uncommitted diff (untracked included) as a durable patch."""
    wt = t.get("worktree")
    if not wt or not os.path.isdir(wt):
        return
    try:
        # --intent-to-add makes untracked files visible to `diff`; reset drops the
        # intent entries again, so the agent's worktree is left as it was found.
        subprocess.run(["git", "-C", wt, "add", "-A", "--intent-to-add"],
                       capture_output=True, check=True)
        diff = subprocess.run(["git", "-C", wt, "diff", "--binary"],
                              capture_output=True, check=True).stdout
        subprocess.run(["git", "-C", wt, "reset", "-q"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"warn: could not snapshot worktree diff: {e}")
        return
    if not diff.strip():
        return
    pdir = os.path.join(repo_root(args), ".git", "parallel-dev", "patches")
    os.makedirs(pdir, exist_ok=True)
    patch = os.path.join(pdir, f"{thread_id}.patch")
    with open(patch, "wb") as f:
        f.write(diff)
    t["patch"] = patch
    print(f"done: work snapshot -> {patch} (apply with `git apply` if the worktree is lost)")


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
    snapshot_worktree(t, args.thread, args)
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


def cmd_reset(args):
    plan = load(args.plan)
    t = thread_of(plan, args.thread)
    for k in RESET_FIELDS:
        t.pop(k, None)
    t["status"] = "pending"
    t["actual_files"] = []
    t["worktree"] = None
    t["branch"] = None
    save(plan, args.plan, args)
    print(f"reset: {args.thread} back to pending — run `build` (prompt was cleared), then `launch`")


def cmd_merged(args):
    plan = load(args.plan)
    t = thread_of(plan, args.thread)
    if t.get("status") not in ("done", "merged"):
        print(f"warn: merging a thread whose status is '{t.get('status')}', not 'done'")
    t["status"] = "merged"
    if args.commit:
        t["merge_commit"] = args.commit
    save(plan, args.plan, args)
    print(f"merged: {args.thread}" + (f" @ {args.commit}" if args.commit else ""))


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
        if not args.verbose:
            continue
        planned = {f for f in t.get("files", [])}
        actual = {f for f in t.get("actual_files") or []}
        detail = []
        if actual:
            unreported = sorted(planned - actual)
            outside = sorted(actual - planned)
            if unreported:
                detail.append("planned, not reported: " + ", ".join(unreported))
            if outside:
                detail.append("reported OUTSIDE boundary: " + ", ".join(outside))
        for key, label in (("worktree", "worktree"), ("branch", "branch"),
                           ("merge_commit", "merge"), ("patch", "patch"),
                           ("note", "note"), ("deviations", "deviations")):
            v = t.get(key)
            if v:
                v = str(v).replace("\n", " ¶ ")
                detail.append(f"{label}: {v[:160]}")
        for line in detail:
            print(f"    {line}")
    sys.exit(0 if args.no_gate else (1 if unfinished else 0))


def cmd_mirror(args):
    plan = load(args.plan)  # validates the JSON before it becomes the backup
    save(plan, args.plan, args)
    print(f"mirror: {args.plan} -> {backup_path(args.plan, args)}")


def cmd_restore(args):
    src = backup_path(args.plan, args)
    if not os.path.exists(src):
        sys.exit(f"error: no backup at {src}")
    if (os.path.exists(args.plan)
            and os.path.getmtime(args.plan) > os.path.getmtime(src)
            and not args.force):
        sys.exit(
            "error: the plan is NEWER than the backup — it may hold hand edits that were "
            "never mirrored. Run `mirror` to keep them, or `restore --force` to discard them."
        )
    os.makedirs(os.path.dirname(os.path.abspath(args.plan)) or ".", exist_ok=True)
    shutil.copyfile(src, args.plan)
    print(f"restore: {src} -> {args.plan}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", help="git repository root (default: current toplevel)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("build"); s.add_argument("plan"); s.add_argument("--rebuild", action="append", metavar="THREAD"); s.set_defaults(fn=cmd_build)
    s = sub.add_parser("launch"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("agent_id"); s.add_argument("--worktree"); s.add_argument("--branch"); s.set_defaults(fn=cmd_launch)
    s = sub.add_parser("done"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("--report"); s.add_argument("--summary"); s.set_defaults(fn=cmd_done)
    s = sub.add_parser("fail"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("--note"); s.set_defaults(fn=cmd_fail)
    s = sub.add_parser("reset"); s.add_argument("plan"); s.add_argument("thread"); s.set_defaults(fn=cmd_reset)
    s = sub.add_parser("merged"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("--commit"); s.set_defaults(fn=cmd_merged)
    s = sub.add_parser("status"); s.add_argument("plan"); s.add_argument("-v", "--verbose", action="store_true"); s.add_argument("--no-gate", action="store_true"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("mirror"); s.add_argument("plan"); s.set_defaults(fn=cmd_mirror)
    s = sub.add_parser("restore"); s.add_argument("plan"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_restore)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
