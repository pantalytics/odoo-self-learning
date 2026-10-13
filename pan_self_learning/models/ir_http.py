# -*- coding: utf-8 -*-
from odoo import models, release


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Expose the Odoo Self Learning configuration to the backend JS bundle
        through the session, so no extra RPC round-trip is needed to bootstrap
        PostHog. Dormant until this Odoo is connected to Pantalytics: the
        project key and host come from the signed entitlement, never from a
        data file.
        """
        result = super().session_info()
        result["pan_self_learning"] = self._pan_self_learning_config()
        return result

    def _pan_self_learning_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        enabled = icp.get_param("pan_self_learning.enabled", "True") not in ("False", "0", "")
        link = self.env["pan.self.learning.link"].sudo().config()
        api_key = link["api_key"] if link else ""
        api_host = link["api_host"] if link else ""

        env = self.env
        # Pseudonymous identity: database name + user id. Never a name or email.
        distinct_id = "%s#%s" % (env.cr.dbname, env.uid)
        # Replay is off when the local switch says so OR the entitlement does.
        local_off = icp.get_param("pan_self_learning.disable_session_recording", "False") in ("True", "1")

        return {
            # The loader stays a no-op until both flags are true.
            "enabled": bool(enabled and api_key),
            "api_key": api_key,
            "api_host": api_host,
            "distinct_id": distinct_id,
            # Per-customer workspace so data never mixes between databases.
            # The database uuid is the key Pantalytics knows this Odoo by
            # (the pairing), the name is what a person reads.
            "workspace": icp.get_param("database.uuid", "") or env.cr.dbname,
            "workspace_name": env.cr.dbname,
            "company": env.company.name if env.company else None,
            "odoo_version": release.version,
            "module_version": self.env["pan.self.learning.link"].sudo()._module_version(),
            "mask_all_text": icp.get_param("pan_self_learning.mask_all_text", "False")
            in ("True", "1"),
            "disable_session_recording": local_off or not (link and link["session_replay"]),
        }
