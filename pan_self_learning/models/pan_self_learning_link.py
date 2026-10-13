# -*- coding: utf-8 -*-
"""This database's link to a Pantalytics account, and the key it brings.

The module is dormant until somebody connects it. The admin presses
**Connect to Pantalytics** on the settings page; Odoo asks the Pantalytics
server for a pairing and opens its page in a new tab with the code already in
the link. The admin signs in there, checks that the page names this Odoo, and
approves; the button back lands on `/self_learning/pantalytics/return`, which
collects the key. Nobody types a code or copies a key. **Check approval** on
the settings page does the same collection by hand.

After that, one heartbeat a day: the database id and two version strings go
out, a signed entitlement comes back. The entitlement carries the PostHog
project key and host and whether sessions may be recorded. Those used to be
in this module's data files, which meant a plain install started reporting
before anybody had said yes. Now the yes is the pairing, and the project is
whatever Pantalytics hands out, so a switch there (Disconnect in the panel)
reaches this Odoo at its next heartbeat and the module goes quiet.

**Trust.** An entitlement is only stored after its Ed25519 signature checks
out against the public key this module ships and its `db_uuid` matches this
database, so a cached answer cannot be forged by editing a response or lifted
from another customer. The key is held in a field only `base.group_system`
can read. It is not encrypted at rest: it lets a database heartbeat as this
installation and receive a public PostHog key, which is the whole of what it
unlocks.

**There is one row**, created the first time somebody connects. `current()`
is the answer. The server side is `pantalytics/odoo-mcp-pro-admin`,
`mcp_server_odoo_admin/apps/self_learning.py`.
"""
import base64
import json
import logging
import os
from datetime import datetime, timezone

import requests

from odoo import _, api, fields, models, release
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

SERVER_URL = 'https://mcp.pantalytics.com'

# The verifying half of the key Pantalytics signs entitlements with: the same
# one Mail Pro pins (pantalytics/pan_mail_pro, models/pan_mail_license.py).
# Publishing it is safe: it can only check a signature, never make one.
PUBLIC_KEY = 'ZWLGGpks2iRjFguGsGlhpDl64ekFiDCM7L/O/g3xK/8='

# Deployment-level overrides for a staging server. Never a settings field: a
# wrong value there is a support ticket nobody can diagnose from the screen.
ENV_URL = 'PAN_SELF_LEARNING_SERVER_URL'
ENV_PUBLIC_KEY = 'PAN_SELF_LEARNING_PUBLIC_KEY'

LINK_PREFIX = '/api/v1/self-learning/link'
HEARTBEAT_PATH = '/api/v1/self-learning/heartbeat'
TIMEOUT = 15

STATUS_SELECTION = [
    ('not_connected', 'Not connected'),
    ('pending', 'Waiting for approval'),
    ('active', 'Connected'),
    ('revoked', 'Disconnected at Pantalytics'),
    ('invalid', 'Key refused'),
]


def _server_url():
    return (os.environ.get(ENV_URL) or SERVER_URL).rstrip('/')


def _public_key():
    return os.environ.get(ENV_PUBLIC_KEY) or PUBLIC_KEY


def canonical_json(payload):
    """The bytes the server signed. Must match the platform's `apps/signing.py` exactly."""
    return json.dumps(
        payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    ).encode('utf-8')


def verify_signature(payload, signature_b64, public_key_b64):
    """True only for a payload our server signed. Any doubt is a no."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if not public_key_b64 or not signature_b64:
        return False
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        key.verify(base64.b64decode(signature_b64), canonical_json(payload))
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def _naive_utc(iso_value):
    """An ISO timestamp from the server as the naive UTC datetime Odoo stores."""
    if not iso_value:
        return False
    value = datetime.fromisoformat(iso_value)
    if value.tzinfo:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class PanSelfLearningLink(models.Model):
    _name = 'pan.self.learning.link'
    _description = 'Pantalytics Account Link'

    status = fields.Selection(STATUS_SELECTION, default='not_connected', required=True)
    key = fields.Char(groups='base.group_system', copy=False)

    # The pairing in progress. The code is for a person to read; the device
    # token proves the poll comes from this database, so it is kept with the key.
    user_code = fields.Char(copy=False)
    verify_url = fields.Char(copy=False)
    device_token = fields.Char(groups='base.group_system', copy=False)
    pairing_expires_at = fields.Datetime(copy=False)

    # The last entitlement whose signature checked out, and what it said.
    posthog_key = fields.Char(readonly=True, copy=False)
    posthog_host = fields.Char(readonly=True, copy=False)
    session_replay = fields.Boolean(readonly=True, copy=False)
    valid_until = fields.Datetime(readonly=True)
    message = fields.Char(readonly=True)
    entitlement_json = fields.Text(readonly=True, copy=False)
    signature = fields.Char(readonly=True, copy=False)

    last_check = fields.Datetime(readonly=True, copy=False)
    last_error = fields.Char(readonly=True, copy=False)

    connected_user_id = fields.Many2one('res.users', readonly=True, copy=False,
                                        ondelete='set null')
    connected_on = fields.Datetime(readonly=True, copy=False)

    # -------------------------------------------------------------------------
    # One row
    # -------------------------------------------------------------------------

    @api.model
    def current(self):
        return self.sudo().search([], limit=1)

    def is_entitled(self):
        """May this Odoo report? Connected, a key in hand, an answer that
        named a project and has not lapsed."""
        self.ensure_one()
        if self.status != 'active' or not self.sudo().key or not self.posthog_key:
            return False
        return bool(self.valid_until and self.valid_until > fields.Datetime.now())

    @api.model
    def config(self):
        """What the browser needs, or False. Read by `ir.http.session_info`
        once per page load."""
        link = self.current()
        if not link or not link.is_entitled():
            return False
        return {
            'api_key': link.posthog_key,
            'api_host': link.posthog_host,
            'session_replay': link.session_replay,
        }

    def _check_admin(self):
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only an administrator can change the connection '
                                'to Pantalytics.'))

    # -------------------------------------------------------------------------
    # Pairing
    # -------------------------------------------------------------------------

    @api.model
    def action_connect(self):
        """Ask our server for a code, and show it with the link."""
        self._check_admin()
        link = self.current() or self.sudo().create({})
        if link.is_entitled():
            raise UserError(_('This Odoo instance is already connected to Pantalytics. '
                              'Disconnect it first to connect it again.'))
        code, body = link._post(LINK_PREFIX + '/start', {
            'db_uuid': self._db_uuid(),
            'odoo_url': self.env['ir.config_parameter'].sudo().get_param('web.base.url', ''),
            'module_version': self._module_version(),
        })
        if code == 429:
            raise UserError(_('Too many connection attempts from this Odoo instance. '
                              'Try again in a few minutes.'))
        if code != 200 or body.get('status') != 'started':
            raise UserError(_('Pantalytics did not accept the request (HTTP %s). '
                              'Try again later.') % code)
        link.write({
            'status': 'pending',
            'user_code': body['user_code'],
            'verify_url': body.get('verify_url_complete') or body['verify_url'],
            'device_token': body['device_token'],
            'pairing_expires_at': _naive_utc(body.get('expires_at')),
            'last_error': False,
        })
        return link

    def action_check_approval(self):
        """Collect the key once the admin has approved in their browser.

        Returns a notification when there is nothing to collect yet, and False
        when something changed, so the settings page re-reads and redraws.
        """
        self.ensure_one()
        self._check_admin()
        if self.sudo().key and self.status == 'active' and not self.is_entitled():
            # Connected, but the answer never came (or lapsed): ask again now
            # rather than at the next daily heartbeat.
            self._heartbeat_guarded()
            return False
        token = self.sudo().device_token
        if self.status != 'pending' or not token:
            return False

        code, body = self._post(LINK_PREFIX + '/poll', {'device_token': token})
        status = body.get('status')
        if status == 'linked' and body.get('key'):
            self.sudo().write({
                'key': body['key'],
                'status': 'active',
                'connected_user_id': self.env.user.id,
                'connected_on': fields.Datetime.now(),
            })
            self._clear_pairing()
            self._heartbeat_guarded()
            return False
        if status in ('pending', 'too_soon'):
            return self._notify(_('Not approved yet. Approve it on the Pantalytics '
                                  'page first, then check again.'))
        if code >= 500 or not status:
            return self._notify(_('Pantalytics did not answer (HTTP %s). Try again '
                                  'in a minute; the code stays valid.') % code, 'warning')
        # expired, collected, unknown: this pairing cannot finish. Start over.
        self._clear_pairing()
        if not self.sudo().key:
            self.status = 'not_connected'
        return self._notify(_('This code is no longer valid. Press Connect to '
                              'Pantalytics to get a new one.'), 'warning')

    @api.model
    def accept_key(self, key):
        """The Pantalytics panel connected this Odoo itself: it holds an
        administrator's key here, so there is no tab and no code. The key is
        the installation key the panel just minted. Returns where the link
        stands after its first check-in, so the panel can say so.
        """
        self._check_admin()
        if not isinstance(key, str) or not key.startswith('mp_') or len(key) > 128:
            raise UserError(_('That is not a Pantalytics installation key.'))
        link = self.current() or self.sudo().create({})
        link._clear_pairing()
        link.sudo().write({
            'key': key,
            'status': 'active',
            'posthog_key': False,
            'posthog_host': False,
            'session_replay': False,
            'valid_until': False,
            'message': False,
            'last_error': False,
            'connected_user_id': self.env.user.id,
            'connected_on': fields.Datetime.now(),
        })
        link._heartbeat_guarded()
        return {'status': link.status, 'last_error': link.last_error or ''}

    def collect_on_return(self):
        """The admin came back from the Pantalytics tab: collect the key now."""
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            return
        if self.status == 'pending':
            try:
                self.action_check_approval()
            except UserError as error:
                self.last_error = str(error)

    def action_disconnect(self):
        """Forget the key and the last answer on this database."""
        self.ensure_one()
        self._check_admin()
        self._clear_pairing()
        self.sudo().write({
            'status': 'not_connected',
            'key': False,
            'posthog_key': False,
            'posthog_host': False,
            'session_replay': False,
            'valid_until': False,
            'message': False,
            'entitlement_json': False,
            'signature': False,
            'last_error': False,
            'connected_user_id': False,
            'connected_on': False,
        })
        return True

    def _clear_pairing(self):
        self.sudo().write({
            'user_code': False,
            'verify_url': False,
            'device_token': False,
            'pairing_expires_at': False,
        })

    # -------------------------------------------------------------------------
    # Heartbeat
    # -------------------------------------------------------------------------

    @api.model
    def _cron_heartbeat(self):
        link = self.current()
        if link:
            link._heartbeat_guarded()

    def _heartbeat_guarded(self):
        """A heartbeat that cannot take the caller's transaction down with it."""
        try:
            with self.env.cr.savepoint():
                self._heartbeat()
        except Exception as error:  # noqa: BLE001 - recorded, never raised
            _logger.exception('[Self Learning] Heartbeat failed')
            self.sudo().write({'last_check': fields.Datetime.now(), 'last_error': str(error)})

    def _heartbeat(self):
        """Report in, and store the answer if, and only if, it is ours."""
        self.ensure_one()
        key = self.sudo().key
        if not key:
            return
        now = fields.Datetime.now()
        try:
            code, body = self._post(HEARTBEAT_PATH, {
                'db_uuid': self._db_uuid(),
                'module_version': self._module_version(),
                'odoo_version': release.major_version,
            }, key=key)
        except UserError as error:
            # Offline keeps the cached answer: valid_until is the grace period.
            self.sudo().write({'last_check': now, 'last_error': str(error)})
            return

        if code == 403 and body.get('status') == 'wrong_database':
            reason = _('This key was issued to another Odoo database. A copy '
                       'needs its own connection: Disconnect, then Connect to '
                       'Pantalytics.')
            self._refused(now, reason)
            return
        if code == 401:
            self._refused(now, _('Pantalytics no longer recognises this key.'))
            return
        if code != 200:
            self.sudo().write({'last_check': now,
                               'last_error': _('Heartbeat failed (HTTP %s).') % code})
            return

        payload = body.get('entitlement') or {}
        signature = body.get('signature') or ''
        problem = self._untrusted(payload, signature)
        if problem:
            _logger.warning('[Self Learning] Ignored an entitlement: %s', problem)
            self.sudo().write({'last_check': now, 'last_error': problem})
            return

        status = payload.get('status')
        self.sudo().write({
            'status': status if status in dict(STATUS_SELECTION) else 'invalid',
            'posthog_key': (payload.get('posthog_key') or '')[:128] or False,
            'posthog_host': (payload.get('posthog_host') or '')[:255] or False,
            'session_replay': bool(payload.get('session_replay')),
            'valid_until': _naive_utc(payload.get('valid_until')),
            'message': payload.get('message') or False,
            'entitlement_json': json.dumps(payload, sort_keys=True),
            'signature': signature,
            'last_check': now,
            'last_error': False,
        })

    def _refused(self, now, reason):
        _logger.warning('[Self Learning] %s', reason)
        self.sudo().write({
            'status': 'invalid', 'last_check': now, 'last_error': reason,
            'posthog_key': False, 'posthog_host': False, 'session_replay': False,
            'entitlement_json': False, 'signature': False, 'valid_until': False,
        })

    def _untrusted(self, payload, signature):
        """Why this answer may not be stored, or None when it may."""
        if not verify_signature(payload, signature, _public_key()):
            return _('The answer from Pantalytics was not signed with its key.')
        if payload.get('db_uuid') != self._db_uuid():
            return _('The answer from Pantalytics was meant for another Odoo instance.')
        return None

    # -------------------------------------------------------------------------
    # Plumbing
    # -------------------------------------------------------------------------

    def _post(self, path, payload, key=None):
        """POST to our server. Returns (status code, JSON body); raises UserError
        when the server cannot be reached at all."""
        headers = {'Authorization': f'Bearer {key}'} if key else {}
        try:
            response = requests.post(
                _server_url() + path, json=payload, headers=headers, timeout=TIMEOUT)
        except requests.RequestException as error:
            _logger.warning('[Self Learning] %s unreachable: %s', path, error)
            raise UserError(_('Could not reach Pantalytics. Check that this server '
                              'can make outgoing HTTPS requests.')) from error
        try:
            body = response.json()
        except ValueError:
            body = {}
        return response.status_code, body if isinstance(body, dict) else {}

    @api.model
    def _db_uuid(self):
        return self.env['ir.config_parameter'].sudo().get_param('database.uuid', '')

    @api.model
    def _module_version(self):
        return self.env['ir.module.module'].sudo().search(
            [('name', '=', 'pan_self_learning')], limit=1).installed_version or ''

    def _notify(self, message, kind='info'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'message': message, 'type': kind},
        }
