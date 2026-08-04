#!/usr/bin/env gjs
/* Unit tests for the formatters and the two provider parsers.
 *
 * Run:  tests/run.sh
 *
 * The indicator itself needs a live GNOME Shell (St, PanelMenu), so it is
 * out of reach here; everything with actual logic — window selection,
 * staleness, expiry, the two JSON dialects — lives in lib/format.js and the
 * providers, and that is what this covers.
 */
'use strict';

const GLib = imports.gi.GLib;

// GNOME Shell installs String.prototype.format for its own code; plain gjs
// does not, so the modules under test would fail without this.
String.prototype.format = imports.format.format;

const Format = imports.lib.format;
const Claude = imports.lib.claude.provider;
const Codex = imports.lib.codex.provider;

let failures = 0;
let checks = 0;

function check(name, actual, expected) {
    checks++;
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a === e) {
        print('  ok   %s'.format(name));
    } else {
        failures++;
        print('  FAIL %s\n         expected %s\n         actual   %s'.format(name, e, a));
    }
}

function checkMatch(name, actual, needle) {
    checks++;
    if (typeof actual === 'string' && actual.indexOf(needle) !== -1) {
        print('  ok   %s'.format(name));
    } else {
        failures++;
        print('  FAIL %s\n         expected to contain %s\n         actual   %s'.format(
            name, JSON.stringify(needle), JSON.stringify(actual)));
    }
}

const NOW = GLib.get_real_time() / 1000000;

print('formatWindow');
check('5-hour window', Format.formatWindow(300), '5 h');
check('weekly window', Format.formatWindow(10080), 'Week');
check('whole days', Format.formatWindow(1440), '1 d');
check('whole hours', Format.formatWindow(120), '2 h');
check('odd length falls back to minutes', Format.formatWindow(90), '90 min');

print('formatRemaining');
check('an hour out', Format.formatRemaining(NOW + 3600), '1:00');
check('four minutes out', Format.formatRemaining(NOW + 4 * 60), '0:04');
check('a full week reads in days', Format.formatRemaining(NOW + 7 * 86400), '7d');
check('days carry the odd hours', Format.formatRemaining(NOW + 6 * 86400 + 3600), '6d 1h');
check('already past clamps to zero', Format.formatRemaining(NOW - 500), '0:00');
check('missing timestamp', Format.formatRemaining(0), '?');

print('formatAge');
check('under 90s', Format.formatAge(30), 'just now');
check('minutes', Format.formatAge(600), '10 min ago');
check('hours', Format.formatAge(7200), '2 h ago');
check('days', Format.formatAge(2 * 86400), '2 d ago');

print('isoToUnix');
check('valid ISO', Format.isoToUnix('2026-08-11T11:23:29Z'), 1786447409);
check('missing', Format.isoToUnix(null), 0);
check('garbage', Format.isoToUnix('not a date'), 0);

print('Codex provider — live app-server payload (the real shape observed)');
{
    const model = Codex.parse({
        ok: true, source: 'app-server', age_seconds: 0,
        windows: [{ minutes: 10080, percent: 2.0, resets_at: Math.round(NOW + 6 * 86400) }],
        plan: 'plus', credits: { balance: '0', unlimited: false, has_credits: false },
        limit_reached: null,
    });
    check('percent from the only window', model.percent, 2.0);
    check('fresh data is not stale', model.stale, false);
    check('no second window, no suffix', model.suffix, null);
    checkMatch('window row', model.rows[0], 'Week: 2% used');
    check('credits row', model.rows[1], 'Credits: 0');
    check('plan row', model.rows[2], 'Plan: plus');
    check('no staleness note', model.note, null);
}

print('Codex provider — two windows: the bar tracks the shorter one');
{
    const model = Codex.parse({
        ok: true, source: 'app-server', age_seconds: 0,
        windows: [
            { minutes: 300, percent: 20, resets_at: Math.round(NOW + 3600) },
            { minutes: 10080, percent: 85, resets_at: Math.round(NOW + 6 * 86400) },
        ],
        limit_reached: null,
    });
    check('bar shows the 5-hour window', model.percent, 20);
    check('the weekly window goes to the suffix', model.suffix, ' · Week 85%');
    check('both windows listed', model.rows.length, 2);
    checkMatch('shorter window first', model.rows[0], '5 h: 20% used');
}

print('Codex provider — stale snapshot from the session journal');
{
    const model = Codex.parse({
        ok: true, source: 'rollout', age_seconds: 3681,
        windows: [{ minutes: 10080, percent: 1.0, resets_at: Math.round(NOW + 6 * 86400) }],
        limit_reached: null,
    });
    check('marked stale', model.stale, true);
    check('percent still shown', model.percent, 1.0);
    checkMatch('note names the source and the age', model.note, 'from session journal, 1 h ago');
}

print('Codex provider — stale snapshot whose window already reset');
{
    const model = Codex.parse({
        ok: true, source: 'rollout', age_seconds: 400000,
        windows: [{ minutes: 10080, percent: 64, resets_at: Math.round(NOW - 3600) }],
        limit_reached: null,
    });
    check('percent withheld rather than shown as stale truth', model.percent, null);
    checkMatch('menu explains the blank', model.rows[0], 'window has reset');
    check('the stale number is gone from the menu too, not just the bar',
        model.rows[0].indexOf('64') === -1, true);
    check('no suffix while the number is untrusted', model.suffix, null);
}

print('Codex provider — expiry is decided per window, not once for all');
{
    // shorter window still inside its period, longer one long past it
    const model = Codex.parse({
        ok: true, source: 'rollout', age_seconds: 400000,
        windows: [
            { minutes: 300, percent: 20, resets_at: Math.round(NOW + 1800) },
            { minutes: 10080, percent: 85, resets_at: Math.round(NOW - 3600) },
        ],
        limit_reached: null,
    });
    check('the live window still drives the bar', model.percent, 20);
    checkMatch('and keeps its row', model.rows[0], '5 h: 20% used');
    checkMatch('the expired one is blanked', model.rows[1], 'window has reset');
    check('and never reaches the suffix', model.suffix, null);
}
{
    // the reverse: the bar's own window expired but the weekly one has not
    const model = Codex.parse({
        ok: true, source: 'rollout', age_seconds: 400000,
        windows: [
            { minutes: 300, percent: 20, resets_at: Math.round(NOW - 60) },
            { minutes: 10080, percent: 85, resets_at: Math.round(NOW + 86400) },
        ],
        limit_reached: null,
    });
    check('bar blanked', model.percent, null);
    checkMatch('expired bar window blanked in the menu', model.rows[0], 'window has reset');
    checkMatch('the still-valid window keeps its number', model.rows[1], 'Week: 85% used');
}

print('Codex provider — a fresh reading is never treated as expired');
{
    // same already-past reset time, but straight from the app-server
    const model = Codex.parse({
        ok: true, source: 'app-server', age_seconds: 0,
        windows: [{ minutes: 10080, percent: 64, resets_at: Math.round(NOW - 3600) }],
        limit_reached: null,
    });
    check('live data is trusted as-is', model.percent, 64);
    check('not stale', model.stale, false);
}

print('Codex provider — degenerate input');
check('no windows at all', Codex.parse({ ok: true, source: 'app-server', windows: [] }), null);
check('windows missing entirely', Codex.parse({ ok: true, source: 'app-server' }), null);

print('Claude provider');
{
    const model = Claude.parse({
        ok: true, percent: 43, resets_at: '2026-08-04T18:00:00Z',
        seven_day_percent: 12, seven_day_resets_at: '2026-08-09T18:00:00Z',
        model_name: 'Fable', model_percent: 89, model_resets_at: '2026-08-09T18:00:00Z',
    });
    check('session percent drives the bar', model.percent, 43);
    check('never stale — the endpoint is polled live', model.stale, false);
    check('model quota in the suffix', model.suffix, ' · Fable 89%');
    check('three rows', model.rows.length, 3);
    checkMatch('session row', model.rows[0], 'Session (5 h): 43% used');
    checkMatch('week row', model.rows[1], 'Week: 12% used');
    checkMatch('model row', model.rows[2], 'Fable: 89% used');
}
{
    const model = Claude.parse({ ok: true, percent: 43, resets_at: '2026-08-04T18:00:00Z' });
    check('session-only payload has one row', model.rows.length, 1);
    check('and no suffix', model.suffix, null);
}
check('missing percent is rejected', Claude.parse({ ok: true }), null);

print('');
print('%d checks, %d failures'.format(checks, failures));
if (failures > 0)
    imports.system.exit(1);
