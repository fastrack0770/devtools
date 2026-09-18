"""Shared AI usage runtime: one contract, one cache, two renderers.

The GNOME extension and the Godot Shell both read `ai-usage` output rather than
each other's internals; see the godot-mvp change `add-contextual-ai-usage-hud`
(design.md D1, D2) for why this lives outside the extension directory.
"""
