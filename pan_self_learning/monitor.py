# -*- coding: utf-8 -*-
"""Module drift and a heartbeat for an outside monitor (Uptime Kuma).

Every five minutes the cron in `models/pan_self_learning_monitor.py` asks
two things:

* **Drift**: is any installed module's code on disk at another version than
  the database it runs on? That happens when a host pulls new code without
  running the upgrade, and it breaks every screen that touches a new field
  (UndefinedColumn). Found drift is logged as one ERROR, so the
  server-errors handler (`server_errors.py`) reports it to PostHog error
  tracking under one stable issue.
* **Heartbeat**: when the system parameter
  `pan_self_learning.monitor_push_url` holds an Uptime Kuma push URL, the
  cron calls it with `status=up` (no drift) or `status=down` (drift), and a
  short message. Kuma raises the alarm on `down`, and also when the push
  stops coming: Odoo or its crons are down.

What leaves Odoo: module technical names and version strings. Nothing about
users or records.

This file has no Odoo imports, so its logic is tested without a database.
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PUSH_PARAM = 'pan_self_learning.monitor_push_url'
TIMEOUT = 10
MAX_MSG = 250


def find_drift(modules):
    """Installed modules whose code and database disagree.

    `modules` is an iterable of `(name, db_version, code_version)`, with
    `db_version` what the database was last upgraded to and `code_version`
    what the manifest on disk says now. A module whose code is gone from
    disk (`code_version` empty) counts too: Odoo cannot load it either.

    Returns `[(name, db_version, code_version)]`, sorted by name.
    """
    drift = []
    for name, db_version, code_version in modules:
        if (db_version or '') != (code_version or ''):
            drift.append((name, db_version or '', code_version or ''))
    return sorted(drift)


def describe(drift):
    """One short line for the monitor: `ok`, or the modules out of sync."""
    if not drift:
        return 'ok'
    parts = ['%s %s->%s' % (name, db or '?', code or 'missing')
             for name, db, code in drift]
    text = 'drift: ' + ', '.join(parts)
    if len(text) > MAX_MSG:
        text = text[:MAX_MSG - 3] + '...'
    return text


def push_url(base, drift):
    """The Kuma push URL with status and message, keeping any query the
    configured URL already has (Kuma's own default is `?status=up&msg=OK&ping=`)."""
    scheme, netloc, path, query, fragment = urlsplit(base)
    params = {k: v for k, v in parse_qsl(query) if k not in ('status', 'msg', 'ping')}
    params['status'] = 'down' if drift else 'up'
    params['msg'] = describe(drift)
    return urlunsplit((scheme, netloc, path, urlencode(params), fragment))


def valid_push_url(base):
    """Only an http(s) URL with a host: a typo in a system parameter must
    not turn into a request to somewhere unexpected."""
    try:
        parts = urlsplit(base or '')
    except ValueError:
        return False
    return parts.scheme in ('http', 'https') and bool(parts.netloc)
