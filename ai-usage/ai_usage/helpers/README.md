# Vendor helpers

One script per CLI, each talking to that vendor's own source: Claude to its usage
endpoint (refreshing the CLI's OAuth token when it has expired), Codex to
`codex app-server` and, failing that, to the local rollout journal.

They are deliberately unchanged by the move out of the GNOME extension. Token
refresh, atomic credential writes and the Codex fallback chain are the parts of
this component with real consequences if they regress, so the move relocated them
rather than rewriting them. What did move is the *normalisation* of their replies:
that now lives in `ai_usage/providers/`, in Python, instead of being duplicated in
the extension's JavaScript and again in the Shell's GDScript.

Each script prints one JSON object on stdout: either `{"ok": true, …}` in its own
vendor-shaped form, or `{"ok": false, "error": "<code>"}`.
