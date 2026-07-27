# Claude Usage Control

A GNOME Shell top-panel indicator showing how much of your Claude Code usage
limits you have consumed.

```
Activities   …   [ Usage ▓▓▓▓▓░░░ 74% · 0:48 · Fable 89% ]   ⏻ 🔊 📶
```

Every number is the **used** share of a limit, not the remainder.

- **Progress bar** for the current 5-hour session: blue < 75 %, yellow 75–90 %,
  red 90–100 %. Next to it: the session percentage, a countdown to the limit
  reset (`5:00`, `4:22`, `0:04` — hours:minutes, refreshed every 20 s) and the
  used share of the model-scoped weekly quota (e.g. Fable).
- **Notifications** when usage crosses 20 / 40 / 60 / 80 / 90 / 100 %, stating
  when the limit resets (critical urgency at ≥ 90 %). Thresholds fire again in
  each new 5-hour window.
- **Click the indicator** for a menu with the session (percent, time left,
  reset time), the weekly limit, the model quota and a *Refresh now* button.
  Polling interval: 60 s.
- **Failure handling**: a rate limit or network blip keeps the last known
  numbers on screen, marked stale in the menu, instead of blanking the panel.
  After an HTTP 429 automatic polling pauses for 5 minutes; *Refresh now*
  still forces a request.

## Requirements

- GNOME Shell 42 (Ubuntu 22.04). Other versions are untested — bump
  `shell-version` in `metadata.json` if you want to try.
- `python3` (standard library only, no third-party packages).
- A logged-in Claude Code CLI (`~/.claude/.credentials.json` must exist).

## Install

From the repo root:

```bash
make gnome-extension
```

or directly:

```bash
deploy/gnome-extension.sh
```

Then **log out and log back in** (Wayland cannot restart GNOME Shell in place);
the indicator appears on the right side of the panel.

To uninstall:

```bash
make uninstall-gnome-extension
```

## Where the data comes from

`usage-helper.py` calls the same endpoint the `/usage` command of the claude
CLI uses (`api.anthropic.com/api/oauth/usage`), with the OAuth token from
`~/.claude/.credentials.json`. It prints one line of JSON to stdout, which the
extension renders.

These endpoints are not a documented public API — Anthropic can change them at
any time, and this project is unaffiliated with Anthropic.

### Following the CLI instead of hardcoding

To survive such a change, the helper reads its configuration out of the
installed claude binary rather than pinning it: the usage URL, the token
refresh URL, the OAuth client id and the version used in the `User-Agent` are
scraped from the bundled config object inside
`~/.local/share/claude/versions/<version>` (resolved through whatever `claude`
on your `PATH` points at). When the CLI updates, the helper follows it on the
next poll.

The scan is anchored and bounded, so all values come from the same config
object, and it takes ~0.3 s over a 270 MB binary. The result is cached in
`~/.cache/claude-usage-control/cli-meta.json`, keyed by the binary's path,
mtime and size, so it only re-runs after a CLI update.

Anything that cannot be found or validated falls back to the constants at the
top of `usage-helper.py`. `config_source` in the JSON output tells you which
path was taken: `cli` (freshly scanned), `cache` or `defaults`.

## Security notes

Read these before installing — the helper touches your credentials file.

- The helper **reads** `~/.claude/.credentials.json` and, when the access token
  has expired, **writes** a refreshed token back to it (atomically, under a
  file lock, preserving every other key). Before the first write it saves a
  backup to `~/.claude/.credentials.json.bak-claude-usage`.
- The refresh goes to `platform.claude.com/v1/oauth/token` with the public
  OAuth client id of the claude CLI. No other host is contacted.
- URLs scraped from the CLI binary are only used if they are `https` on
  `anthropic.com`, `claude.com` or `claude.ai`; anything else is discarded in
  favour of the built-in defaults. The client id is only taken together with a
  token URL that passed this check, since the two are posted alongside your
  refresh token.
- Tokens are never printed, logged or copied anywhere else.
- The lock only serializes concurrent runs of this helper. The claude CLI
  rewrites the credentials file independently, so the helper re-reads it under
  the lock and skips the refresh if the CLI got there first.

## Debugging

```bash
# Fetch the data by hand (expect a single JSON line):
python3 "gnome-extension/claude-usage@claude-usage-control/usage-helper.py"

# Ignore the installed CLI and use the built-in endpoint constants:
CU_NO_CLI_DISCOVERY=1 python3 "gnome-extension/claude-usage@claude-usage-control/usage-helper.py"

# Read the config from a specific claude binary:
CU_CLAUDE_BIN=/path/to/claude python3 "gnome-extension/claude-usage@claude-usage-control/usage-helper.py"

# Force a re-scan of the CLI:
rm ~/.cache/claude-usage-control/cli-meta.json

# Extension logs:
journalctl --user -f /usr/bin/gnome-shell | grep -i claude

# Override the session percent to test colors and notifications
# (remove the file to go back to real data):
echo 92 > ~/.cache/claude-usage-control/fake_percent
rm ~/.cache/claude-usage-control/fake_percent
```

Which notification thresholds have already fired is stored in
`~/.cache/claude-usage-control/state.json`.

## License

MIT — see [LICENSE](LICENSE).
