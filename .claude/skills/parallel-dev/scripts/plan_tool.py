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
      --branch or pd/<thread-id>, branched off the repo's current HEAD; a directory
      already sitting at that path is an error, not something to adopt (`reset` is
      how a relaunch clears it). An explicit --worktree must be the root of an
      existing git worktree. Either way the files listed in the plan's optional
      `worktree_seed_files` (repo-relative; e.g. local.properties) are copied into
      the worktree when absent — untracked per-machine config that a fresh worktree
      otherwise lacks.

  done <plan> <thread-id> [--report <file>] [--summary <text>] [--allow-unparsed]
      status=done. With --report (or a report piped to stdin) the agent's final
      message is parsed for the template's three sections: FILES CHANGED -> the
      thread's actual_files, SUMMARY -> summary, DEVIATIONS -> deviations
      (omitted when literally "none"). --summary overrides the parsed summary.
      Ending up with NO actual_files is an ERROR — whether the report was absent,
      empty, unparseable, or listed no files — because the audit's per-thread boundary
      check would then have nothing to check and the thread would reach the merge gate
      unverified. --allow-unparsed records it anyway and marks the thread
      `unparsed_report` so `status -v` says the boundary was never verified.
      If the thread has a worktree with uncommitted changes, their full diff
      (staged, unstaged and untracked) is saved to
      .git/parallel-dev/patches/<slot>/<thread>.patch — insurance against losing an
      agent's uncommitted work to a scratchpad wipe. It does NOT cover commits the
      agent made on its own branch.

  fail <plan> <thread-id> [--note <text>]
      status=failed with an optional note — for an agent that was cancelled or
      returned unusable work. Snapshots the worktree first, so partial work survives
      the `reset` that usually follows.

  reset <plan> <thread-id> [--keep-worktree] [--force]
      Back to status=pending for a relaunch: snapshots whatever is in the worktree
      (recorded as `salvaged_patch`), then DELETES the worktree and its branch, and
      clears prompt, summary, deviations, note, agent_id, actual_files, worktree and
      branch. Without the deletion the next `launch` would hand the new agent the
      previous attempt's leftovers. Deletion is ABORTED (and the plan keeps pointing
      at what survived) when the snapshot failed or when the branch carries commits
      that are merged nowhere — the patch covers uncommitted work only, so those
      commits are the only copy. --force deletes regardless, discarding that work;
      --keep-worktree resets only the record. Follow with `build` (the cleared prompt
      is reassembled from the thread's `task`) and `launch`.

  merged <plan> <thread-id> [--commit <sha>]
      status=merged (+ merge_commit) — recorded by the orchestrator right after
      `git merge` of the thread branch, so a recovery never has to re-derive
      "what already landed" from the git log.

  status <plan> [-v] [--no-gate]
      One line per thread: id, executor, status, agent id, files counts.
      -v adds per-thread detail: planned-but-unreported / reported-outside file
      names, worktree, merge commit, deviations and notes.
      Exit code 1 while any thread is pending/running/failed (usable as a wave gate
      — `failed` is terminal but not finished, and must be reset or dropped from the
      plan before the merge step);
      --no-gate always exits 0 (for use inside && chains that must not break).

  mirror <plan>
      Re-copy the plan to the durable backup. plan_tool's own commands mirror on
      every write, but a hand edit of the JSON does not — run this after one.

  restore <plan> [--force]
      Copy the durable backup back to <plan> (after a scratchpad wipe). Refuses
      to overwrite a <plan> that is NEWER than the backup (likely hand-edited and
      never mirrored) unless --force is given.

DURABILITY: every mutating command writes a copy to <repo>/.git/parallel-dev/
(same basename, plus a <basename>.source file recording which plan path it came
from — a second concurrent run under the same canonical filename atomically claims
its own slot instead of overwriting the first one's backup, and its patches go under
patches/<slot>/ for the same reason). The .git directory survives
scratchpad wipes and process restarts and is never committed, which makes it the
recovery point the scratchpad turned out not to be. --repo defaults to the current
directory's git toplevel.

Prompt assembly (build): a thread prompt becomes

    {intro}\n{task}\n\n## File boundary (hard rule)\n...files...\n
    {## Contracts block from contract_ids, if any}\n{verify}\n{tail}

with the boundary and contracts wording fixed here so every run carries the
same non-negotiables without the orchestrator retyping them.
"""

import argparse
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile

# Verbatim copies of the corresponding blocks in references/agent-prompt-template.md — `build`
# splices them in so the orchestrator never retypes them. Edit both sides together.
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
RESET_FIELDS = ("prompt", "summary", "deviations", "note", "agent_id", "merge_commit",
                "patch", "salvaged_patch", "unparsed_report")


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


def backup_dir(args):
    return os.path.join(repo_root(args), ".git", "parallel-dev")


def slot_candidates(plan_path, args):
    """Backup filenames this plan may occupy, best first.

    The canonical basename comes first so that recovery still works from a NEW session whose
    scratchpad path differs from the original. The hashed fallback is what a second
    concurrent run (same canonical `parallel-dev-plan.json` name, different scratchpad) takes
    instead of clobbering the first one's backup.
    """
    d, src, base = backup_dir(args), os.path.abspath(plan_path), os.path.basename(plan_path)
    stem, ext = os.path.splitext(base)
    digest = hashlib.sha1(src.encode()).hexdigest()[:8]
    return [os.path.join(d, base), os.path.join(d, f"{stem}-{digest}{ext}")]


def backup_path(plan_path, args):
    """Look up this plan's backup slot without claiming anything (read path)."""
    src = os.path.abspath(plan_path)
    for cand in slot_candidates(plan_path, args):
        owner = read_source_marker(cand)
        if owner is None or owner == src:
            return cand
    return slot_candidates(plan_path, args)[-1]


def claim_backup_slot(plan_path, args):
    """Take ownership of a backup slot (write path), atomically."""
    src = os.path.abspath(plan_path)
    os.makedirs(backup_dir(args), exist_ok=True)
    for cand in slot_candidates(plan_path, args):
        try:
            # O_EXCL makes the claim atomic: two runs racing to start cannot both conclude
            # that the canonical name is free and then overwrite each other's backup.
            fd = os.open(cand + ".source", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(src + "\n")
            return cand
        except FileExistsError:
            if read_source_marker(cand) == src:
                return cand
    sys.exit(f"error: could not claim a backup slot for {plan_path} in {backup_dir(args)}")


# Known limitation: a backup written by an older version of this tool has no `.source` marker,
# so the first run to touch it adopts it. Two pre-upgrade runs sharing the canonical basename
# would have been clobbering each other already; the loser now keeps its own hashed slot, but
# the legacy file itself still goes to the winner.


def read_source_marker(backup):
    try:
        with open(backup + ".source", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def save(plan, plan_path, args):
    body = json.dumps(plan, ensure_ascii=False, indent=1)
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(body)
    dst = claim_backup_slot(plan_path, args)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(body)
    if os.path.basename(dst) != os.path.basename(plan_path):
        print(f"note: another run owns the '{os.path.basename(plan_path)}' backup slot; "
              f"this run mirrors to {dst}")


def patches_dir(args):
    """Patches live under this run's own backup slot — two runs that happen to use the same
    thread ids must not overwrite each other's salvaged work. Claims the slot rather than
    merely looking it up, so a patch written before this run's first `save()` cannot land in
    a slot that a concurrent run then takes.
    """
    slot = os.path.splitext(os.path.basename(claim_backup_slot(args.plan, args)))[0]
    return os.path.join(backup_dir(args), "patches", slot)


def thread_of(plan, thread_id):
    for t in plan.get("threads", []):
        if t.get("id") == thread_id:
            return t
    sys.exit(f"error: no thread with id '{thread_id}' in the plan")


def cmd_build(args):
    plan = load(args.plan)
    tpl = plan.get("prompt_template") or {}
    intro, tail = tpl.get("intro", ""), tpl.get("tail", "")
    contracts = {}
    for c in plan.get("contracts", []):
        if not c.get("id"):
            continue
        if not c.get("definition"):
            sys.exit(f"error: contract '{c['id']}' has no `definition`")
        contracts[c["id"]] = c["definition"]
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
    if worktree:
        if not os.path.isdir(worktree):
            sys.exit(f"error: --worktree {worktree} does not exist — create it, or omit "
                     "--worktree to have launch create one")
        top = subprocess.run(["git", "-C", worktree, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
        if top.returncode != 0 or os.path.realpath(top.stdout.strip()) != os.path.realpath(worktree):
            sys.exit(f"error: --worktree {worktree} is not the root of a git worktree")
        # Take the branch from the worktree rather than believing --branch. `reset` deletes
        # whatever branch is recorded here, and an unrelated name would send it after someone
        # else's branch entirely.
        head = subprocess.run(["git", "-C", worktree, "rev-parse", "--abbrev-ref", "HEAD"],
                              capture_output=True, text=True)
        checked_out = head.stdout.strip() if head.returncode == 0 else ""
        if checked_out in ("", "HEAD"):
            sys.exit(f"error: --worktree {worktree} is on a detached HEAD — check a branch out "
                     "there first, so the thread's work has somewhere to be merged from")
        if branch and branch != checked_out:
            sys.exit(f"error: --branch {branch} does not match the branch checked out in "
                     f"{worktree} ({checked_out}); drop --branch to adopt the worktree's own")
        branch = checked_out
    else:
        branch = branch or f"pd/{args.thread}"
        worktree = os.path.join(
            os.path.dirname(os.path.abspath(args.plan)), f"wt-{args.thread}"
        )
        # Silently adopting a leftover directory used to hand the new agent the previous
        # attempt's half-finished files. A relaunch goes through `reset`, which clears both.
        if os.path.isdir(worktree):
            sys.exit(f"error: {worktree} already exists — an earlier attempt at "
                     f"'{args.thread}' left it behind. Run `reset {args.plan} {args.thread}` "
                     "first (it salvages the work and removes worktree + branch), or pass "
                     "--worktree to adopt it deliberately.")
        res = subprocess.run(
            ["git", "-C", root, "worktree", "add", worktree, "-b", branch],
            capture_output=True, text=True,
        )
        if res.returncode != 0:
            sys.exit(f"error: git worktree add failed:\n{res.stderr.strip()}\n"
                     f"hint: if branch '{branch}' is left over from an earlier attempt, "
                     "`reset` this thread first, or pass --branch <other-name>.")
        print(f"launch: worktree created at {worktree} (branch {branch})")
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
    """Save the worktree's uncommitted diff (untracked included) as a durable patch.

    The `--intent-to-add` marking that makes untracked files visible to `diff` happens in a
    THROWAWAY COPY of the index. Doing it in the real index and undoing it with `git reset`
    (as this once did) discards staging the agent set up deliberately — and plain `git diff`
    compares index-to-worktree, so every staged hunk would be missing from the patch that is
    sold as insurance against losing the agent's work. `diff HEAD` against the scratch index
    captures staged and unstaged and untracked in one pass, and touches nothing.

    Returns True when the worktree's state is safely on disk (including "there was nothing to
    save"), False when the snapshot FAILED. Callers that are about to delete the worktree must
    check it: silently proceeding past a failed snapshot destroys the very work this exists to
    protect.
    """
    wt = t.get("worktree")
    if not wt or not os.path.isdir(wt):
        return True
    tmp_index = None
    try:
        real_index = subprocess.run(
            ["git", "-C", wt, "rev-parse", "--git-path", "index"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if not os.path.isabs(real_index):
            real_index = os.path.join(wt, real_index)
        fd, tmp_index = tempfile.mkstemp(prefix="pd-index-")
        os.close(fd)
        if os.path.exists(real_index):
            shutil.copyfile(real_index, tmp_index)
        else:
            os.remove(tmp_index)  # let git create a fresh one; an empty file is not a valid index
        env = {**os.environ, "GIT_INDEX_FILE": tmp_index}
        subprocess.run(["git", "-C", wt, "add", "-A", "--intent-to-add"],
                       capture_output=True, check=True, env=env)
        diff = subprocess.run(["git", "-C", wt, "diff", "HEAD", "--binary"],
                              capture_output=True, check=True, env=env).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"warn: could not snapshot worktree diff: {e}")
        return False
    finally:
        if tmp_index and os.path.exists(tmp_index):
            os.remove(tmp_index)
    if not diff.strip():
        # Nothing uncommitted left (e.g. the agent committed its work). Drop any patch from an
        # earlier attempt so `reset` does not report it as this attempt's salvage.
        t.pop("patch", None)
        return True
    try:
        pdir = patches_dir(args)
        os.makedirs(pdir, exist_ok=True)
        patch = os.path.join(pdir, f"{thread_id}.patch")
        with open(patch, "wb") as f:
            f.write(diff)
    except OSError as e:
        print(f"warn: could not write the worktree patch: {e}")
        return False
    t["patch"] = patch
    print(f"done: work snapshot -> {patch} (apply with `git apply` if the worktree is lost)")
    return True


def stdin_has_data(timeout=0.25):
    """Whether a report is actually waiting on stdin.

    `not isatty()` alone is not enough. Run from a tool harness rather than a shell, stdin is
    typically an inherited pipe that nobody ever writes to, and a bare `read()` then blocks the
    command forever — which is exactly how the orchestrator invokes `done --summary ...` with
    no report. A pipe carrying a real report, a redirect, and /dev/null are all readable at
    once; only the idle pipe times out.
    """
    if sys.stdin is None or sys.stdin.isatty():
        return False
    try:
        return bool(select.select([sys.stdin], [], [], timeout)[0])
    except (OSError, ValueError):
        return False


def cmd_done(args):
    plan = load(args.plan)
    t = thread_of(plan, args.thread)
    report, source = None, None
    if args.report:
        with open(args.report, encoding="utf-8") as f:
            report, source = f.read(), args.report
    elif stdin_has_data():
        report, source = sys.stdin.read(), "stdin"
    m = SECTION_RE.search(report) if report else None
    files = []
    if m:
        files = [
            ln.strip().lstrip("-* ").strip("`")
            for ln in m.group("files").splitlines()
            if ln.strip() and not ln.strip().startswith("```")
        ]
        files = [f for f in files if f]
        t["summary"] = m.group("summary").strip()
        dev = m.group("dev").strip()
        # Always overwrite from THIS report: a re-run that no longer flags a deviation must
        # not leave the resolved one standing in the plan.
        t.pop("deviations", None)
        if dev and dev.lower() not in ("none", "none."):
            t["deviations"] = dev
    # Record what this report said, not what a previous `done` left behind — otherwise a stale
    # actual_files would let an unparseable re-run through the gate below.
    t["actual_files"] = files
    if args.summary:
        t["summary"] = args.summary
    # The gate is on actual_files, not on "a report was supplied": an absent report, an empty
    # one, and a well-formed one with an empty FILES CHANGED section all leave the boundary
    # half of the audit with nothing to check, and the thread would reach the merge gate
    # unverified. Salvage the work, then stop and make the operator look.
    if not t.get("actual_files"):
        if not args.allow_unparsed:
            snapshot_worktree(t, args.thread, args)
            save(plan, args.plan, args)
            sys.exit("error: no FILES CHANGED entries were parsed"
                     + (f" from the report on {source}" if source else
                        " — no report was given on stdin or via --report")
                     + f", so '{args.thread}' stays {t.get('status', 'pending')}. Re-run with "
                     "the agent's three-section report, or with --allow-unparsed --summary "
                     "<text> to record it by hand — the audit's per-thread boundary check is "
                     "then skipped and you must review that diff yourself.")
        print("warn: recording `done` with no actual_files; boundary NOT verified")
        t["unparsed_report"] = True
    else:
        t.pop("unparsed_report", None)
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
    # A cancelled agent's partial work is still worth keeping — `reset` is about to delete
    # the worktree it lives in.
    snapshot_worktree(t, args.thread, args)
    save(plan, args.plan, args)
    print(f"fail: {args.thread}")


def remove_worktree(t, root, force=False):
    """Delete the thread's worktree and branch so the next `launch` really starts clean.

    Returns False if anything survived — the caller must then leave the plan pointing at it,
    or the tool forgets about a directory/branch that will block the next `launch`.
    """
    ok = True
    wt, br = t.get("worktree"), t.get("branch")
    if wt and os.path.isdir(wt):
        res = subprocess.run(["git", "-C", root, "worktree", "remove", "--force", wt],
                             capture_output=True, text=True)
        if res.returncode == 0:
            print(f"reset: worktree removed ({wt})")
        else:
            ok = False
            print(f"warn: could not remove worktree {wt}: {res.stderr.strip()}")
    subprocess.run(["git", "-C", root, "worktree", "prune"], capture_output=True)
    if br:
        # `-d`, not `-D`: the patch snapshot covers UNCOMMITTED work only, so a branch that
        # carries commits of its own (the template says to leave work uncommitted, but nothing
        # enforces it) must not be force-destroyed by a bookkeeping command.
        res = subprocess.run(["git", "-C", root, "branch", "-D" if force else "-d", br],
                             capture_output=True, text=True)
        if res.returncode == 0:
            print(f"reset: branch {br} deleted")
        else:
            ok = False
            print(f"warn: could not delete branch {br}: {res.stderr.strip()}")
            if not force:
                print(f"      '{br}' most likely holds commits that are not merged anywhere, "
                      "and the patch snapshot does NOT cover commits. Merge or cherry-pick "
                      "them first, or re-run `reset --force` to destroy them.")
    return ok


def cmd_reset(args):
    plan = load(args.plan)
    t = thread_of(plan, args.thread)
    salvaged = None
    if not args.keep_worktree:
        if not snapshot_worktree(t, args.thread, args) and not args.force:
            save(plan, args.plan, args)
            sys.exit(f"error: could not snapshot the worktree of '{args.thread}', so reset is "
                     "NOT deleting it — the uncommitted work would be lost with no patch to "
                     "recover from. Fix the cause above, copy the worktree aside, or re-run "
                     "with --force to discard the work deliberately.")
        salvaged = t.get("patch")
        if not remove_worktree(t, repo_root(args), force=args.force) and not args.force:
            save(plan, args.plan, args)
            sys.exit(f"error: reset aborted for '{args.thread}' — see the warning above. The "
                     "plan still points at the surviving worktree/branch, so a follow-up "
                     "`reset` (or `reset --force`) can finish the job.")
    for k in RESET_FIELDS:
        t.pop(k, None)
    t["status"] = "pending"
    t["actual_files"] = []
    if not args.keep_worktree:
        t["worktree"] = None
        t["branch"] = None
    if salvaged:
        t["salvaged_patch"] = salvaged
    save(plan, args.plan, args)
    print(f"reset: {args.thread} back to pending — run `build` (prompt was cleared), then `launch`"
          + (f"\nreset: previous attempt salvaged to {salvaged}" if salvaged else ""))


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
    unfinished, failed = 0, []
    for t in plan.get("threads", []):
        st = t.get("status", "pending")
        if st in ("pending", "running"):
            unfinished += 1
        elif st == "failed":
            # `failed` is terminal but NOT finished: letting it open the gate sends the
            # orchestrator into Step 6 to merge a branch that holds nothing usable.
            failed.append(t.get("id", "?"))
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
        if t.get("unparsed_report"):
            detail.append("report was NOT parsed (--allow-unparsed): actual_files unverified")
        for key, label in (("worktree", "worktree"), ("branch", "branch"),
                           ("merge_commit", "merge"), ("patch", "patch"),
                           ("salvaged_patch", "salvaged patch"),
                           ("note", "note"), ("deviations", "deviations")):
            v = t.get(key)
            if v:
                v = str(v).replace("\n", " ¶ ")
                detail.append(f"{label}: {v[:160]}")
        for line in detail:
            print(f"    {line}")
    if failed:
        print(f"gate: {len(failed)} failed thread(s) — {', '.join(failed)}: "
              "`reset` and relaunch each, or drop it from the plan, before merging")
    sys.exit(0 if args.no_gate else (1 if unfinished or failed else 0))


def cmd_mirror(args):
    plan = load(args.plan)  # validates the JSON before it becomes the backup
    save(plan, args.plan, args)
    print(f"mirror: {args.plan} -> {backup_path(args.plan, args)}")


def cmd_restore(args):
    src = backup_path(args.plan, args)
    if not os.path.exists(src):
        # Recovery after a restart: the scratchpad path (and so the plan path) may differ from
        # the one that produced the backup. Fall back to the backups actually on disk.
        d = backup_dir(args)
        found = sorted(f for f in os.listdir(d) if not f.endswith(".source")) if os.path.isdir(d) else []
        found = [f for f in found if os.path.isfile(os.path.join(d, f))]
        if len(found) != 1:
            listing = "\n".join(
                f"  {os.path.join(d, f)}  (from {read_source_marker(os.path.join(d, f)) or 'unknown'})"
                for f in found
            )
            sys.exit(f"error: no backup at {src}" + (f"; candidates:\n{listing}\n"
                     "Pass the plan path that produced one of these." if found else ""))
        src = os.path.join(d, found[0])
        print(f"restore: no exact match; using the only backup present, from "
              f"{read_source_marker(src) or 'unknown'}")
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
    s = sub.add_parser("done"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("--report"); s.add_argument("--summary"); s.add_argument("--allow-unparsed", action="store_true", help="record `done` even when the report does not parse (skips the boundary check)"); s.set_defaults(fn=cmd_done)
    s = sub.add_parser("fail"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("--note"); s.set_defaults(fn=cmd_fail)
    s = sub.add_parser("reset"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("--keep-worktree", action="store_true", help="leave the worktree and branch in place (default: salvage a patch, then delete both)"); s.add_argument("--force", action="store_true", help="delete the worktree and branch even when the snapshot failed or the branch holds unmerged commits (destroys that work)"); s.set_defaults(fn=cmd_reset)
    s = sub.add_parser("merged"); s.add_argument("plan"); s.add_argument("thread"); s.add_argument("--commit"); s.set_defaults(fn=cmd_merged)
    s = sub.add_parser("status"); s.add_argument("plan"); s.add_argument("-v", "--verbose", action="store_true"); s.add_argument("--no-gate", action="store_true"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("mirror"); s.add_argument("plan"); s.set_defaults(fn=cmd_mirror)
    s = sub.add_parser("restore"); s.add_argument("plan"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_restore)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
