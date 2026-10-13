# -*- coding: utf-8 -*-
"""The way back from the Pantalytics approval page: collect the key, land on
the settings page. An ordinary link to this Odoo, not an OAuth redirect, so
there is no redirect URI to register per customer."""
from odoo import http
from odoo.http import request

SETTINGS_URL = '/odoo/settings#pan_self_learning'


class SelfLearningController(http.Controller):

    @http.route('/self_learning/pantalytics/return', type='http', auth='user')
    def pantalytics_return(self, **kwargs):
        if request.env.user.has_group('base.group_system'):
            link = request.env['pan.self.learning.link'].current()
            if link:
                link.collect_on_return()
        return request.redirect(SETTINGS_URL)
