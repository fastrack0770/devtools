#!/usr/bin/env python3
"""Validate parallel-dev partition plans and audit agent file boundaries.

Usage:
  check_partition.py check    <plan.json> [--repo DIR]
  check_partition.py snapshot <plan.json> [--repo DIR]
  check_partition.py audit    <plan.json> [--repo DIR] [--thread ID]

check    - verify that thread file sets are pairwise disjoint and do not
           collide with deferred_hub_edits; run before launching agents.
snapshot - record files already changed in the working tree into
           <plan.json>.baseline so the audit can exclude pre-existing edits;
           run right before launching the first wave.
audit    - after the wave: compare actual git changes (minus the baseline)
           against the planned files, and each thread's reported actual_files
           against its allowed list. With one worktree per thread, always pass
           --thread <id> alongside --repo <that thread's worktree>: it narrows
           the allowed set to that thread, which is what makes a stray edit into
           a neighbouring thread's file detectable at all. Without --thread the
           allowed set is the union of every thread (the older shared-working-tree
           layout) and cross-thread strays are invisible.

Exit code 0 = clean, 1 = violations found, 2 = usage/plan error.
"""
import argparse
import json
import os
import subprocess
import sys


def norm(path):
    p = os.path.normpath(path.strip()).replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def load_plan(path):
    try:
        with open(path, encoding="utf-8") as f:
            plan = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"error: cannot read plan {path}: {e}")
    if not isinstance(plan.get("threads"), list) or not plan["threads"]:
        sys.exit(f"error: plan {path} has no threads[]")
    return plan


def thread_files(plan):
    out = {}
    for t in plan["threads"]:
        tid = t.get("id") or f"thread-{len(out)}"
        out[tid] = {norm(f) for f in t.get("files", [])}
    return out


def changed_files(repo):
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repo, capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"error: git status failed in {repo}: {e}")
    files, untracked = set(), set()
    for line in res.stdout.splitlines():
        code, path = line[:2], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        p = norm(path.strip().strip('"'))
        files.add(p)
        if code == "??":
            untracked.add(p)
    return files, untracked


def cmd_check(plan, args):
    by_thread = thread_files(plan)
    hub = {norm(f) for f in plan.get("deferred_hub_edits", [])}
    ok = True
    ids = list(by_thread)
    for i, a in enumerate(ids):
        if not by_thread[a]:
            print(f"WARN: thread '{a}' has an empty files list")
        for b in ids[i + 1:]:
            overlap = by_thread[a] & by_thread[b]
            if overlap:
                ok = False
                print(f"OVERLAP between '{a}' and '{b}':")
                for f in sorted(overlap):
                    print(f"  {f}")
        clash = by_thread[a] & hub
        if clash:
            ok = False
            print(f"OVERLAP between '{a}' and deferred_hub_edits:")
            for f in sorted(clash):
                print(f"  {f}")
            print("  hint: hub files live in deferred_hub_edits ONLY — remove them from the "
                  "thread's files; the orchestrator applies them at the merge step.")
    print("check: OK — all thread file sets are disjoint" if ok
          else "check: FAILED — fix the partition before launching agents")
    return 0 if ok else 1


def cmd_snapshot(plan, args):
    baseline = args.plan + ".baseline"
    files = sorted(changed_files(args.repo)[0])
    with open(baseline, "w", encoding="utf-8") as f:
        f.write("\n".join(files) + ("\n" if files else ""))
    print(f"snapshot: {len(files)} pre-existing changed file(s) -> {baseline}")
    return 0


def cmd_audit(plan, args):
    baseline_path = args.plan + ".baseline"
    baseline = set()
    if os.path.exists(baseline_path):
        with open(baseline_path, encoding="utf-8") as f:
            baseline = {norm(l) for l in f if l.strip()}
    else:
        print(f"WARN: no baseline at {baseline_path}; auditing all changes")

    by_thread = thread_files(plan)
    hub = {norm(f) for f in plan.get("deferred_hub_edits", [])}
    threads = plan["threads"]
    if args.thread:
        if args.thread not in by_thread:
            sys.exit(f"error: no thread '{args.thread}' in the plan")
        # One worktree holds exactly one thread's work, so `allowed` is that thread's file
        # set — NOT the union of every thread's. With the union, an agent straying into
        # another thread's files is indistinguishable from legitimate work and the audit,
        # which is the only mechanical guard on the partition invariant, passes it silently.
        allowed = by_thread[args.thread] | hub
        threads = [t for t in threads if t.get("id") == args.thread]
        scope = f"thread '{args.thread}'"
    else:
        allowed = set().union(*by_thread.values()) if by_thread else set()
        allowed |= hub
        scope = "all threads (shared working tree)"
        print("WARN: auditing against the union of every thread's files — a stray edit into "
              "another thread's file cannot be detected. Pass --thread <id> when auditing a "
              "single agent's worktree.")
    # Excuse a seeded path only while it is still UNTRACKED — that is the copy `launch` put
    # there, and untracked files never take part in the branch merge. A seed path that is
    # tracked and modified is the agent editing a repo file, and must still count.
    seeded = {norm(f) for f in plan.get("worktree_seed_files", [])}
    changed, untracked = changed_files(args.repo)
    changed = changed - baseline - (seeded & untracked)
    print(f"audit scope: {scope}, {len(allowed)} allowed path(s)")

    # Collect first, print in labeled sections: a FAILED audit must read unambiguously —
    # during a real run the violation lines and the informational tail were mistaken
    # for one another.
    unclaimed = sorted(changed - allowed)
    boundary = []  # (thread-id, [files])
    unverified = []
    for t in threads:
        tid = t.get("id", "?")
        actual = {norm(f) for f in t.get("actual_files") or []}
        if not actual and t.get("status") in ("done", "merged"):
            unverified.append(tid)
        extra = sorted(actual - by_thread.get(tid, set()))
        if extra:
            boundary.append((tid, extra))
    untouched = sorted(allowed - changed - baseline)
    ok = not unclaimed and not boundary

    if unclaimed:
        print(f"VIOLATIONS — changed outside the plan ({len(unclaimed)}):")
        for f in unclaimed:
            print(f"  {f}")
    for tid, extra in boundary:
        print(f"VIOLATIONS — thread '{tid}' reported outside its boundary ({len(extra)}):")
        for f in extra:
            print(f"  {f}")
    if unverified:
        print(f"WARN: no reported actual_files for finished thread(s) {', '.join(unverified)} "
              "— their boundary was NOT verified; review those diffs by hand.")
    if untouched:
        label = ("work that turned out unnecessary" if args.thread
                 else "another thread's files or work that turned out unnecessary")
        print(f"PLANNED, UNCHANGED ({len(untouched)}) — informational, NOT a violation "
              f"({label}):")
        for f in untouched:
            print(f"  {f}")
    total = len(unclaimed) + sum(len(e) for _, e in boundary)
    print("audit: OK — all changes stay within the plan" if ok
          else f"audit: FAILED — {total} violation(s) above; resolve before merging")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["check", "snapshot", "audit"])
    ap.add_argument("plan", help="path to parallel-dev-plan.json")
    ap.add_argument("--repo", default=".", help="repository root (default: cwd)")
    ap.add_argument("--thread", help="audit: restrict the allowed file set to this thread "
                                     "(use when --repo is that thread's own worktree)")
    args = ap.parse_args()
    plan = load_plan(args.plan)
    sys.exit({"check": cmd_check, "snapshot": cmd_snapshot, "audit": cmd_audit}[args.command](plan, args))


if __name__ == "__main__":
    main()
