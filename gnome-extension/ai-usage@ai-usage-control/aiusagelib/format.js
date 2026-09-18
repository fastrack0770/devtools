/* Timestamp and window formatting shared by the indicator and the providers.
 *
 * Kept free of St/Shell imports on purpose: these are the only parts of the
 * extension with interesting logic, and this way they can be exercised
 * outside a running GNOME session (see tests/format-test.js).
 */
'use strict';

const { GLib } = imports.gi;

function now() {
    return GLib.get_real_time() / 1000000;
}

/* Unix seconds of an ISO-8601 timestamp, or 0 if missing/unparseable. */
var isoToUnix = function (isoString) {
    if (!isoString)
        return 0;
    const dt = GLib.DateTime.new_from_iso8601(isoString, null);
    return dt ? dt.to_unix() : 0;
};

/* Wall-clock of a reset: "14:20" today, "11.08 14:20" further out. */
var formatReset = function (unixSeconds) {
    if (!unixSeconds)
        return '?';
    const local = GLib.DateTime.new_from_unix_local(unixSeconds);
    if (!local)
        return '?';
    if (unixSeconds - now() > 24 * 3600)
        return local.format('%d.%m %H:%M');
    return local.format('%H:%M');
};

/* Time left until a reset. Under a day "H:MM" — "5:00", "0:04"; beyond it
 * "6d 21h", because a weekly window rendered as "167:23" reads as noise. */
var formatRemaining = function (unixSeconds) {
    if (!unixSeconds)
        return '?';
    let mins = Math.ceil((unixSeconds - now()) / 60);
    if (mins < 0)
        mins = 0;
    if (mins >= 24 * 60) {
        const days = Math.floor(mins / (24 * 60));
        const hours = Math.floor((mins % (24 * 60)) / 60);
        return hours ? '%dd %dh'.format(days, hours) : '%dd'.format(days);
    }
    return '%d:%02d'.format(Math.floor(mins / 60), mins % 60);
};

/* "5 h" / "Week" / "90 min" — a window named by its length, since the
 * providers do not agree on which windows exist. */
var formatWindow = function (minutes) {
    if (minutes === 300)
        return '5 h';
    if (minutes === 10080)
        return 'Week';
    if (minutes % (24 * 60) === 0)
        return '%d d'.format(minutes / (24 * 60));
    if (minutes % 60 === 0)
        return '%d h'.format(minutes / 60);
    return '%d min'.format(minutes);
};

/* How old a cached snapshot is, in words. */
var formatAge = function (seconds) {
    if (seconds < 90)
        return 'just now';
    const mins = Math.round(seconds / 60);
    if (mins < 60)
        return '%d min ago'.format(mins);
    const hours = Math.round(mins / 60);
    if (hours < 24)
        return '%d h ago'.format(hours);
    return '%d d ago'.format(Math.round(hours / 24));
};
