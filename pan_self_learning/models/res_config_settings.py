# -*- coding: utf-8 -*-
"""The settings page: one line for the Pantalytics account, two privacy
switches. The project key and host are no longer typed here; they arrive in
the signed entitlement once the instance is connected (pan_self_learning_link.py).
"""
from odoo import api, fields, models

from .pan_self_learning_link import STATUS_SELECTION


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pan_self_learning_enabled = fields.Boolean(
        string="Enable Odoo Self Learning",
        config_parameter="pan_self_learning.enabled",
        help="Master switch. Even when enabled, tracking stays off until this "
        "Odoo instance is connected to Pantalytics.",
    )
    pan_self_learning_mask_all_text = fields.Boolean(
        string="Mask all visible text",
        config_parameter="pan_self_learning.mask_all_text",
        default=False,
        help="Input fields are ALWAYS masked. Tick this to also hide all visible "
        "text (labels, values) in recordings: maximum privacy, but you mainly "
        "see layout and flow. Leave off for useful recordings.",
    )
    pan_self_learning_disable_session_recording = fields.Boolean(
        string="Disable session replay",
        config_parameter="pan_self_learning.disable_session_recording",
        default=False,
        help="Session replay is on once connected (the most valuable signal). "
        "Tick to turn it off for this instance, for example a customer that opts out.",
    )

    # The link, read once per page load. Nothing stored on this model.
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

    @api.depends("pan_self_learning_enabled")
    def _compute_pan_self_learning_link(self):
        link = self.env["pan.self.learning.link"].current()
        for record in self:
            record.pan_self_learning_link_status = (link and link.status) or "not_connected"
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
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_pan_self_learning_connect(self):
        link = self.env["pan.self.learning.link"].action_connect()
        return {
            "type": "ir.actions.act_url",
            "url": link.verify_url,
            "target": "new",
        }

    def action_pan_self_learning_check(self):
        link = self.env["pan.self.learning.link"].current()
        return (link and link.action_check_approval()) or self._reload()

    def action_pan_self_learning_disconnect(self):
        link = self.env["pan.self.learning.link"].current()
        if link:
            link.action_disconnect()
        return self._reload()
