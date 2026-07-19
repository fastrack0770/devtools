#!/usr/bin/env python3
"""Validate parallel-dev partition plans and audit agent file boundaries.

Usage:
  check_partition.py check    <plan.json> [--repo DIR]
  check_partition.py snapshot <plan.json> [--repo DIR]
  check_partition.py audit    <plan.json> [--repo DIR]

check    - verify that thread file sets are pairwise disjoint and do not
           collide with deferred_hub_edits; run before launching agents.
snapshot - record files already changed in the working tree into
           <plan.json>.baseline so the audit can exclude pre-existing edits;
           run right before launching the first wave.
audit    - after the wave: compare actual git changes (minus the baseline)
           against the union of planned files, and each thread's reported
           actual_files against its allowed list.

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
    files = set()
    for line in res.stdout.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.add(norm(path.strip().strip('"')))
    return files


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
    print("check: OK — all thread file sets are disjoint" if ok
          else "check: FAILED — fix the partition before launching agents")
    return 0 if ok else 1


def cmd_snapshot(plan, args):
    baseline = args.plan + ".baseline"
    files = sorted(changed_files(args.repo))
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
    allowed = set().union(*by_thread.values()) if by_thread else set()
    allowed |= {norm(f) for f in plan.get("deferred_hub_edits", [])}
    changed = changed_files(args.repo) - baseline

    ok = True
    unclaimed = sorted(changed - allowed)
    if unclaimed:
        ok = False
        print("VIOLATION: files changed outside the plan:")
        for f in unclaimed:
            print(f"  {f}")
    for t in plan["threads"]:
        tid = t.get("id", "?")
        actual = {norm(f) for f in t.get("actual_files") or []}
        extra = sorted(actual - by_thread.get(tid, set()))
        if extra:
            ok = False
            print(f"VIOLATION: thread '{tid}' reported files outside its boundary:")
            for f in extra:
                print(f"  {f}")
    untouched = sorted(allowed - changed - baseline)
    if untouched:
        print("info: planned but unchanged files (may be fine):")
        for f in untouched:
            print(f"  {f}")
    print("audit: OK — all changes stay within the plan" if ok
          else "audit: FAILED — resolve violations before merging")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["check", "snapshot", "audit"])
    ap.add_argument("plan", help="path to parallel-dev-plan.json")
    ap.add_argument("--repo", default=".", help="repository root (default: cwd)")
    args = ap.parse_args()
    plan = load_plan(args.plan)
    sys.exit({"check": cmd_check, "snapshot": cmd_snapshot, "audit": cmd_audit}[args.command](plan, args))


if __name__ == "__main__":
    main()
