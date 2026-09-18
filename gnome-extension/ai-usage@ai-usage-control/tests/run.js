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

/* --- the shared document, rendered ------------------------------------- */
/* The provider parsers moved into the Python runtime, so what is checked here
 * is the one renderer both entry points use: schema-v1 entries in, the panel's
 * render model out. Fixtures mirror tests/fixtures of the ai-usage component. */

const Model = imports.aiusagelib.model;

function win(id, kind, label, minutes, percent, resetsAt) {
    return { id, kind, label, minutes, used_percent: percent, resets_at: resetsAt };
}

function entry(props) {
    return Object.assign({
        state: 'ok', source: 'app-server', fetched_at: Math.round(NOW),
        next_retry_at: null, error: null, age_seconds: 0, details: [], windows: [],
    }, props);
}

print('document envelope');
check('version 1 is accepted',
    !!Model.providersOf({ schema_version: 1, providers: { claude: {} } }), true);
check('another version is refused',
    Model.providersOf({ schema_version: 2, providers: {} }), null);
check('a document without providers is refused',
    Model.providersOf({ schema_version: 1 }), null);
check('an unavailable CLI gets no indicator',
    Model.isPresent(entry({ state: 'unavailable' })), false);
check('an errored CLI keeps its indicator',
    Model.isPresent(entry({ state: 'error' })), true);

print('render — Codex, one weekly window (the real shape observed)');
{
    const model = Model.render(entry({
        windows: [win('primary', 'weekly', 'Week', 10080, 2.0, Math.round(NOW + 6 * 86400))],
        details: ['Credits: 0', 'Plan: plus'],
    }));
    check('percent from the only window', model.percent, 2.0);
    check('fresh data is not stale', model.stale, false);
    check('no second window, no suffix', model.suffix, null);
    checkMatch('window row', model.rows[0], 'Week: 2% used');
    check('credits row', model.rows[1], 'Credits: 0');
    check('plan row', model.rows[2], 'Plan: plus');
    check('no staleness note', model.note, null);
}

print('render — two windows: the bar tracks the first');
{
    const model = Model.render(entry({
        windows: [
            win('primary', 'session', '5 h', 300, 20, Math.round(NOW + 3600)),
            win('secondary', 'weekly', 'Week', 10080, 85, Math.round(NOW + 6 * 86400)),
        ],
    }));
    check('bar shows the 5-hour window', model.percent, 20);
    check('the weekly window goes to the suffix', model.suffix, ' · Week 85%');
    check('both windows listed', model.rows.length, 2);
    checkMatch('shorter window first', model.rows[0], '5 h: 20% used');
}

print('render — a stale snapshot from the session journal');
{
    const model = Model.render(entry({
        state: 'stale', source: 'rollout', age_seconds: 3681,
        windows: [win('primary', 'weekly', 'Week', 10080, 1.0, Math.round(NOW + 6 * 86400))],
    }));
    check('marked stale', model.stale, true);
    check('percent still shown', model.percent, 1.0);
    checkMatch('note names the source and the age', model.note, 'from session journal, 1 h ago');
}

print('render — a window whose percentage the runtime withheld');
{
    const model = Model.render(entry({
        state: 'stale', source: 'rollout', age_seconds: 400000,
        windows: [win('primary', 'weekly', 'Week', 10080, null, Math.round(NOW - 3600))],
    }));
    check('no invented percentage', model.percent, null);
    checkMatch('menu explains the blank', model.rows[0], 'window has reset');
    check('no suffix while the number is untrusted', model.suffix, null);
}

print('render — a withheld percentage never pairs with a confident suffix');
{
    const live = Model.render(entry({
        state: 'stale', source: 'rollout', age_seconds: 400000,
        windows: [
            win('primary', 'session', '5 h', 300, 20, Math.round(NOW + 1800)),
            win('secondary', 'weekly', 'Week', 10080, null, Math.round(NOW - 3600)),
        ],
    }));
    check('the live window still drives the bar', live.percent, 20);
    checkMatch('and keeps its row', live.rows[0], '5 h: 20% used');
    checkMatch('the withheld one is blanked', live.rows[1], 'window has reset');
    check('and never reaches the suffix', live.suffix, null);

    const blanked = Model.render(entry({
        state: 'stale', source: 'rollout', age_seconds: 400000,
        windows: [
            win('primary', 'session', '5 h', 300, null, Math.round(NOW - 60)),
            win('secondary', 'weekly', 'Week', 10080, 85, Math.round(NOW + 86400)),
        ],
    }));
    check('bar blanked', blanked.percent, null);
    checkMatch('blanked bar window explained in the menu', blanked.rows[0], 'window has reset');
    checkMatch('the still-valid window keeps its number', blanked.rows[1], 'Week: 85% used');
    check('no suffix beside a blank bar', blanked.suffix, null);
}

print('render — degenerate input');
check('no windows at all', Model.render(entry({ windows: [] })), null);
check('windows missing entirely', Model.render(entry({ windows: undefined })), null);
check('no entry at all', Model.render(undefined), null);

print('render — Claude, session plus weekly plus model quota');
{
    const model = Model.render(entry({
        source: 'usage-endpoint',
        windows: [
            win('session', 'session', 'Session (5 h)', 300, 43, Math.round(NOW + 3600)),
            win('weekly_all', 'weekly', 'Week', 10080, 12, Math.round(NOW + 5 * 86400)),
            win('model:fable', 'model', 'Fable', 10080, 89, Math.round(NOW + 5 * 86400)),
        ],
    }));
    check('session percent drives the bar', model.percent, 43);
    check('never stale — the endpoint is polled live', model.stale, false);
    check('model quota in the suffix', model.suffix, ' · Fable 89%');
    check('three rows', model.rows.length, 3);
    checkMatch('session row', model.rows[0], 'Session (5 h): 43% used');
    checkMatch('week row', model.rows[1], 'Week: 12% used');
    checkMatch('model row', model.rows[2], 'Fable: 89% used');
}
{
    const model = Model.render(entry({
        source: 'usage-endpoint',
        windows: [win('session', 'session', 'Session (5 h)', 300, 43, Math.round(NOW + 3600))],
    }));
    check('session-only payload has one row', model.rows.length, 1);
    check('and no suffix', model.suffix, null);
}

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

/* --- the controller: which reply is allowed to reach the panel ---------- */

function documentWith(providers) {
    return { schema_version: 1, generated_at: Math.round(NOW), providers };
}

function okEntry(percent) {
    return entry({
        source: 'usage-endpoint',
        windows: [win('session', 'session', 'Session (5 h)', 300, percent, Math.round(NOW + 3600))],
    });
}

function newController() {
    const created = [];
    const usage = FakeShell.makeFakeUsage();
    const Controller = FakeShell.loadControllerFactory(
        EXT_DIR, FakeShell.makeFakeIndicator(created), usage);
    return { controller: new Controller(ENV.shell, EXT_DIR), usage, created };
}

print('controller — one fetch answers for every provider');
{
    const c = newController();
    c.controller.refresh(false);
    check('one subprocess, not one per provider', c.usage.calls.length, 1);
    c.usage.answer(0, documentWith({ claude: okEntry(40), codex: okEntry(50) }));
    check('an indicator per present provider', c.created.length, 2);
    check('claude got its own entry', c.created[0].entries[0].windows[0].used_percent, 40);
    check('codex got its own entry', c.created[1].entries[0].windows[0].used_percent, 50);
}

print('controller — a late reply never overwrites a fresher one');
{
    const c = newController();
    c.controller.refresh(false);          // slow poll
    c.controller.refresh(true);           // quick "Refresh now"
    check('both requests were issued', c.usage.calls.length, 2);
    c.usage.answer(1, documentWith({ claude: okEntry(90) }));   // the newer one lands first
    c.usage.answer(0, documentWith({ claude: okEntry(10) }));   // the older one straggles in
    const seen = c.created[0].entries.map(e => e.windows[0].used_percent);
    check('the stale answer is dropped', seen, [90]);
}

print('controller — a late failure never marks fresh numbers stale');
{
    const c = newController();
    c.controller.refresh(false);
    c.controller.refresh(true);
    c.usage.answer(1, documentWith({ claude: okEntry(90) }));
    c.usage.answer(0, null, 'network');
    check('no error reached the panel', c.created[0].errors, []);
}

print('controller — Refresh now asks the runtime to skip its freshness window');
{
    const c = newController();
    c.controller.refresh(false);
    check('ordinary polling uses the cache', c.usage.calls[0].force, false);
    c.usage.answer(0, documentWith({ claude: okEntry(40) }));
    c.created[0].onForceRefresh();
    check('the menu item forces a refresh', c.usage.calls[1].force, true);
}

print('controller — indicators follow which CLIs are set up');
{
    const c = newController();
    c.controller.refresh(false);
    c.usage.answer(0, documentWith({ claude: okEntry(40), codex: okEntry(50) }));
    check('both present', c.created.length, 2);

    c.controller.refresh(false);
    c.usage.answer(1, documentWith({
        claude: okEntry(41), codex: entry({ state: 'unavailable', windows: [] }),
    }));
    check('the logged-out CLI leaves no empty indicator', c.created[1].destroyed, true);
    check('the other one carries on', c.created[0].entries.length, 2);

    c.controller.refresh(false);
    c.usage.answer(2, documentWith({ claude: okEntry(42), codex: okEntry(55) }));
    check('and comes back when it is logged in again', c.created.length, 3);
}

print('controller — a runtime that cannot be run keeps the numbers on screen');
{
    const c = newController();
    c.controller.refresh(false);
    c.usage.answer(0, documentWith({ claude: okEntry(40) }));
    c.controller.refresh(false);
    c.usage.answer(1, null, 'helper');
    check('the indicator is kept, not destroyed', c.created[0].destroyed, false);
    check('and is told why', c.created[0].errors, ['helper']);
}

print('controller — a document from another version is refused');
{
    const c = newController();
    c.controller.refresh(false);
    c.usage.answer(0, okEntry(40));
    c.controller.refresh(false);
    c.usage.answer(1, { schema_version: 99, providers: { claude: okEntry(40) } });
    check('no indicator was built from an unknown version', c.created.length, 0);
}

/* --- the two entry points ----------------------------------------------- */
/* GNOME 42-44 reads extension.js with the legacy importer; GNOME 45-50 imports
 * extension-esm.js as an ES module. Neither can be loaded here — one needs
 * imports.ui.*, the other resource:/// URLs that exist only inside the shell —
 * so what is checked is that both reach the panel through the same shared
 * pieces, and that neither has grown a second owner of notifications. */

function sourceOf(name) {
    const [ok, bytes] = GLib.file_get_contents(GLib.build_filenamev([EXT_DIR, name]));
    if (!ok)
        throw new Error('cannot read %s'.format(name));
    return new TextDecoder().decode(bytes);
}

const LEGACY = sourceOf('extension.js');
const ESM = sourceOf('extension-esm.js');
const CORE = sourceOf('aiusagelib/core.js');
const USAGE = sourceOf('aiusagelib/usage.js');

print('entry points — both go through the same controller');
check('GNOME 42 entry point loads aiusagelib.core',
    LEGACY.indexOf('imports.aiusagelib.core') !== -1, true);
check('GNOME 45+ entry point loads aiusagelib.core',
    ESM.indexOf('imports.aiusagelib.core') !== -1, true);
check('GNOME 42 entry point builds the controller',
    LEGACY.indexOf('new Core.Controller') !== -1, true);
check('GNOME 45+ entry point builds the controller',
    ESM.indexOf('new Core.Controller') !== -1, true);
check('the legacy entry point is a script, not a module',
    LEGACY.indexOf('export default') === -1, true);
check('the modern entry point is a module',
    ESM.indexOf('export default') !== -1, true);

print('entry points — both read the shared runtime and nothing else');
check('the controller fetches through aiusagelib.usage',
    CORE.indexOf('imports.aiusagelib.usage') !== -1, true);
check('the runtime is reached at the stable installed path',
    USAGE.indexOf("'ai-usage-control'") !== -1, true);
check('and may be pointed elsewhere for development',
    USAGE.indexOf('AI_USAGE_BIN') !== -1, true);
[['GNOME 42', LEGACY], ['GNOME 45+', ESM], ['the controller', CORE]].forEach(pair => {
    check('%s no longer spawns a per-provider helper'.format(pair[0]),
        pair[1].indexOf('usage-helper.py') === -1, true);
});

print('entry points — notifications have exactly one owner');
/* The Godot Shell renders the same numbers and raises no notifications, so a
 * crossed threshold is announced once. Inside the extension the indicator is
 * that single owner (design.md D8). */
[['GNOME 42', LEGACY], ['GNOME 45+', ESM], ['the controller', CORE]].forEach(pair => {
    check('%s raises no notification of its own'.format(pair[0]),
        pair[1].indexOf('MessageTray.Notification') === -1, true);
});
check('the indicator is the one that does',
    sourceOf('aiusagelib/indicator.js').indexOf('MessageTray.Notification') !== -1, true);

/* --- the runtime bridge, actually loaded -------------------------------- */
/* Everything above reads aiusagelib/usage.js as text. That leaves the file
 * itself never executed, so a syntax error or a bad import in it would first
 * appear in a live session — which on Wayland means after a logout. Importing
 * it here costs nothing and closes that gap. */

const UsageModule = imports.aiusagelib.usage;

print('runtime bridge');
check('the module loads and exposes fetch',
    typeof UsageModule.fetch === 'function', true);
check('it points at the stable installed path by default',
    UsageModule.binary(), GLib.build_filenamev(
        [GLib.get_home_dir(), '.local', 'libexec', 'ai-usage-control', 'ai-usage']));
{
    const previous = GLib.getenv('AI_USAGE_BIN');
    GLib.setenv('AI_USAGE_BIN', '/tmp/ai-usage-under-test', true);
    check('AI_USAGE_BIN overrides it', UsageModule.binary(), '/tmp/ai-usage-under-test');
    check('and an absent runtime is reported, not assumed',
        UsageModule.isInstalled(), false);
    if (previous)
        GLib.setenv('AI_USAGE_BIN', previous, true);
    else
        GLib.unsetenv('AI_USAGE_BIN');
}

print('');
print('%d checks, %d failures'.format(checks, failures));
if (failures > 0)
    imports.system.exit(1);
