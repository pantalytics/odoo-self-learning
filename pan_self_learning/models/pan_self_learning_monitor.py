# -*- coding: utf-8 -*-
import logging

import requests
from odoo import api, models

from .. import monitor

_logger = logging.getLogger(__name__)


class PanSelfLearningMonitor(models.AbstractModel):
    """The five-minute check: module drift, and a push to Uptime Kuma.
    The logic lives in `monitor.py`; this is only the Odoo side of it."""

    _name = 'pan.self.learning.monitor'
    _description = 'Odoo Self Learning: Monitor'

    @api.model
    def _installed_versions(self):
        """`(name, db_version, code_version)` for every installed module.
        `latest_version` is what the database was upgraded to, the computed
        `installed_version` what the manifest on disk says (Odoo's own,
        confusing, field names)."""
        modules = self.env['ir.module.module'].sudo().search([('state', '=', 'installed')])
        return [(m.name, m.latest_version, m.installed_version) for m in modules]

    @api.model
    def _cron_monitor(self):
        drift = monitor.find_drift(self._installed_versions())
        if drift:
            # One format string, so error tracking keeps one issue for it;
            # the module list is a value and stays out of the report.
            _logger.error('Module code and database out of sync: %s', monitor.describe(drift))
        base = self.env['ir.config_parameter'].sudo().get_param(monitor.PUSH_PARAM)
        if not base:
            return
        if not monitor.valid_push_url(base):
            _logger.warning('[Self Learning] Ignoring %s: not an http(s) URL', monitor.PUSH_PARAM)
            return
        try:
            requests.get(monitor.push_url(base, drift), timeout=monitor.TIMEOUT)
        except requests.RequestException:
            # Kuma notices a missing push by itself; never fail the cron for it.
            _logger.warning('[Self Learning] Monitor push failed', exc_info=True)
