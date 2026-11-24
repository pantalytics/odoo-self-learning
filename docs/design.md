# Settings page design

The one screen this module has: Settings, Odoo Self Learning. The clickable
design is the canvas "Self Learning screens" in Claude (Design type);
screenshots below are Odoo 19, taken locally on 2026-11-24.

## Words

One verb and one thing, on every screen of the flow: this Odoo instance
**connects** to a Pantalytics **workspace**. Signing in happens on the way
when it is needed and is never a step of its own. The pairing code is
plumbing and never shown. (Link is for joining two things that are both
already in Pantalytics: a local vault to a cloud vault, a partner workspace
to a company. Connect is for something outside that gets a key.)

## States

| State | The Workspace row | Screenshot |
|---|---|---|
| Not connected | **Connect to Pantalytics**, nothing else | [1](design/1-not-connected.png) |
| Waiting | amber "Finish in the Pantalytics tab", Cancel; follows by itself | [2](design/2-pending.png) |
| Connected | green "Connected to Juffermans", Disconnect beside it; Reporting appears | [3](design/3-connected.png) |
| Disconnected at Pantalytics | red status, **Connect to Pantalytics** | [4](design/4-disconnected.png) |

On the Pantalytics side the approval page says "Connect *host* for Odoo
Self Learning to your workspace *X*" when the Odoo instance is already in a
workspace, and offers a pick of workspace when it is not.

## Brand check (brand.pantalytics.com)

| Rule | How |
|---|---|
| One section per product, at most three blocks; checkboxes, saved with Save | Pantalytics and Reporting; two checkboxes |
| Odoo's own buttons, font and Title Case in the backend | yes |
| One primary button per screen | Connect to Pantalytics, only when not connected |
| Colour is status: green works, amber needs you, red broken | yes |
| Stay quiet when fine; state each fact once | no help lines, no "nothing is sent" line |
| Destructive actions confirmed | Disconnect asks first |

Departure, on purpose: Disconnect sits beside Connected instead of in a
Danger Zone block; it belongs to that row and is undone by connecting again.
