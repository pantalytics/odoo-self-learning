# Settings page design

The one screen this module has: Settings, Odoo Self Learning. Checked
against brand.pantalytics.com (Odoo UI, Product UI, Colours, Tone of
voice) on 2026-11-24. Screenshots are Odoo 19, taken locally.

## States

| State | What the account row shows | Screenshot |
|---|---|---|
| Not connected | "Not connected. Nothing is sent until you connect." + **Connect Account** | [1](design/1-not-connected.png), [phone](design/5-not-connected-phone.png) |
| Waiting for approval | amber status, the code, **Check Approval**, Cancel | [2](design/2-pending.png) |
| Connected | green "Connected", who and when; Reporting and Danger Zone appear | [3](design/3-connected.png) |
| Disconnected or key refused | red status, Pantalytics' message, **Connect Account** | [4](design/4-disconnected.png) |

## Brand check

| Rule (source page) | How this page meets it |
|---|---|
| One section per product, at most three blocks (Odoo UI) | Pantalytics, Reporting, Danger Zone |
| Checkboxes, no switches; nothing works until Save (Odoo UI) | Reporting uses Odoo's checkbox settings |
| One line of explanation per setting (Odoo UI) | Every setting has one short line or none |
| Odoo's Title Case for labels in the backend (Odoo UI) | Connect Account, Check Approval, Record Sessions |
| No accent colour or Murecho in the backend (Odoo UI) | Odoo's own buttons and font only |
| One primary button per screen (Product UI) | Connect Account, or Check Approval while waiting |
| Colour means status: green works, amber needs the user, red broken (Product UI) | Connected green, Waiting amber, Disconnected red |
| Destructive actions last, confirmed (Product UI) | Disconnect only in Danger Zone, with a confirm |
| Confirm: question with the thing, consequence, verb repeated (Product UI) | "Disconnect this Odoo instance from Pantalytics? Reporting stops until you connect again." |
| State each fact once (Product UI) | Status word once; no repeated "Pantalytics account" title |
| Fixed term "Odoo instance", never "database" (Product UI) | Page copy uses neither; the confirm says Odoo instance |

## Open

- Odoo settings cannot collapse a block, so Danger Zone shows whenever the
  instance is connected instead of folded away.
- The message under "Disconnected at Pantalytics" comes from the
  Pantalytics server (`apps/self_learning.py` in odoo-mcp-pro-admin) and
  still says "database".
