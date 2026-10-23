# -*- coding: utf-8 -*-
"""The settings page: one status line for the Pantalytics account, and on a
connected instance three switches. The project key and host are never typed
here; they arrive in the signed entitlement (pan_self_learning_link.py).

There is no master switch any more. Connected is on, Disconnect is off, and
a switch for a sensor that is off is a page that looks broken. The
`pan_self_learning.enabled` parameter still exists for a deploy that wants
to silence the module without disconnecting it (ir_http.py reads it); it is
not on the screen.
"""
from odoo import api, fields, models

from .pan_self_learning_link import STATUS_SELECTION

# The line's four states. `broken` is a connection Pantalytics refused or
# replaced: red, the word that broke, and the way back.
STATE_SELECTION = [
    ("not_connected", "Not connected"),
    ("pending", "Waiting for approval"),
    ("connected", "Connected"),
    ("broken", "Broken"),
]
BROKEN = ("revoked", "invalid")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Stored as the inverse of the parameter the loader reads
    # (`disable_session_recording`), so an upgraded database keeps its answer.
    pan_self_learning_session_replay = fields.Boolean(
        string="Record sessions",
        compute="_compute_pan_self_learning_session_replay",
        inverse="_inverse_pan_self_learning_session_replay",
    )
    # Written as "True"/"False" by hand: a Boolean `config_parameter` deletes
    # the row on False, which server_errors.py would read as its default, on.
    pan_self_learning_server_errors = fields.Boolean(
        string="Report server errors",
        compute="_compute_pan_self_learning_server_errors",
        inverse="_inverse_pan_self_learning_server_errors",
    )
    pan_self_learning_mask_all_text = fields.Boolean(
        string="Mask all text in recordings",
        config_parameter="pan_self_learning.mask_all_text",
        default=False,
    )

    # The link, read once per page load. Nothing stored on this model.
    pan_self_learning_state = fields.Selection(
        STATE_SELECTION, compute="_compute_pan_self_learning_link"
    )
    pan_self_learning_link_status = fields.Selection(
        STATUS_SELECTION, compute="_compute_pan_self_learning_link"
    )
    pan_self_learning_user_code = fields.Char(
        string="Code", compute="_compute_pan_self_learning_link"
    )
    pan_self_learning_verify_url = fields.Char(
        string="Approve at", compute="_compute_pan_self_learning_link"
    )
    pan_self_learning_last_error = fields.Char(compute="_compute_pan_self_learning_link")
    pan_self_learning_message = fields.Char(compute="_compute_pan_self_learning_link")
    pan_self_learning_connected_by = fields.Char(compute="_compute_pan_self_learning_link")

    def _compute_pan_self_learning_session_replay(self):
        off = self.env["ir.config_parameter"].sudo().get_param(
            "pan_self_learning.disable_session_recording", "False"
        ) in ("True", "1")
        for record in self:
            record.pan_self_learning_session_replay = not off

    def _inverse_pan_self_learning_session_replay(self):
        for record in self:
            self.env["ir.config_parameter"].sudo().set_param(
                "pan_self_learning.disable_session_recording",
                "False" if record.pan_self_learning_session_replay else "True",
            )

    def _compute_pan_self_learning_server_errors(self):
        on = self.env["ir.config_parameter"].sudo().get_param(
            "pan_self_learning.server_errors", "True"
        ) not in ("False", "0", "")
        for record in self:
            record.pan_self_learning_server_errors = on

    def _inverse_pan_self_learning_server_errors(self):
        for record in self:
            self.env["ir.config_parameter"].sudo().set_param(
                "pan_self_learning.server_errors",
                "True" if record.pan_self_learning_server_errors else "False",
            )

    @api.depends("pan_self_learning_mask_all_text")
    def _compute_pan_self_learning_link(self):
        link = self.env["pan.self.learning.link"].current()
        status = (link and link.status) or "not_connected"
        if status == "active":
            state = "connected"
        elif status in BROKEN:
            state = "broken"
        else:
            state = status
        for record in self:
            record.pan_self_learning_state = state
            record.pan_self_learning_link_status = status
            record.pan_self_learning_user_code = link and link.user_code
            record.pan_self_learning_verify_url = link and link.verify_url
            record.pan_self_learning_last_error = link and link.last_error
            record.pan_self_learning_message = link and link.message
            who = link and link.connected_user_id
            when = link and link.connected_on
            record.pan_self_learning_connected_by = (
                "%s, %s" % (who.name, fields.Date.to_string(when)) if who and when else False
            )

    def _reload(self):
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_pan_self_learning_connect(self):
        link = self.env["pan.self.learning.link"].action_connect()
        return {"type": "ir.actions.act_url", "url": link.verify_url, "target": "new"}

    def action_pan_self_learning_check(self):
        link = self.env["pan.self.learning.link"].current()
        return (link and link.action_check_approval()) or self._reload()

    def action_pan_self_learning_disconnect(self):
        link = self.env["pan.self.learning.link"].current()
        if link:
            link.action_disconnect()
        return self._reload()
