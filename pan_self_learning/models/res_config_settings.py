# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pan_self_learning_enabled = fields.Boolean(
        string="Enable Self-Learning Odoo",
        config_parameter="pan_self_learning.enabled",
        help="Master switch. Even when enabled, tracking stays off until a "
        "PostHog project key is provided.",
    )
    pan_self_learning_project_key = fields.Char(
        string="PostHog Project Key",
        config_parameter="pan_self_learning.posthog_project_key",
        help="Public project API key (starts with 'phc_'). Leave empty to keep "
        "the module dormant.",
    )
    pan_self_learning_host = fields.Char(
        string="PostHog Host",
        config_parameter="pan_self_learning.posthog_host",
        default="https://eu.i.posthog.com",
        help="PostHog instance URL. Use https://us.i.posthog.com for US Cloud.",
    )
    pan_self_learning_mask_all_text = fields.Boolean(
        string="Mask all visible text",
        config_parameter="pan_self_learning.mask_all_text",
        default=False,
        help="Input fields are ALWAYS masked. Tick this to also hide all visible "
        "text (labels, values) in recordings — maximum privacy, but you mainly "
        "see layout and flow. Leave off for useful recordings.",
    )
    pan_self_learning_disable_session_recording = fields.Boolean(
        string="Disable session replay",
        config_parameter="pan_self_learning.disable_session_recording",
        default=False,
        help="Session replay is ON by default (the most valuable signal). Tick "
        "to turn it off for this instance (e.g. a customer that opts out).",
    )
