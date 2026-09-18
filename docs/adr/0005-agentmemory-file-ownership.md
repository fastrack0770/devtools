# 0005: The agentmemory installer classifies files by owner, not by location

## Context
`make install agentmemory` deploys into two directories that already exist on a working machine and are not the installer's to begin with. `~/llm` holds the compose stack next to unrelated user work (a Python venv, leftovers from the pre-container install), and `~/llm/data` plus `~/.agentmemory` hold the memory itself — sessions, observations, the knowledge graph, git-versioned snapshots — accumulated over real work and not reproducible from the repo. The usual case is not a fresh machine but a running stack with a piece missing, so the installer runs against live state far more often than against an empty directory.

## Decision
Every path the installer can reach falls into exactly one of four classes, and the class determines what may happen to it:

- **Repo-owned** — `docker-compose.yml`, `Dockerfile.agentmemory`, `iii-config.docker.yaml`. Replaced from `agentmemory/llm/` when absent or identical; when they differ, the installer prints the diff and stops without touching anything, and only `FORCE=1` replaces them, backing each up first.
- **Generated** — `~/llm/.env`. Same policy, rendered from machine facts plus `agentmemory/versions.env`.
- **User-owned** — `~/.agentmemory/.env`, `preferences.json`, `snapshots/`, `backups/`, and all of `~/llm/data` except `llama-cache`. Created only when absent, never rewritten — not even under `FORCE`. A stale value is reported, with the line to change, and left alone.
- **Foreign** — anything else in either directory. Never read, never written, never removed.

`uninstall` deletes the first two classes, the regenerable `llama-cache`, the host npm package, the containers and the locally built image, and the agent wiring. It keeps the third and fourth untouched, so a later `install` lands on top of the existing memory.

## Why
The classes make the dangerous cases unrepresentable rather than merely discouraged. Silent replacement is the failure that matters: a user asks for the missing Codex hooks and gets an unannounced migration of a stack that was working, which is why drift stops the run instead of backing up and proceeding. In the other direction, memory is the one thing here that cannot be rebuilt — pinning it as user-owned is what makes `uninstall` safe enough to be worth having, and what lets `stop` exist as the lighter operation that deletes nothing at all.

## Consequences
The engine version is pinned in `versions.env` while the state it wrote survives an uninstall, so changing `III_VERSION` over kept data is a data migration rather than an image bump; the installer reports the pairing but cannot verify it. `FORCE=1` is needed once on any machine whose files were placed by hand before this component existed, since the repo ships a parameterised copy that will not compare equal to a hand-written one.
