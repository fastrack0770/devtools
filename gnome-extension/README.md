# AI Usage

GNOME Shell top-panel indicators showing how much of your coding-agent usage
limits you have consumed — one bar per CLI, for Claude Code and Codex.

```
Activities  …  [ Claude ▓▓▓▓▓░░░ 74% · 0:48 · Fable 89% ][ Codex ▓░░░░░░░ 2% · 6d 22h ]  ⏻ 🔊 📶
```

Every number is the **used** share of a limit, not the remainder.

- **Progress bar** per provider, tracking the *shortest* limit window that
  provider reports: blue < 75 %, yellow 75–90 %, red 90–100 %. Next to it the
  percentage and a countdown to the reset — `4:22` within a day, `6d 22h`
  beyond it, refreshed every 20 s. A second window, when there is one, is
  appended compactly (`· Fable 89%`, `· Week 85%`).
- **Notifications** when usage crosses 20 / 40 / 60 / 80 / 90 / 100 %, stating
  when the limit resets (critical urgency at ≥ 90 %). Thresholds fire again in
  each new window. The first reading after install only sets the baseline, so
  installing at 85 % announces 90 % rather than replaying 20–80 at once.
- **Click an indicator** for a menu with every window (percent, time left,
  reset time), the extras that provider exposes, and a *Refresh now* button.
  Polling interval: 60 s.
- **Failure handling**: a rate limit or network blip keeps the last known
  numbers on screen, dimmed and marked stale in the menu, instead of blanking
  the panel. After an HTTP 429 automatic polling pauses for 5 minutes;
  *Refresh now* still forces a request.

## No settings, by design

There is no preferences window. A provider's bar appears when that CLI is
installed and logged in, and disappears when it is not — rechecked on every
poll, so logging in to either tool brings its bar up within a minute. Detection
is just the presence of `~/.claude/.credentials.json` and `~/.codex/auth.json`.

## Requirements

- GNOME Shell 42 (Ubuntu 22.04). Other versions are untested — bump
  `shell-version` in `metadata.json` if you want to try.
- `python3` (standard library only, no third-party packages).
- At least one logged-in CLI. With neither, the panel simply stays empty.

  ```bash
  # Claude Code
  curl -fsSL https://claude.ai/install.sh | bash
  claude            # then /login inside the CLI

  # Codex
  npm i -g @openai/codex
  codex login
  ```

## Install

From the repo root:

```bash
make gnome-extension
```

Then **log out and log back in** (Wayland cannot restart GNOME Shell in place);
the indicators appear on the right side of the panel.

To uninstall:

```bash
make uninstall-gnome-extension
```

### Upgrading from `claude-usage@claude-usage-control`

This extension used to ship under that UUID. A UUID is the install identity, so
the renamed package would otherwise sit *alongside* the old one and you would
see two Claude bars. `deploy/gnome-extension.sh` disables and deletes the old
install before copying the new one — nothing to do by hand.

## Where the data comes from

Each provider has its own helper script printing one line of JSON to stdout,
which the extension renders. Neither helper sends anything to a model, so
neither costs inference tokens.

Neither data source is a documented public API — both vendors can change them
at any time, and this project is unaffiliated with Anthropic and OpenAI.

### Claude — `claude-usage-helper.py`

Calls the same endpoint the `/usage` command of the claude CLI uses
(`api.anthropic.com/api/oauth/usage`), with the OAuth token from
`~/.claude/.credentials.json`. Always current, since the server is polled
directly.

To survive endpoint changes, the helper reads its configuration out of the
installed claude binary rather than pinning it: the usage URL, the token
refresh URL, the OAuth client id and the version used in the `User-Agent` are
scraped from the bundled config object inside
`~/.local/share/claude/versions/<version>` (resolved through whatever `claude`
on your `PATH` points at). When the CLI updates, the helper follows it on the
next poll.

The scan is anchored and bounded, so all values come from the same config
object, and it takes ~0.3 s over a 270 MB binary. The result is cached in
`~/.cache/ai-usage-control/cli-meta.json`, keyed by the binary's path, mtime and
size, so it only re-runs after a CLI update. Anything that cannot be found or
validated falls back to the constants at the top of the helper; `config_source`
in the JSON output says which path was taken: `cli`, `cache` or `defaults`.

### Codex — `codex-usage-helper.py`

Two sources, in order.

1. **`codex app-server --stdio`**, JSON-RPC method `account/rateLimits/read`.
   Authoritative and current. A one-shot spawn answers in about a second, so
   no long-lived child process is needed.
2. **The session journal** — the newest `token_count` event carrying
   `rate_limits` in `~/.codex/sessions/**/rollout-*.jsonl`. Free and local, but
   only written while Codex is running, so it is a **stale snapshot**. The
   indicator dims when showing it and the menu states its age.

Deliberately *not* used: replicating the Claude approach of reading
`~/.codex/auth.json` and calling the ChatGPT backend directly. Codex's refresh
token rotates, and a second writer racing the CLI can log you out of Codex —
so this helper never reads or writes that file. Letting `app-server` own the
token is both safer and more durable, since a Codex update carries any auth or
endpoint change along with it.

#### Windows are not fixed

Codex reports one or two windows as `primary`/`secondary`, and these are **not**
synonyms for "5-hour" and "weekly" — a Plus account may return a single weekly
limit and no session window at all. The helper therefore keys off
`windowDurationMins` (300 = 5 h, 10080 = week), sorts what it got shortest-first
and lets the bar track the first one. It accepts both the app-server's camelCase
and the journal's snake_case spellings, so the two sources produce identical
output.

#### When a stale window has already reset

If the newest snapshot is older than its own reset time, the percentage is
dropped and the bar shows `—` rather than a confident `0 %`: the window may
well have been spent from an IDE, the web, or another machine in the meantime.

## Security notes

Read these before installing — the Claude helper touches your credentials file.

- `claude-usage-helper.py` **reads** `~/.claude/.credentials.json` and, when the
  access token has expired, **writes** a refreshed token back to it (atomically,
  under a file lock, preserving every other key). Before the first write it
  saves a backup to `~/.claude/.credentials.json.bak-claude-usage`.
- The refresh goes to `platform.claude.com/v1/oauth/token` with the public
  OAuth client id of the claude CLI. No other host is contacted.
- URLs scraped from the CLI binary are only used if they are `https` on
  `anthropic.com`, `claude.com` or `claude.ai`; anything else is discarded in
  favour of the built-in defaults. The client id is only taken together with a
  token URL that passed this check, since the two are posted alongside your
  refresh token.
- `codex-usage-helper.py` never reads or writes `~/.codex/auth.json`; it only
  checks that the file exists. All Codex network access happens inside
  `codex app-server`, under Codex's own credentials handling.
- Tokens are never printed, logged or copied anywhere else.

## Tests

```bash
gnome-extension/ai-usage@ai-usage-control/tests/run.sh
```

Covers the formatters and both provider parsers — window selection, staleness,
expiry and the two JSON dialects — using `gjs` with a stub for the GNOME Shell
imports. The indicator widget itself needs a live Shell and is not covered.

## Debugging

```bash
EXT="gnome-extension/ai-usage@ai-usage-control"

# Fetch the data by hand (expect a single JSON line each):
python3 "$EXT/claude-usage-helper.py"
python3 "$EXT/codex-usage-helper.py"

# Codex: force the stale session-journal path instead of the app-server
CU_CODEX_NO_APPSERVER=1 python3 "$EXT/codex-usage-helper.py"

# Point either helper at a specific binary:
CU_CLAUDE_BIN=/path/to/claude python3 "$EXT/claude-usage-helper.py"
CU_CODEX_BIN=/path/to/codex   python3 "$EXT/codex-usage-helper.py"

# Claude: ignore the installed CLI and use the built-in endpoint constants
CU_NO_CLI_DISCOVERY=1 python3 "$EXT/claude-usage-helper.py"

# Force a re-scan of the claude CLI:
rm ~/.cache/ai-usage-control/cli-meta.json

# Extension logs:
journalctl --user -f /usr/bin/gnome-shell | grep -i usage

# Override the percent to test colours and notifications:
echo 92 > ~/.cache/ai-usage-control/fake_percent   # Claude (remove to restore)
CU_CODEX_FAKE_PERCENT=92 python3 "$EXT/codex-usage-helper.py"
```

Which notification thresholds have already fired is stored per provider in
`~/.cache/ai-usage-control/state-claude.json` and `state-codex.json`.

## License

MIT — see [LICENSE](LICENSE).
