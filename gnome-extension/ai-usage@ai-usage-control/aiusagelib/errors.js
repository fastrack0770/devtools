/* Helper failure codes: what the panel shows for one, and which ones are
 * rate limits that must pause polling.
 *
 * Kept free of gi/St imports like lib/format.js, so tests/run.js can
 * exercise it outside a running GNOME session.
 */
'use strict';

var DEFAULT_BACKOFF_SECONDS = 300; // pause polling when the server names no wait
var MAX_BACKOFF_SECONDS = 3600; // ceiling on a server-supplied Retry-After

/* Helper error codes the user can actually act on. Anything absent falls
 * back to the raw code, which is still enough to grep the helpers for. */
const MESSAGES = {
    no_credentials: 'Not logged in',
    not_logged_in: 'Not logged in',
    no_refresh_token: 'Session expired — log in again',
    refresh_token_expired: 'Session expired — log in again',
    unauthorized: 'Session expired — log in again',
    network: 'No connection to the usage endpoint',
    helper: 'Helper failed to start',
    parse: 'Unexpected helper output',
    no_codex_cli: 'codex CLI not found',
    no_usage_data: 'No usage data yet — run codex once',
};

/* Both endpoints the claude helper talks to can rate-limit, and each reports
 * it under its own code — `usage_http_429` from the usage endpoint,
 * `refresh_http_429` from the token endpoint. Matching the usage one alone
 * left a token-endpoint 429 with no message and no backoff, so it kept
 * retrying every minute and printing its raw code; hence the shape match. */
var isRateLimit = function (reason) {
    return typeof reason === 'string' && reason.endsWith('_http_429');
};

/* The most common failure by far, and the only action is to wait — so it must
 * not be the one users have to look up. */
var errorMessage = function (reason) {
    if (isRateLimit(reason))
        return 'Rate limited — polling paused';
    return MESSAGES[reason] || reason;
};

/* How long to stop polling. Prefer the server's own Retry-After: a fixed
 * five-minute guess that undershoots it just earns the next 429. Capped, so
 * one absurd header cannot freeze the panel. */
var backoffSeconds = function (retryAfter) {
    return Number.isFinite(retryAfter) && retryAfter > 0
        ? Math.min(retryAfter, MAX_BACKOFF_SECONDS)
        : DEFAULT_BACKOFF_SECONDS;
};
