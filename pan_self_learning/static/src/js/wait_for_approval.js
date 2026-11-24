/** While the settings page waits for approval, ask Odoo every few seconds
 * whether the code was approved, and redraw once it was. Replaces the
 * "Check Approval" button: the admin approves in the other tab and this
 * tab follows by itself. */
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, onMounted, onWillUnmount, xml } from "@odoo/owl";

// Pantalytics answers "too soon" to polls closer than five seconds apart.
const INTERVAL_MS = 6000;

export class WaitForApproval extends Component {
    static props = standardWidgetProps;
    static template = xml`<span/>`;

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        onMounted(() => {
            this.timer = browser.setInterval(() => this.check(), INTERVAL_MS);
        });
        onWillUnmount(() => browser.clearInterval(this.timer));
    }

    async check() {
        if (this.busy || this.props.record.data.pan_self_learning_state !== "pending") {
            return;
        }
        this.busy = true;
        try {
            const status = await this.orm.call("pan.self.learning.link", "wait_for_approval", []);
            if (status !== "pending") {
                browser.clearInterval(this.timer);
                this.action.doAction("reload_context");
            }
        } finally {
            this.busy = false;
        }
    }
}

registry.category("view_widgets").add("pan_self_learning_wait", { component: WaitForApproval });
