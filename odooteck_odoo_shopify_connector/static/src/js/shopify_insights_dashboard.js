/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, onMounted, onWillUnmount, useRef, useReactive } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";

export class ShopifyStoreInsightsDashboard extends Component {
    static template = "odooteck_odoo_shopify_connector.ShopifyStoreInsightsDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.salesTrendCanvas = useRef("salesTrendChart");
        this.financialStatusCanvas = useRef("financialStatusChart");
        this.fulfillmentStatusCanvas = useRef("fulfillmentStatusChart");
        this.topProductsCanvas = useRef("topProductsChart");
        this.categoryCanvas = useRef("categoryChart");

        this.chartInstances = {};

        const initialInstanceId = this.props.action?.params?.instance_id ||
                                  this.props.action?.context?.active_instance_id ||
                                  this.props.action?.context?.default_instance_id ||
                                  null;

        this.state = useReactive({
            isLoading: true,
            selectedInstanceId: initialInstanceId,
            selectedPeriod: "all",
            data: null,
        });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.fetchData();
        });

        onMounted(() => {
            this.renderCharts();
        });

        onWillUnmount(() => {
            this.destroyCharts();
        });
    }

    async fetchData() {
        try {
            const result = await this.orm.call(
                "shopify.instance",
                "get_store_insights_data",
                [],
                {
                    instance_id: this.state.selectedInstanceId,
                    period: this.state.selectedPeriod,
                }
            );
            this.state.data = result;
            if (!this.state.selectedInstanceId && result.selected_instance_id) {
                this.state.selectedInstanceId = result.selected_instance_id;
            }
        } catch (error) {
            console.error("Failed to load Shopify store insights:", error);
            this.notification.add(_t("Unable to load store insights data."), { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    async onSelectStore(ev) {
        const val = ev.target.value;
        this.state.selectedInstanceId = val ? parseInt(val) : null;
        await this.reloadDashboard();
    }

    async onSelectPeriod(period) {
        if (this.state.selectedPeriod === period) return;
        this.state.selectedPeriod = period;
        await this.reloadDashboard();
    }

    async reloadDashboard() {
        this.destroyCharts();
        this.state.isLoading = true;
        await this.fetchData();
        // Give OWL a render cycle to mount canvas elements if needed
        setTimeout(() => {
            this.renderCharts();
        }, 50);
    }

    destroyCharts() {
        Object.keys(this.chartInstances).forEach((key) => {
            if (this.chartInstances[key]) {
                try {
                    this.chartInstances[key].destroy();
                } catch (e) {
                    console.warn("Chart destroy warning:", e);
                }
                this.chartInstances[key] = null;
            }
        });
    }

    renderCharts() {
        if (typeof window.Chart === "undefined") {
            return;
        }
        const data = this.state.data;
        if (!data) return;

        this.destroyCharts();

        this.renderSalesTrendChart(data);
        this.renderFinancialStatusChart(data);
        this.renderFulfillmentStatusChart(data);
        this.renderTopProductsChart(data);
        this.renderCategoryChart(data);
    }

    renderSalesTrendChart(data) {
        const el = this.salesTrendCanvas.el;
        if (!el) return;

        const trend = data.sales_trend || { labels: [], revenue: [], orders: [] };
        const currency = data.currency || "$";

        const labels = trend.labels.length ? trend.labels : [_t("No Data")];
        const revenue = trend.revenue.length ? trend.revenue : [0];
        const orders = trend.orders.length ? trend.orders : [0];

        const ctx = el.getContext("2d");
        let gradient = null;
        if (ctx) {
            gradient = ctx.createLinearGradient(0, 0, 0, 280);
            gradient.addColorStop(0, "rgba(37, 99, 235, 0.35)");
            gradient.addColorStop(1, "rgba(37, 99, 235, 0.0)");
        }

        this.chartInstances.salesTrend = new window.Chart(el, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        type: "line",
                        label: _t("Revenue"),
                        data: revenue,
                        borderColor: "#2563EB",
                        backgroundColor: gradient || "rgba(37, 99, 235, 0.1)",
                        borderWidth: 3,
                        pointBackgroundColor: "#2563EB",
                        pointBorderColor: "#FFFFFF",
                        pointHoverRadius: 6,
                        pointRadius: 4,
                        fill: true,
                        tension: 0.35,
                        yAxisID: "y",
                    },
                    {
                        type: "bar",
                        label: _t("Orders"),
                        data: orders,
                        backgroundColor: "rgba(148, 163, 184, 0.4)",
                        hoverBackgroundColor: "rgba(100, 116, 139, 0.7)",
                        borderRadius: 4,
                        barThickness: 16,
                        yAxisID: "y1",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: "top",
                        labels: {
                            usePointStyle: true,
                            boxWidth: 8,
                            font: { family: "Inter, sans-serif", weight: "600", size: 12 },
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                if (context.dataset.type === "line") {
                                    return ` Revenue: ${currency}${context.parsed.y.toLocaleString()}`;
                                }
                                return ` Orders: ${context.parsed.y}`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 11 } },
                    },
                    y: {
                        type: "linear",
                        display: true,
                        position: "left",
                        grid: { color: "rgba(226, 232, 240, 0.6)" },
                        ticks: {
                            callback: function (val) {
                                return `${currency}${val.toLocaleString()}`;
                            },
                            font: { size: 11 },
                        },
                    },
                    y1: {
                        type: "linear",
                        display: true,
                        position: "right",
                        grid: { drawOnChartArea: false },
                        ticks: {
                            precision: 0,
                            font: { size: 11 },
                        },
                    },
                },
            },
        });
    }

    renderFinancialStatusChart(data) {
        const el = this.financialStatusCanvas.el;
        if (!el) return;

        const fin = data.financial_breakdown || { labels: [], counts: [], colors: [] };
        const labels = fin.labels.length ? fin.labels : [_t("No Status Data")];
        const counts = fin.counts.length ? fin.counts : [1];
        const colors = fin.colors && fin.colors.length ? fin.colors : ["#94A3B8"];

        this.chartInstances.financialStatus = new window.Chart(el, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [
                    {
                        data: counts,
                        backgroundColor: colors,
                        borderWidth: 2,
                        borderColor: "#FFFFFF",
                        hoverOffset: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            usePointStyle: true,
                            boxWidth: 8,
                            font: { family: "Inter, sans-serif", size: 11 },
                            padding: 12,
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const val = ctx.parsed;
                                const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                                return ` ${ctx.label}: ${val} orders (${pct}%)`;
                            },
                        },
                    },
                },
            },
        });
    }

    renderFulfillmentStatusChart(data) {
        const el = this.fulfillmentStatusCanvas.el;
        if (!el) return;

        const ful = data.fulfillment_breakdown || { labels: [], counts: [], colors: [] };
        const labels = ful.labels.length ? ful.labels : [_t("No Fulfillment Data")];
        const counts = ful.counts.length ? ful.counts : [1];
        const colors = ful.colors && ful.colors.length ? ful.colors : ["#06B6D4", "#6366F1", "#EC4899"];

        this.chartInstances.fulfillmentStatus = new window.Chart(el, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [
                    {
                        data: counts,
                        backgroundColor: colors,
                        borderWidth: 2,
                        borderColor: "#FFFFFF",
                        hoverOffset: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            usePointStyle: true,
                            boxWidth: 8,
                            font: { family: "Inter, sans-serif", size: 11 },
                            padding: 12,
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const val = ctx.parsed;
                                const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                                return ` ${ctx.label}: ${val} orders (${pct}%)`;
                            },
                        },
                    },
                },
            },
        });
    }

    renderTopProductsChart(data) {
        const el = this.topProductsCanvas.el;
        if (!el) return;

        const prods = data.top_products || [];
        const currency = data.currency || "$";

        const labels = prods.length ? prods.map((p) => p.name) : [_t("No Products")];
        const revenues = prods.length ? prods.map((p) => p.revenue) : [0];

        this.chartInstances.topProducts = new window.Chart(el, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: _t("Revenue"),
                        data: revenues,
                        backgroundColor: [
                            "#3B82F6",
                            "#10B981",
                            "#F59E0B",
                            "#8B5CF6",
                            "#06B6D4",
                            "#EC4899",
                        ],
                        borderRadius: 6,
                        barThickness: 18,
                    },
                ],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                return ` Revenue: ${currency}${ctx.parsed.x.toLocaleString()}`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { color: "rgba(226, 232, 240, 0.6)" },
                        ticks: {
                            callback: function (val) {
                                return `${currency}${val.toLocaleString()}`;
                            },
                            font: { size: 10 },
                        },
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            font: { size: 11, weight: "500" },
                        },
                    },
                },
            },
        });
    }

    renderCategoryChart(data) {
        const el = this.categoryCanvas.el;
        if (!el) return;

        const cats = data.top_categories || { labels: [], values: [], colors: [] };
        const currency = data.currency || "$";

        const labels = cats.labels.length ? cats.labels : [_t("No Categories")];
        const values = cats.values.length ? cats.values : [1];
        const colors = cats.colors && cats.colors.length ? cats.colors : ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6"];

        this.chartInstances.category = new window.Chart(el, {
            type: "pie",
            data: {
                labels: labels,
                datasets: [
                    {
                        data: values,
                        backgroundColor: colors,
                        borderWidth: 2,
                        borderColor: "#FFFFFF",
                        hoverOffset: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            usePointStyle: true,
                            boxWidth: 8,
                            font: { family: "Inter, sans-serif", size: 11 },
                            padding: 10,
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                return ` ${ctx.label}: ${currency}${ctx.parsed.toLocaleString()}`;
                            },
                        },
                    },
                },
            },
        });
    }

    // Navigation and Action Handlers
    openOrder(orderId) {
        if (!orderId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            res_id: orderId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    viewAllOrders() {
        const domain = this.state.selectedInstanceId ? [["instance_id", "=", this.state.selectedInstanceId]] : [];
        this.action.doAction({
            name: _t("Shopify Orders"),
            type: "ir.actions.act_window",
            res_model: "shopify.order.mapping",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            context: { default_instance_id: this.state.selectedInstanceId },
        });
    }

    openSyncWizard() {
        this.action.doAction({
            name: _t("Sync Operations Wizard"),
            type: "ir.actions.act_window",
            res_model: "shopify.sync.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_instance_id: this.state.selectedInstanceId,
                default_sync_direction: "shopify_to_odoo",
                default_sync_orders: true,
            },
        });
    }

    openStoreSettings() {
        if (this.state.selectedInstanceId) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "shopify.instance",
                res_id: this.state.selectedInstanceId,
                views: [[false, "form"]],
                target: "current",
            });
        }
    }

    async loadSampleData() {
        try {
            await this.orm.call(
                "shopify.instance",
                "action_load_sample_insights_data",
                [this.state.selectedInstanceId]
            );
            await this.reloadDashboard();
            this.notification.add(_t("Sample analytics data loaded successfully!"), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Could not load sample analytics: ") + e.message, { type: "warning" });
        }
    }
}

registry.category("actions").add("shopify_store_insights_dashboard", ShopifyStoreInsightsDashboard);
