# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ShopifyOnboardingWizard(models.TransientModel):
    _name = "shopify.onboarding.wizard"
    _description = "Shopify Store Guided Setup and Onboarding Wizard"

    instance_id = fields.Many2one(
        "shopify.instance",
        string="Shopify Store",
        required=True,
        ondelete="cascade",
    )
    current_step = fields.Selection(
        [
            ("connection", "1. API Connection & Credentials"),
            ("logistics", "2. Warehouse & Stock Logistics"),
            ("financials", "3. Pricelist & Accounting Financials"),
            ("automations", "4. Automation Workflows & Operations"),
        ],
        string="Current Setup Step",
        default="connection",
        required=True,
    )

    # Step Status & Progress
    onboarding_progress = fields.Integer(string="Progress (%)", compute="_compute_step_status")
    step_connection_done = fields.Boolean(string="Connection Done", compute="_compute_step_status")
    step_logistics_done = fields.Boolean(string="Logistics Done", compute="_compute_step_status")
    step_financials_done = fields.Boolean(string="Financials Done", compute="_compute_step_status")
    step_automations_done = fields.Boolean(string="Automations Done", compute="_compute_step_status")

    # Step 1: API Connection & Credentials
    shop_url = fields.Char(string="Shopify Store URL")
    auth_method = fields.Selection(
        [
            ("token", "Admin API Access Token (Recommended)"),
            ("oauth", "Shopify OAuth 2.0 (Custom App)"),
        ],
        string="Authentication Method",
        default="token",
    )
    access_token = fields.Char(string="Admin API Access Token")
    api_version = fields.Selection(
        [
            ("2025-01", "2025-01 (Latest Supported)"),
            ("2024-10", "2024-10"),
            ("2024-07", "2024-07"),
            ("2024-04", "2024-04"),
            ("2024-01", "2024-01"),
        ],
        string="Shopify API Version",
        default="2025-01",
    )
    client_id = fields.Char(string="Client ID (API Key)")
    client_secret = fields.Char(string="Client Secret")
    redirect_url = fields.Char(string="OAuth Callback URL", readonly=True)

    # Step 2: Warehouse & Stock Logistics
    company_id = fields.Many2one("res.company", string="Company")
    warehouse_id = fields.Many2one("stock.warehouse", string="Default Warehouse")
    location_id = fields.Many2one("stock.location", string="Default Stock Location")

    # Step 3: Pricelist & Accounting Financials
    pricelist_id = fields.Many2one("product.pricelist", string="Default Pricelist")
    payment_journal_id = fields.Many2one("account.journal", string="Default Payment Journal")
    payment_term_id = fields.Many2one("account.payment.term", string="Payment Terms")
    discount_product_id = fields.Many2one("product.product", string="Discount Service Product")
    delivery_product_id = fields.Many2one("product.product", string="Shipping Charge Product")
    auto_paid_invoices = fields.Boolean(string="Auto-Register Invoice Payments", default=True)

    # Step 4: Automations & Workflows
    sync_inventory_on_update = fields.Boolean(string="Real-time Inventory Sync", default=True)
    auto_validate_orders = fields.Boolean(string="Auto-Confirm Sales Orders", default=False)
    auto_create_invoices = fields.Boolean(string="Auto-Create Invoices", default=False)
    auto_deliver_orders = fields.Boolean(string="Auto-Validate Delivery Orders", default=False)
    auto_process_refunds = fields.Boolean(string="Auto-Process Refunds", default=True)
    auto_create_credit_notes = fields.Boolean(string="Auto-Create Credit Notes", default=True)
    auto_validate_refunds = fields.Boolean(string="Auto-Post Credit Notes", default=False)

    @api.depends("instance_id", "instance_id.state", "instance_id.warehouse_id", "instance_id.location_id",
                 "instance_id.pricelist_id", "instance_id.payment_journal_id", "instance_id.sync_inventory_on_update",
                 "instance_id.auto_validate_orders", "instance_id.auto_create_invoices")
    def _compute_step_status(self):
        for rec in self:
            inst = rec.instance_id
            if inst:
                rec.step_connection_done = inst.onboarding_step_connection
                rec.step_logistics_done = inst.onboarding_step_logistics
                rec.step_financials_done = inst.onboarding_step_financials
                rec.step_automations_done = inst.onboarding_step_automations
                rec.onboarding_progress = inst.onboarding_progress
            else:
                rec.step_connection_done = False
                rec.step_logistics_done = False
                rec.step_financials_done = False
                rec.step_automations_done = False
                rec.onboarding_progress = 0

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        instance_id = self.env.context.get("default_instance_id") or self.env.context.get("active_id")
        if not instance_id and self.env.context.get("active_model") == "shopify.instance":
            instance_id = self.env.context.get("active_id")
        if not instance_id:
            inst = self.env["shopify.instance"].search([], limit=1)
            instance_id = inst.id if inst else False

        if instance_id:
            inst = self.env["shopify.instance"].browse(instance_id)
            res.update({
                "instance_id": inst.id,
                "shop_url": inst.shop_url,
                "auth_method": inst.auth_method,
                "access_token": inst.access_token,
                "api_version": inst.api_version,
                "client_id": inst.client_id,
                "client_secret": inst.client_secret,
                "redirect_url": inst.redirect_url,
                "company_id": inst.company_id.id,
                "warehouse_id": inst.warehouse_id.id,
                "location_id": inst.location_id.id,
                "pricelist_id": inst.pricelist_id.id,
                "payment_journal_id": inst.payment_journal_id.id,
                "payment_term_id": inst.payment_term_id.id if inst.payment_term_id else False,
                "discount_product_id": inst.discount_product_id.id if inst.discount_product_id else False,
                "delivery_product_id": inst.delivery_product_id.id if inst.delivery_product_id else False,
                "auto_paid_invoices": inst.auto_paid_invoices,
                "sync_inventory_on_update": inst.sync_inventory_on_update,
                "auto_validate_orders": inst.auto_validate_orders,
                "auto_create_invoices": inst.auto_create_invoices,
                "auto_deliver_orders": inst.auto_deliver_orders,
                "auto_process_refunds": inst.auto_process_refunds,
                "auto_create_credit_notes": inst.auto_create_credit_notes,
                "auto_validate_refunds": inst.auto_validate_refunds,
            })
            if "default_current_step" in self.env.context:
                res["current_step"] = self.env.context["default_current_step"]
            elif not res.get("current_step"):
                if not inst.onboarding_step_connection:
                    res["current_step"] = "connection"
                elif not inst.onboarding_step_logistics:
                    res["current_step"] = "logistics"
                elif not inst.onboarding_step_financials:
                    res["current_step"] = "financials"
                else:
                    res["current_step"] = "automations"
        return res

    def _save_current_step_to_instance(self):
        self.ensure_one()
        inst = self.instance_id
        if not inst:
            return
        vals = {}
        if self.current_step == "connection":
            vals.update({
                "shop_url": self.shop_url,
                "auth_method": self.auth_method,
                "access_token": self.access_token,
                "api_version": self.api_version,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
        elif self.current_step == "logistics":
            vals.update({
                "company_id": self.company_id.id if self.company_id else inst.company_id.id,
                "warehouse_id": self.warehouse_id.id if self.warehouse_id else False,
                "location_id": self.location_id.id if self.location_id else False,
            })
        elif self.current_step == "financials":
            vals.update({
                "pricelist_id": self.pricelist_id.id if self.pricelist_id else False,
                "payment_journal_id": self.payment_journal_id.id if self.payment_journal_id else False,
                "payment_term_id": self.payment_term_id.id if self.payment_term_id else False,
                "discount_product_id": self.discount_product_id.id if self.discount_product_id else False,
                "delivery_product_id": self.delivery_product_id.id if self.delivery_product_id else False,
                "auto_paid_invoices": self.auto_paid_invoices,
            })
        elif self.current_step == "automations":
            vals.update({
                "sync_inventory_on_update": self.sync_inventory_on_update,
                "auto_validate_orders": self.auto_validate_orders,
                "auto_create_invoices": self.auto_create_invoices,
                "auto_deliver_orders": self.auto_deliver_orders,
                "auto_process_refunds": self.auto_process_refunds,
                "auto_create_credit_notes": self.auto_create_credit_notes,
                "auto_validate_refunds": self.auto_validate_refunds,
            })
        if vals:
            inst.write(vals)

    def _reopen_wizard(self):
        self.ensure_one()
        return {
            "name": _("Shopify Setup & Onboarding Wizard"),
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # Step Navigation Actions
    def action_go_step_connection(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        self.current_step = "connection"
        return self._reopen_wizard()

    def action_go_step_logistics(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        self.current_step = "logistics"
        return self._reopen_wizard()

    def action_go_step_financials(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        self.current_step = "financials"
        return self._reopen_wizard()

    def action_go_step_automations(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        self.current_step = "automations"
        return self._reopen_wizard()

    def action_next_step(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        steps = ["connection", "logistics", "financials", "automations"]
        idx = steps.index(self.current_step)
        if idx < len(steps) - 1:
            self.current_step = steps[idx + 1]
            return self._reopen_wizard()
        return self.action_save_and_close()

    def action_prev_step(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        steps = ["connection", "logistics", "financials", "automations"]
        idx = steps.index(self.current_step)
        if idx > 0:
            self.current_step = steps[idx - 1]
            return self._reopen_wizard()
        return self._reopen_wizard()

    # Step 1 Action: Test Connection inside Wizard
    def action_wizard_test_connection(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        res = self.instance_id.action_test_connection()
        return self._reopen_wizard()

    # Step 2 Action: Fetch Locations inside Wizard
    def action_wizard_fetch_locations(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        self.instance_id.action_fetch_locations()
        return self._reopen_wizard()

    # Step 4 Action: Launch Sync Wizard
    def action_save_and_launch_sync(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        return self.instance_id.action_open_sync_wizard()

    # Complete / Save
    def action_save_and_close(self):
        self.ensure_one()
        self._save_current_step_to_instance()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Shopify Setup Updated"),
                "message": _("Store '%s' setup configuration saved successfully (Progress: %s%%).")
                           % (self.instance_id.name, self.instance_id.onboarding_progress),
                "type": "success",
                "sticky": False,
            },
        }
