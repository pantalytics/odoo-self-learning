# Self-Learning Odoo

An Odoo 19 module by [Pantalytics](https://pantalytics.com). It is the first
step of a loop that turns real usage into a self-learning, advising ERP.

## The loop

| Step | What | Status |
|---|---|---|
| 1. Observe | Watch how people actually use this Odoo and the implementation project around it | **this module** |
| 2. Propose | Where people get stuck, draft a config change or a guided answer | design in [#2](https://github.com/pantalytics/odoo-insights-pro/issues/2) and [#3](https://github.com/pantalytics/odoo-insights-pro/issues/3) |
| 3. Approve | A human reviews the proposal and applies it. Nothing is applied on its own | not started |
| 4. Learn | Measure the outcome on the same signal, remember it across customers | not started |

The pattern follows PostHog's [self-driving product](https://posthog.com/docs/self-driving):
the agent's output is a proposal, a person presses the button, the data says
whether it worked.

## What ships today (step 1)

`pan_self_learning` injects [PostHog](https://posthog.com) into
`web.assets_backend` and records pageviews, clicks, rage clicks and session
replay.

- **Live on install.** The module ships pre-connected to the Pantalytics
  PostHog project on EU Cloud. A plain install starts sending right away.
  Empty the key or flip the switch under **Settings → Self-Learning Odoo** to
  make it dormant.
- **Pseudonymous identity.** Users are identified as `db#uid`. Never a name,
  never an email.
- **Per-customer workspace.** Every database reports under its own PostHog
  group, so data never mixes between customers.
- **Inputs always masked.** Typed-in text never leaves the browser. Visible
  text (labels, list values) is recorded unless you turn on "Mask all visible
  text".

## Installation

1. Add this repository to your addons path (CloudPepper: attach as git addon).
2. Update the apps list and install **Self-Learning Odoo**.
3. Reload the backend.

Upgrading from `pan_insights_pro`: uninstall the old module, then install this
one. System parameters moved from `pan_insights_pro.*` to `pan_self_learning.*`.

## Configuration

System parameters, also editable under **Settings → Technical → System Parameters**:

| Parameter | Default | Meaning |
|---|---|---|
| `pan_self_learning.enabled` | `True` | Master switch. |
| `pan_self_learning.posthog_project_key` | Pantalytics EU key | Public PostHog project key. Empty = dormant. |
| `pan_self_learning.posthog_host` | `https://eu.i.posthog.com` | PostHog instance URL. |
| `pan_self_learning.mask_all_text` | `False` | Also mask visible text in recordings. |
| `pan_self_learning.disable_session_recording` | `False` | Turn session replay off for this instance. |

## How it works

On every backend page load, `ir.http.session_info` adds a `pan_self_learning`
block to the session (key, host, pseudonymous id, workspace, privacy flags).
The backend asset `posthog_loader.js` reads it, bootstraps PostHog, identifies
the pseudonymous user and assigns the database as a `workspace` group.

## Notes

- The loader fetches `array.js` from your PostHog host. Under a strict
  Content-Security-Policy, allow that host in `script-src` and `connect-src`.
- Session replay records your users' screens. Make sure your privacy notice
  and processing agreement cover it.
- License: LGPL-3.
