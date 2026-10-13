# -*- coding: utf-8 -*-
"""Drop the pre-filled PostHog project from the system parameters.

Up to 19.0.1.x the module shipped with the Pantalytics project key in its
data files (`noupdate`, so an upgrade leaves it in place). From 19.0.2.0.0
the key and host arrive in the signed entitlement once the instance is
connected to Pantalytics, and nothing reads these two parameters any more.
Deleting them is what makes "dormant until connected" true on an upgraded
database as well as on a fresh one.
"""
import logging

_logger = logging.getLogger(__name__)

PARAMS = ('pan_self_learning.posthog_project_key', 'pan_self_learning.posthog_host')


def migrate(cr, version):
    if not version:
        return
    cr.execute('DELETE FROM ir_config_parameter WHERE key IN %s', (PARAMS,))
    _logger.info('[Self Learning] 19.0.2.0.0: removed the pre-filled PostHog '
                 'project (%s rows). Connect to Pantalytics to resume.', cr.rowcount)
