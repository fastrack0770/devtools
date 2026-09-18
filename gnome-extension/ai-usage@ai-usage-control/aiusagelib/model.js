/* The shared usage document turned into what the panel draws.
 *
 * Version 1 of the document is provider-neutral (see the godot-mvp change
 * `add-contextual-ai-usage-hud`, design.md D2), so there is one renderer here
 * rather than one per CLI: Claude and Codex differ in which windows they
 * report, not in how a window is drawn. The Godot Shell formats the same
 * document its own way; nothing about this file is shared with it but the
 * contract.
 *
 * Kept free of St/Shell imports, like format.js, so tests/run.js can exercise
 * it outside a running GNOME session.
 */
'use strict';

const Format = imports.aiusagelib.format;

var SCHEMA_VERSION = 1;

/* The helper names its own second source; the menu says it in words. */
const SOURCE_LABELS = {
    'rollout': 'session journal',
};

function sourceLabel(source) {
    return SOURCE_LABELS[source] || source || 'cache';
}

function windowRow(entry) {
    if (entry.used_percent === null) {
        return '%s: — window has reset, waiting for fresh data'.format(entry.label);
    }
    return '%s: %d%% used, %s left (resets at %s)'.format(
        entry.label,
        Math.round(entry.used_percent),
        entry.resets_at ? Format.formatRemaining(entry.resets_at) : '?',
        entry.resets_at ? Format.formatReset(entry.resets_at) : '?');
}

/* The render model the indicator has always drawn:
 *   { percent, resetsAt, stale, suffix, rows, note }
 * `percent` null means "no trustworthy number" and renders as an em dash.
 * Returns null when the entry carries nothing to draw. */
var render = function (entry) {
    if (!entry || !Array.isArray(entry.windows) || !entry.windows.length)
        return null;

    const windows = entry.windows;
    const primary = windows[0];
    const last = windows[windows.length - 1];
    const stale = entry.state === 'stale';

    /* The extra window is a courtesy line: it is dropped whenever either it or
     * the window the bar tracks has lost its number, so the panel never pairs a
     * dash with a confident percentage. */
    const suffix = (windows.length > 1 && primary.used_percent !== null && last.used_percent !== null)
        ? ' · %s %d%%'.format(last.label, Math.round(last.used_percent))
        : null;

    const rows = windows.map(windowRow);
    for (const detail of entry.details || [])
        rows.push(detail);

    return {
        percent: primary.used_percent,
        resetsAt: primary.resets_at || 0,
        stale,
        suffix,
        rows,
        note: stale
            ? 'from %s, %s'.format(sourceLabel(entry.source), Format.formatAge(entry.age_seconds || 0))
            : null,
    };
};

/* A provider entry is worth an indicator unless the CLI is simply not set up
 * here — an empty indicator for a CLI the user does not use is noise. */
var isPresent = function (entry) {
    return !!entry && entry.state !== 'unavailable';
};

/* Reject a document from a version this extension does not know rather than
 * render fields whose meaning may have changed. */
var providersOf = function (document) {
    if (!document || document.schema_version !== SCHEMA_VERSION)
        return null;
    if (!document.providers || typeof document.providers !== 'object')
        return null;
    return document.providers;
};
