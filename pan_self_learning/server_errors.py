# -*- coding: utf-8 -*-
"""Server-side errors to PostHog error tracking, for a connected database.

A `logging.Handler` on the root logger takes every ERROR (tracebacks, a
failed cron, a mail that would not send) and hands it to one background
thread, which sends it to the PostHog project in this database's
entitlement as a `$exception` event. Nothing else of the log leaves.

**What an event carries**: the exception type, the stack (module, function,
file name and line number, no local values), the logger name, the Odoo and
module versions, and the database uuid as the `workspace` group the browser
events use. The message only when it is a format string with its values
kept apart (`_logger.error("Cron %s failed", name)` sends `Cron %s failed`):
the values are where record data lives, so they never go. The exception's
own text never goes either: `ValueError("bad email foo@bar")` arrives as
`ValueError`. Dropped on purpose: an error that type and stack alone do not
explain.

**When**: only while the database is connected (`pan.self.learning.link`),
the entitlement says `server_errors`, and the settings switch
`pan_self_learning.server_errors` is on. An error logged outside a database
(server start, the database manager) has no entitlement to ask and is
dropped.

**Never in the way**: `emit` only puts the record on a bounded queue; a
full queue drops it. The thread starts at the first error in a process,
and again in a prefork worker, which a fork leaves without it. It reads
each database's config through its own cursor and keeps it ten minutes (so
the switch takes up to ten minutes to bite), sends one event per error kind
per minute at most, and swallows its own failures. Its own logging stays below
ERROR, and records from the thread itself are ignored, so it cannot feed
itself.
"""
import logging
import os
import queue
import threading
import time
import traceback

import requests

_logger = logging.getLogger(__name__)

PARAM = 'pan_self_learning.server_errors'
CAPTURE_PATH = '/i/v0/e/'
TIMEOUT = 10
QUEUE_SIZE = 200
CONFIG_TTL = 600
ONCE_PER = 60
MAX_FRAMES = 30
MAX_TEXT = 200

# Loggers whose errors are about the sending itself: reporting them would
# loop through the network that just failed.
QUIET = ('urllib3', 'requests', __name__)


def message_template(record):
    """The format string, only when its values were kept apart: then it is
    code, not data. An f-string or a preformatted message is dropped."""
    if record.args and isinstance(record.msg, str):
        return record.msg[:MAX_TEXT]
    return ''


def frames(tb):
    """The stack as PostHog's raw Python frames, oldest first. Names and
    lines only: no locals, no source text."""
    result = []
    for frame, lineno in traceback.walk_tb(tb):
        module = frame.f_globals.get('__name__') or ''
        result.append({
            'platform': 'python',
            'module': module,
            'function': frame.f_code.co_name,
            'filename': '/'.join(frame.f_code.co_filename.split('/')[-3:]),
            'lineno': lineno,
            'in_app': module.startswith('odoo.addons.'),
        })
    return result[-MAX_FRAMES:]


def build_event(record, config):
    """The `$exception` event for one log record. Pure, apart from the
    clock PostHog's timestamp needs."""
    exc_type, _exc, tb = record.exc_info or (None, None, None)
    name = exc_type.__name__ if exc_type else 'LoggedError'
    stack = frames(tb) if tb else []
    template = message_template(record)
    exception = {
        'type': name,
        'value': template or name,
        'mechanism': {'type': 'logging', 'handled': True, 'synthetic': not exc_type},
    }
    if stack:
        exception['stacktrace'] = {'type': 'raw', 'frames': stack}
    return {
        'api_key': config['api_key'],
        'event': '$exception',
        'distinct_id': '%s#server' % config['db_uuid'],
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(record.created)),
        'properties': {
            '$exception_list': [exception],
            '$exception_level': record.levelname.lower(),
            '$process_person_profile': False,
            '$groups': {'workspace': config['db_uuid']},
            'logger': record.name,
            'odoo_version': config['odoo_version'],
            'module_version': config['module_version'],
        },
    }


def fingerprint(record):
    """What counts as the same error for the once-a-minute limit."""
    exc_type = record.exc_info[0] if record.exc_info else None
    tail = ''
    if record.exc_info and record.exc_info[2]:
        last = list(traceback.walk_tb(record.exc_info[2]))[-1]
        tail = '%s:%s' % (last[0].f_code.co_filename, last[1])
    return (record.name, exc_type.__name__ if exc_type else '', tail)


def read_config(dbname):
    """This database's answer, through a cursor of our own, or None when it
    may not report. Runs on the sender thread, never in a request."""
    from odoo import SUPERUSER_ID, api, release
    from odoo.modules.registry import Registry

    # Only a database this process already serves: asking for any other
    # would load its whole registry from a log line.
    if dbname not in Registry.registries:
        return None
    with Registry(dbname).cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        if 'pan.self.learning.link' not in env:
            return None
        icp = env['ir.config_parameter']
        if icp.get_param(PARAM, 'True') in ('False', '0', ''):
            return None
        if icp.get_param('pan_self_learning.enabled', 'True') in ('False', '0', ''):
            return None
        link = env['pan.self.learning.link'].current()
        if not link or not link.is_entitled() or not link.server_errors:
            return None
        return {
            'api_key': link.posthog_key,
            'api_host': link.posthog_host.rstrip('/'),
            'db_uuid': icp.get_param('database.uuid', '') or dbname,
            'odoo_version': release.version,
            'module_version': link._module_version(),
        }


class Sender(threading.Thread):
    """The one thread per process that talks to PostHog."""

    def __init__(self):
        super().__init__(name='pan_self_learning.server_errors', daemon=True)
        self.queue = queue.Queue(QUEUE_SIZE)
        self.configs = {}
        self.sent = {}

    def run(self):
        while True:
            dbname, record = self.queue.get()
            try:
                self.handle(dbname, record)
            except Exception:  # noqa: BLE001 - a report must never raise
                _logger.warning('Could not report a server error', exc_info=True)

    def handle(self, dbname, record):
        now = time.monotonic()
        key = (dbname,) + fingerprint(record)
        if now - self.sent.get(key, -ONCE_PER) < ONCE_PER:
            return
        config = self.config(dbname, now)
        if not config:
            return
        self.sent[key] = now
        if len(self.sent) > 1000:
            self.sent = {k: v for k, v in self.sent.items() if now - v < ONCE_PER}
        requests.post(config['api_host'] + CAPTURE_PATH,
                      json=build_event(record, config), timeout=TIMEOUT)

    def config(self, dbname, now):
        cached = self.configs.get(dbname)
        if cached and now - cached[0] < CONFIG_TTL:
            return cached[1]
        config = read_config(dbname)
        self.configs[dbname] = (now, config)
        return config


class Handler(logging.Handler):
    """Puts ERROR records on the sender's queue, and nothing else."""

    def __init__(self):
        super().__init__(logging.ERROR)
        self.sender = None
        self.pid = None
        # Not `self.lock`: that is logging.Handler's own, held around emit().
        self.starting = threading.Lock()

    def current_sender(self):
        """This process's thread. A fork copies the handler but not the
        thread, so a new pid gets a new one."""
        with self.starting:
            if self.sender is None or self.pid != os.getpid():
                self.sender = Sender()
                self.pid = os.getpid()
                self.sender.start()
            return self.sender

    def emit(self, record):
        thread = threading.current_thread()
        if record.name.startswith(QUIET) or isinstance(thread, Sender):
            return
        dbname = getattr(thread, 'dbname', None)
        if not dbname:
            return
        try:
            self.current_sender().queue.put_nowait((dbname, record))
        except queue.Full:
            pass


_installed = None


def install():
    """Add the handler once per process: Python imports the module once."""
    global _installed
    if _installed is None:
        _installed = Handler()
        logging.getLogger().addHandler(_installed)
    return _installed
