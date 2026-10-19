# -*- coding: utf-8 -*-
{
    "name": "Odoo Self Learning",
    "summary": "Product analytics for the Odoo backend, powered by PostHog",
    "description": """
Odoo Self Learning
==================

A lightweight, privacy-conscious asset module that injects PostHog into the
Odoo backend so you can see where users get stuck.

Key characteristics
--------------------
* **Dormant until connected** - does nothing until an administrator presses
  *Connect to Pantalytics* under *Settings > Odoo Self Learning*. The PostHog
  project arrives in the signed entitlement; no key is ever typed or shipped.
* **Pseudonymous identity** - users are identified as ``db#uid`` (database name
  plus user id), never by name or email.
* **Per-customer workspace** - each database reports under its own group so data
  never mixes between customers.
* **Privacy first** - recordings mask all text, inputs and attributes and block
  images, autocapture keeps element text out of events, and session replay can
  be switched off per instance.
    """,
    "author": "Pantalytics",
    "website": "https://pantalytics.com",
    "category": "Productivity/Analytics",
    "version": "19.0.2.4.0",
    "license": "LGPL-3",
    "depends": ["web"],
    "external_dependencies": {"python": ["cryptography", "requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pan_self_learning/static/src/js/posthog_loader.js",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
