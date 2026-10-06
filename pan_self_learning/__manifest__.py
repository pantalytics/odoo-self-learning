# -*- coding: utf-8 -*-
{
    "name": "Self-Learning Odoo",
    "summary": "Observe how your team uses Odoo; the first step of a self-learning, advising ERP",
    "description": """
Self-Learning Odoo
==================

The observation layer of a loop that turns real usage into advice:

1. **Observe** how people actually use this Odoo (this module, via PostHog).
2. **Propose** a config change or a guided answer where they get stuck.
3. **Approve**: a human reviews the proposal and applies it.
4. **Learn**: the outcome is measured on the same signal and remembered,
   across customers.

Today this module ships step 1 only. Steps 2 to 4 are tracked in the
repository issues.

What it does
------------
* Loads PostHog into the backend and records pageviews, clicks, rage clicks
  and session replay. Input fields are always masked.
* Identifies users pseudonymously as ``db#uid``, never by name or email.
* Reports each database under its own PostHog workspace group.
* Ships pre-connected to the Pantalytics EU project; swap the key or switch
  it off under *Settings > Self-Learning Odoo*.
    """,
    "author": "Pantalytics",
    "website": "https://pantalytics.com",
    "category": "Productivity/Analytics",
    "version": "19.0.2.0.0",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "data/ir_config_parameter.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pan_self_learning/static/src/js/posthog_loader.js",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
