/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class AdvancedLoginHistoryDashboard extends Component {
    static template = "mst_advanced_login_history.AdvancedLoginHistoryDashboard";

    setup() {
        this.action = useService("action");

        this.state = useState({
            loading: true,
            cards: [],
            rows: [],
            location: {},
            recent_activity: [],
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;

        const result = await rpc("/mst_advanced_login_history/dashboard_data", {});

        this.state.cards = result.cards || [];
        this.state.rows = result.rows || [];
        this.state.location = result.location || {};
        this.state.recent_activity = result.recent_activity || [];
        this.state.loading = false;
    }

    async refreshDashboard() {
        await this.loadDashboardData();
    }

    openMap() {
        if (this.state.location && this.state.location.open_url) {
            window.open(this.state.location.open_url, "_blank");
        }
    }

    openLoginRecord(row) {
        if (!row || !row.res_model || !row.res_id) {
            return;
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Login History",
            res_model: row.res_model,
            res_id: row.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add(
    "mst_advanced_login_history.dashboard",
    AdvancedLoginHistoryDashboard
);