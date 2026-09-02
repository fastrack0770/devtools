#!/usr/bin/env gjs
/* Unit tests for the formatters, the two provider parsers and the parts of
 * the indicator that do not need a live shell.
 *
 * Run:  tests/run.sh
 *
 * St and PanelMenu exist only inside GNOME Shell, so the indicator is
 * loaded through tests/fakeShell.js, which hands it stand-ins. That is what
 * lets the notification code be checked against both shell generations from
 * one machine — the half of the port that no single GNOME version can
 * exercise on its own.
 */
'use strict';

const GLib = imports.gi.GLib;

// GNOME Shell installs String.prototype.format for its own code; plain gjs
// does not, so the modules under test would fail without this.
String.prototype.format = imports.format.format;

const Format = imports.aiusagelib.format;
const Errors = imports.aiusagelib.errors;
const Claude = imports.aiusagelib.claude.provider;
const Codex = imports.aiusagelib.codex.provider;

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

print('errors');
/* Both endpoints rate-limit; matching only the usage code left a token-endpoint
 * 429 with no message and no backoff. */
check('usage 429 is a rate limit', Errors.isRateLimit('usage_http_429'), true);
check('refresh 429 is a rate limit too', Errors.isRateLimit('refresh_http_429'), true);
check('a 500 is not', Errors.isRateLimit('usage_http_500'), false);
check('nor is a non-code', Errors.isRateLimit(undefined), false);

/* The raw code must never be what the panel shows for a rate limit. */
checkMatch('usage 429 reads as a rate limit', Errors.errorMessage('usage_http_429'), 'Rate limited');
checkMatch('refresh 429 too', Errors.errorMessage('refresh_http_429'), 'Rate limited');
check('no leaked code in the 429 message',
    Errors.errorMessage('usage_http_429').indexOf('429'), -1);
check('known code maps to its message', Errors.errorMessage('network'),
    'No connection to the usage endpoint');
check('unknown code falls back to itself', Errors.errorMessage('weird'), 'weird');

check('Retry-After wins', Errors.backoffSeconds(900), 900);
check('no header falls back', Errors.backoffSeconds(null), Errors.DEFAULT_BACKOFF_SECONDS);
check('zero falls back', Errors.backoffSeconds(0), Errors.DEFAULT_BACKOFF_SECONDS);
check('an absurd header is capped', Errors.backoffSeconds(999999), Errors.MAX_BACKOFF_SECONDS);

/* --- the indicator, against both shell generations --------------------- */

const EXT_DIR = ARGV[0];
const FakeShell = imports.tests.fakeShell;

const TEST_PROVIDER = { id: 'test', title: 'Test', helper: 'unused.py' };

const ENV = FakeShell.makeShell();
const UsageIndicator = FakeShell.loadIndicatorFactory(EXT_DIR, ENV.shell);

/* A fresh indicator with the tray pointed at one shell generation. */
function newIndicator(generation) {
    ENV.use(generation);
    return { indicator: new UsageIndicator(TEST_PROVIDER, '/nonexistent'), log: ENV.log };
}

const built = newIndicator('modern');
check('the panel button is titled after its provider',
    built.indicator.nameText, 'Test Usage');

/* The render path: a known percentage, an unknown one, and the dimming that
 * separates a live reading from a snapshot. */
const r = built.indicator;
r._model = { percent: 42.4, resetsAt: 0, stale: false, suffix: null, rows: ['a', 'b'], note: null };
r._render();
check('the bar reports the used share', r._infoLabel.text, '42% · ?');
check('every row reaches the menu', r._rowItems.length, 2);
check('a live reading is not dimmed', r._box.opacity, 255);

r._model.suffix = ' · x 9%';
r._render();
check('a suffix is appended', r._infoLabel.text, '42% · ? · x 9%');

r._model.percent = null;
r._render();
check('an unknown share renders as a dash', r._infoLabel.text, '—');

r._model.percent = 95;
r._model.stale = true;
r._render();
check('a stale reading is dimmed', r._box.opacity, 110);
check('90% and over turns the bar red', r._fill.style_class, 'cu-fill cu-fill-red');

/* _notify is the only place where the two shell generations diverge, so it
 * is checked call for call on each of them. */
const legacy = newIndicator('legacy');
legacy.indicator._notify('Test: 90%', 'body', true);
check('GNOME 42 gets positional arguments and showNotification', legacy.log, [
    ['source', { title: 'Test', iconName: 'utilities-system-monitor-symbolic' }],
    ['trayAdd', true],
    ['notification', { title: 'Test: 90%', body: 'body', hasSource: true }],
    ['setTransient', false],
    ['setUrgency', 3],
    ['showNotification', 'Test: 90%'],
]);

const modern = newIndicator('modern');
modern.indicator._notify('Test: 90%', 'body', true);
check('GNOME 46+ gets parameter objects and addNotification', modern.log, [
    ['source', { title: 'Test', iconName: 'utilities-system-monitor-symbolic' }],
    ['trayAdd', true],
    ['notification', {
        title: 'Test: 90%', body: 'body', isTransient: false, urgency: 3, hasSource: true,
    }],
    ['addNotification', 'Test: 90%'],
]);

const calmLegacy = newIndicator('legacy');
calmLegacy.indicator._notify('Test: 20%', 'body', false);
check('a non-critical notification leaves the urgency alone on GNOME 42',
    calmLegacy.log.filter(e => e[0] === 'setUrgency').length, 0);

const calmModern = newIndicator('modern');
calmModern.indicator._notify('Test: 20%', 'body', false);
check('a non-critical notification is NORMAL on GNOME 46+',
    calmModern.log.filter(e => e[0] === 'notification')[0][1].urgency, 0);

print('');
print('%d checks, %d failures'.format(checks, failures));
if (failures > 0)
    imports.system.exit(1);
