# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck.
# See LICENSE file for full copyright and licensing details.

import json
import logging
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .shopify_client import ShopifyApiClient, ShopifyNotFoundError

_logger = logging.getLogger(__name__)

class ShopifyInstance(models.Model):
    _name = "shopify.instance"
    _description = "Shopify Store Instance"
    _order = "sequence, id desc"
    _rec_name = "name"

    name = fields.Char(string="Store Name", required=True, copy=False)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Connected"),
            ("error", "Error"),
        ],
        string="Connection State",
        default="draft",
        required=True,
    )

    # API & Authentication Configuration
    auth_method = fields.Selection(
        selection=[
            ("token", "Direct Admin API Token (Custom App)"),
            ("oauth", "Shopify OAuth 2.0 (1-Click Redirect)"),
        ],
        string="Authentication Method",
        default="token",
        required=True,
    )
    shop_url = fields.Char(string="Store URL", required=True)
    access_token = fields.Char(string="Admin API Access Token", copy=False)
    client_id = fields.Char(string="Client ID / API Key", copy=False)
    client_secret = fields.Char(string="Client Secret", copy=False)
    oauth_scopes = fields.Char(
        string="OAuth Scopes",
        default="read_products,write_products,read_orders,write_orders,read_customers,write_customers,read_inventory,write_inventory,read_fulfillments,write_fulfillments,read_locations",
        help="Comma-separated Shopify access scopes.",
    )
    redirect_url = fields.Char(string="OAuth Redirect URI", compute="_compute_redirect_url", help="URL configured in Shopify App Allowed redirection URL(s).")
    api_version = fields.Selection(
        selection=[
            ("2024-07", "2024-07"),
            ("2024-10", "2024-10"),
            ("2025-01", "2025-01 (Recommended)"),
            ("2025-04", "2025-04"),
        ],
        string="API Version",
        default="2025-01",
        required=True,
    )
    webhook_secret = fields.Char(string="Webhook Client Secret", copy=False, help="Used to authenticate Shopify Webhook HMAC-SHA256 signatures.")
    shopify_location_id = fields.Char(string="Shopify Primary Location ID", help="The Shopify fulfillment location ID where inventory is managed.")

    @api.model
    def _default_warehouse_id(self):
        company = self.env.company
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        if not warehouse:
            warehouse = self.env["stock.warehouse"].search([], limit=1)
        return warehouse

    @api.model
    def _default_company_id(self):
        wh = self._default_warehouse_id()
        return wh.company_id if wh else self.env.company

    @api.model
    def _get_or_create_default_pricelist(self, company=None, currency=None):
        if not company:
            company = self.env.company
        curr = currency or company.currency_id
        pricelist_model = self.env["product.pricelist"]

        pricelist = pricelist_model.search([
            ("active", "=", True),
            ("currency_id", "=", curr.id),
            ("company_id", "in", [company.id, False]),
        ], limit=1)
        if not pricelist:
            pricelist = pricelist_model.search([
                ("active", "=", True),
                ("company_id", "=", company.id),
            ], limit=1)
        if not pricelist:
            pricelist = pricelist_model.search([
                ("active", "=", True),
                ("company_id", "=", False),
            ], limit=1)
        if not pricelist:
            pricelist = pricelist_model.sudo().create({
                "name": f"{company.name} - Default Pricelist ({curr.name})",
                "currency_id": curr.id,
                "company_id": company.id,
                "active": True,
            })
        return pricelist

    @api.model
    def _default_pricelist_id(self):
        company = self._default_company_id()
        return self._get_or_create_default_pricelist(company)

    # Odoo Configuration Defaults
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=_default_company_id,
        required=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Default Warehouse",
        default=_default_warehouse_id,
        domain="[('company_id', '=', company_id)]",
        required=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Default Stock Location",
        domain="[('company_id', 'in', (company_id, False)), ('usage', '=', 'internal')]",
    )
    team_id = fields.Many2one(
        "crm.team",
        string="Sales Team",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Default Salesperson",
        default=lambda self: self.env.user,
        domain="['|', ('company_ids', 'in', company_id), ('company_id', '=', False)]",
    )
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Default Pricelist",
        default=_default_pricelist_id,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Payment Terms",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    discount_product_id = fields.Many2one(
        "product.product",
        string="Discount Service Product",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    delivery_product_id = fields.Many2one(
        "product.product",
        string="Shipping Charge Product",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    # Workflow Automation Toggles
    auto_validate_orders = fields.Boolean(string="Auto-Confirm Sales Orders", default=False)
    auto_create_invoices = fields.Boolean(string="Auto-Create Invoices", default=False)
    payment_journal_id = fields.Many2one(
        "account.journal",
        string="Default Payment Journal",
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
        help="Journal used for auto-registering invoice payments from Shopify.",
    )
    auto_paid_invoices = fields.Boolean(
        string="Auto-Register Invoice Payment",
        default=True,
        help="Automatically register payment on invoice if Shopify financial status is paid.",
    )
    auto_deliver_orders = fields.Boolean(
        string="Auto-Validate Delivery",
        default=False,
        help="Automatically validate delivery order if Shopify fulfillment status is fulfilled.",
    )
    sync_inventory_on_update = fields.Boolean(string="Real-time Inventory Sync", default=True)

    # Refund & Return Automation Toggles
    auto_process_refunds = fields.Boolean(string="Auto-Process Refunds", default=True)
    auto_create_credit_notes = fields.Boolean(string="Auto-Create Credit Notes", default=True)
    auto_validate_refunds = fields.Boolean(string="Auto-Post Credit Notes", default=False)

    # Multi-Location & Metafields Configuration
    location_mapping_ids = fields.One2many("shopify.location.mapping", "instance_id", string="Location Mappings")
    metafield_mapping_ids = fields.One2many("shopify.metafield.mapping", "instance_id", string="Metafield Mappings")
    refund_mapping_ids = fields.One2many("shopify.refund.mapping", "instance_id", string="Refund Mappings")

    # Timestamps of Synchronization
    last_order_sync = fields.Datetime(string="Last Order Sync")
    last_product_sync = fields.Datetime(string="Last Product Sync")
    last_customer_sync = fields.Datetime(string="Last Customer Sync")
    last_inventory_sync = fields.Datetime(string="Last Inventory Sync")
    last_category_sync = fields.Datetime(string="Last Category Sync")

    # Metrics / Counts
    order_mapping_count = fields.Integer(string="Orders Count", compute="_compute_metrics")
    product_mapping_count = fields.Integer(string="Products Count", compute="_compute_metrics")
    category_mapping_count = fields.Integer(string="Categories Count", compute="_compute_metrics")
    customer_mapping_count = fields.Integer(string="Customers Count", compute="_compute_metrics")
    feed_count = fields.Integer(string="Pending Feeds", compute="_compute_metrics")
    history_count = fields.Integer(string="Sync Logs", compute="_compute_metrics")
    refund_mapping_count = fields.Integer(string="Refunds Count", compute="_compute_metrics")
    location_mapping_count = fields.Integer(string="Locations Count", compute="_compute_metrics")
    metafield_mapping_count = fields.Integer(string="Metafields Count", compute="_compute_metrics")

    # Dynamic Setup & Onboarding Plan
    onboarding_progress = fields.Integer(string="Setup Progress (%)", compute="_compute_onboarding_status")
    onboarding_step_connection = fields.Boolean(string="Step 1: Connection", compute="_compute_onboarding_status")
    onboarding_step_logistics = fields.Boolean(string="Step 2: Logistics", compute="_compute_onboarding_status")
    onboarding_step_financials = fields.Boolean(string="Step 3: Financials", compute="_compute_onboarding_status")
    onboarding_step_automations = fields.Boolean(string="Step 4: Automations", compute="_compute_onboarding_status")
    show_onboarding_panel = fields.Boolean(string="Show Onboarding Plan", default=True)

    @api.constrains("shop_url")
    def _check_shop_url(self):
        for record in self:
            if record.shop_url and not ("myshopify.com" in record.shop_url or record.shop_url.startswith("http")):
                raise ValidationError(_("Please specify a valid Shopify store URL (e.g. https://store-name.myshopify.com)."))

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        if self.warehouse_id:
            if self.warehouse_id.company_id and self.warehouse_id.company_id != self.company_id:
                self.company_id = self.warehouse_id.company_id
            if self.warehouse_id.lot_stock_id and (not self.location_id or self.location_id.warehouse_id != self.warehouse_id):
                self.location_id = self.warehouse_id.lot_stock_id

    @api.onchange("company_id")
    def _onchange_company_id(self):
        if self.company_id:
            # 1. Update warehouse to match company
            if not self.warehouse_id or self.warehouse_id.company_id != self.company_id:
                wh = self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)
                self.warehouse_id = wh
                self.location_id = wh.lot_stock_id if wh else False

            # 2. Update pricelist to match company
            if not self.pricelist_id or (self.pricelist_id.company_id and self.pricelist_id.company_id != self.company_id):
                self.pricelist_id = self._get_or_create_default_pricelist(self.company_id)

            # 3. Update payment journal to match company
            if self.payment_journal_id and self.payment_journal_id.company_id != self.company_id:
                self.payment_journal_id = self.env["account.journal"].search([
                    ("company_id", "=", self.company_id.id),
                    ("type", "in", ("bank", "cash")),
                ], limit=1)

            # 4. Clear mismatched company-specific products
            if self.discount_product_id and self.discount_product_id.company_id and self.discount_product_id.company_id != self.company_id:
                self.discount_product_id = False
            if self.delivery_product_id and self.delivery_product_id.company_id and self.delivery_product_id.company_id != self.company_id:
                self.delivery_product_id = False

    def _compute_metrics(self):
        for record in self:
            record.order_mapping_count = self.env["shopify.order.mapping"].search_count([("instance_id", "=", record.id)])
            record.product_mapping_count = self.env["shopify.template.mapping"].search_count([("instance_id", "=", record.id)])
            record.category_mapping_count = self.env["shopify.category.mapping"].search_count([("instance_id", "=", record.id)])
            record.customer_mapping_count = self.env["shopify.partner.mapping"].search_count([("instance_id", "=", record.id)])
            record.feed_count = self.env["shopify.feed"].search_count([("instance_id", "=", record.id), ("state", "in", ("draft", "error"))])
            record.history_count = self.env["shopify.sync.history"].search_count([("instance_id", "=", record.id)])
            record.refund_mapping_count = self.env["shopify.refund.mapping"].search_count([("instance_id", "=", record.id)])
            record.location_mapping_count = self.env["shopify.location.mapping"].search_count([("instance_id", "=", record.id)])
            record.metafield_mapping_count = self.env["shopify.metafield.mapping"].search_count([("instance_id", "=", record.id)])

    @api.depends("state", "warehouse_id", "location_id", "pricelist_id", "payment_journal_id",
                 "sync_inventory_on_update", "auto_validate_orders", "auto_create_invoices")
    def _compute_onboarding_status(self):
        for record in self:
            s1 = record.state == "confirmed"
            s2 = bool(record.warehouse_id and (record.location_id or record.warehouse_id.lot_stock_id))
            s3 = bool(record.pricelist_id and record.payment_journal_id)
            s4 = bool(record.sync_inventory_on_update or record.auto_validate_orders or record.auto_create_invoices)

            record.onboarding_step_connection = s1
            record.onboarding_step_logistics = s2
            record.onboarding_step_financials = s3
            record.onboarding_step_automations = s4

            completed = sum([1 for s in (s1, s2, s3, s4) if s])
            record.onboarding_progress = int((completed / 4.0) * 100)

    def action_toggle_onboarding(self):
        self.ensure_one()
        self.show_onboarding_panel = not self.show_onboarding_panel

    def action_open_step_connection(self):
        self.ensure_one()
        return {
            "name": _("Step 1: API Connection & Credentials - %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "shopify.onboarding.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_instance_id": self.id,
                "default_current_step": "connection",
            },
        }

    def action_open_step_logistics(self):
        self.ensure_one()
        return {
            "name": _("Step 2: Warehouse & Stock Logistics - %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "shopify.onboarding.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_instance_id": self.id,
                "default_current_step": "logistics",
            },
        }

    def action_open_step_financials(self):
        self.ensure_one()
        return {
            "name": _("Step 3: Pricelist & Accounting Financials - %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "shopify.onboarding.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_instance_id": self.id,
                "default_current_step": "financials",
            },
        }

    def action_open_step_automations(self):
        self.ensure_one()
        return {
            "name": _("Step 4: Automation Workflows & Operations - %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "shopify.onboarding.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_instance_id": self.id,
                "default_current_step": "automations",
            },
        }

    def action_open_onboarding_wizard(self):
        instance = self[:1] if self else self.search([], limit=1)
        if not instance:
            instance = self.create({"name": "My Shopify Store"})
        step = "connection"
        if not instance.onboarding_step_connection:
            step = "connection"
        elif not instance.onboarding_step_logistics:
            step = "logistics"
        elif not instance.onboarding_step_financials:
            step = "financials"
        else:
            step = "automations"
        return {
            "name": _("Store Onboarding & Setup Plan - %s") % instance.name,
            "type": "ir.actions.act_window",
            "res_model": "shopify.onboarding.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_instance_id": instance.id,
                "default_current_step": step,
            },
        }

    def _compute_redirect_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for record in self:
            record.redirect_url = f"{base_url}/shopify/oauth/callback"

    @api.model
    def _clean_shop_url(self, url):
        if not url:
            return ""
        cleaned = url.strip()
        if "://" in cleaned:
            cleaned = cleaned.split("://", 1)[1]
        return cleaned.rstrip("/")

    def action_start_oauth(self):
        """Initiates OAuth 2.0 authorization by redirecting user to Shopify consent page."""
        self.ensure_one()
        if not self.shop_url or not self.client_id or not self.client_secret:
            raise UserError(_("Please provide Store URL, Client ID, and Client Secret before initiating OAuth connection."))

        shop = self._clean_shop_url(self.shop_url)
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        redirect_uri = f"{base_url}/shopify/oauth/callback"

        from urllib.parse import urlencode
        params = {
            "client_id": self.client_id.strip(),
            "scope": (self.oauth_scopes or "").strip(),
            "redirect_uri": redirect_uri,
            "state": str(self.id),
        }
        auth_url = f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"
        return {
            "type": "ir.actions.act_url",
            "target": "self",
            "url": auth_url,
        }

    def connect_with_oauth_code(self, code, shop):
        """Exchanges authorization code for permanent offline access token."""
        self.ensure_one()
        import requests
        cleaned_shop = self._clean_shop_url(shop) or self._clean_shop_url(self.shop_url)
        token_url = f"https://{cleaned_shop}/admin/oauth/access_token"
        payload = {
            "client_id": self.client_id.strip(),
            "client_secret": self.client_secret.strip(),
            "code": code.strip(),
        }
        response = requests.post(token_url, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise UserError(_("Shopify did not return an access token: %s") % response.text)

        self.write({
            "access_token": token,
            "state": "confirmed",
        })

        # Auto-discover locations
        try:
            self.action_fetch_locations()
        except Exception as e:
            _logger.warning("Failed to auto-fetch locations after OAuth: %s", str(e))

        # Log history
        self.env["shopify.sync.history"].sudo().create({
            "name": f"OAuth Connected: {self.name}",
            "instance_id": self.id,
            "operation_type": "webhook",
            "entity_type": "instance",
            "status": "success",
            "record_count": 1,
            "message": f"Successfully authenticated via OAuth 2.0 with store {cleaned_shop}.",
        })
        return True

    def _get_or_create_discount_product(self):
        """Finds or creates a service product used for order-level Shopify discount lines."""
        self.ensure_one()
        if self.discount_product_id:
            return self.discount_product_id
        product = self.env["product.product"].search([
            ("default_code", "=", "SHOPIFY-DISCOUNT"),
            ("company_id", "in", [self.company_id.id, False]),
        ], limit=1)
        if not product:
            product = self.env["product.product"].create({
                "name": _("Shopify Discount"),
                "default_code": "SHOPIFY-DISCOUNT",
                "type": "service",
                "invoice_policy": "order",
                "company_id": self.company_id.id,
            })
        self.discount_product_id = product.id
        return product

    def _get_or_create_delivery_product(self):
        """Finds or creates a service product used for Shopify shipping charge lines."""
        self.ensure_one()
        if self.delivery_product_id:
            return self.delivery_product_id
        product = self.env["product.product"].search([
            ("default_code", "=", "SHOPIFY-SHIPPING"),
            ("company_id", "in", [self.company_id.id, False]),
        ], limit=1)
        if not product:
            product = self.env["product.product"].create({
                "name": _("Shopify Shipping & Handling"),
                "default_code": "SHOPIFY-SHIPPING",
                "type": "service",
                "invoice_policy": "order",
                "company_id": self.company_id.id,
            })
        self.delivery_product_id = product.id
        return product

    def _get_payment_journal(self, payment_method_name=None):
        """Resolves payment journal based on method name, configured default, or active bank journal."""
        self.ensure_one()
        if self.payment_journal_id and self.payment_journal_id.company_id == self.company_id:
            return self.payment_journal_id
        journal_model = self.env["account.journal"]
        if payment_method_name:
            clean_name = payment_method_name.strip()
            journal = journal_model.search([
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("name", "=ilike", clean_name),
            ], limit=1)
            if journal:
                return journal
        # Fallback to default bank or cash journal
        return journal_model.search([
            ("company_id", "=", self.company_id.id),
            ("type", "=", "bank"),
        ], limit=1) or journal_model.search([
            ("company_id", "=", self.company_id.id),
            ("type", "in", ("bank", "cash")),
        ], limit=1)

    def get_stock_quantity(self, product, stock_location=None):
        """Calculates accurate available stock quantity for a product at a given stock location."""
        self.ensure_one()
        if not product:
            return 0
        product.invalidate_recordset(["qty_available"])
        loc = stock_location or self.location_id or (self.warehouse_id.lot_stock_id if self.warehouse_id else False)
        if loc:
            domain = [
                ("product_id", "=", product.id),
                ("location_id", "child_of", loc.id),
            ]
            if self.company_id:
                domain.append(("company_id", "in", [self.company_id.id, False]))
            quants = self.env["stock.quant"].search(domain)
            return int(sum(quants.mapped("quantity")))
        return int(product.qty_available)

    def _get_or_create_pricelist_for_currency(self, currency_code=None):
        """Resolves or dynamically creates an active pricelist matching the order currency and instance company."""
        self.ensure_one()
        company = self.company_id or self.env.company
        currency_model = self.env["res.currency"]
        pricelist_model = self.env["product.pricelist"]

        target_currency = False
        if currency_code:
            target_currency = currency_model.search([("name", "=ilike", currency_code.strip())], limit=1)
        if not target_currency:
            target_currency = (self.pricelist_id.currency_id if self.pricelist_id else False) or company.currency_id

        # 1. Check if configured instance pricelist matches target currency and company
        if self.pricelist_id and self.pricelist_id.active:
            if self.pricelist_id.currency_id == target_currency and (not self.pricelist_id.company_id or self.pricelist_id.company_id == company):
                return self.pricelist_id

        # 2. Search active pricelist matching currency and company
        matched_pricelist = pricelist_model.search([
            ("active", "=", True),
            ("currency_id", "=", target_currency.id),
            ("company_id", "in", [company.id, False]),
        ], limit=1)
        if matched_pricelist:
            return matched_pricelist

        # 3. If pricelists are inactive or not configured in Odoo, dynamically create one
        new_pricelist = pricelist_model.sudo().create({
            "name": f"{self.name} - Pricelist ({target_currency.name})",
            "currency_id": target_currency.id,
            "company_id": company.id,
            "active": True,
        })

        if not self.pricelist_id and (not new_pricelist.company_id or new_pricelist.company_id == company):
            self.sudo().write({"pricelist_id": new_pricelist.id})

        return new_pricelist

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("warehouse_id") and not vals.get("company_id"):
                wh = self.env["stock.warehouse"].browse(vals["warehouse_id"])
                vals["company_id"] = wh.company_id.id
            comp_id = vals.get("company_id")
            if comp_id:
                comp = self.env["res.company"].browse(comp_id)
                pl_id = vals.get("pricelist_id")
                pl = self.env["product.pricelist"].browse(pl_id) if pl_id else False
                if not pl or (pl.company_id and pl.company_id != comp):
                    vals["pricelist_id"] = self._get_or_create_default_pricelist(comp).id
        return super().create(vals_list)

    def write(self, vals):
        if "company_id" in vals:
            comp = self.env["res.company"].browse(vals["company_id"])
            pl_id = vals.get("pricelist_id")
            for record in self:
                current_pl = self.env["product.pricelist"].browse(pl_id) if pl_id else record.pricelist_id
                if not current_pl or (current_pl.company_id and current_pl.company_id != comp):
                    vals["pricelist_id"] = self._get_or_create_default_pricelist(comp).id
        return super().write(vals)

    def set_product_pricelist_price(self, product, price):
        """Sets or updates the variant fixed price in the instance's default pricelist.

        Ensures imported Shopify products and variants have their sales price accurately
        reflected in the active pricelist assigned to this Shopify store.
        """
        self.ensure_one()
        if not product or price is None:
            return False

        company = self.company_id or self.env.company
        pricelist = self.pricelist_id
        if not pricelist or (pricelist.company_id and pricelist.company_id != company):
            pricelist = self._get_or_create_pricelist_for_currency()
        if not pricelist:
            return False

        # Support both product.template and product.product
        if product._name == "product.template":
            for variant in product.product_variant_ids:
                self.set_product_pricelist_price(variant, price)
            return True

        # Avoid company crossover errors: product and pricelist must belong to same company (or False)
        prod_comp = product.company_id or product.product_tmpl_id.company_id
        if prod_comp and pricelist.company_id and prod_comp != pricelist.company_id:
            return False

        try:
            price_val = float(price)
        except (ValueError, TypeError):
            price_val = 0.0

        pricelist_item_model = self.env["product.pricelist.item"].with_company(company).sudo()
        item = pricelist_item_model.search([
            ("pricelist_id", "=", pricelist.id),
            ("applied_on", "=", "0_product_variant"),
            ("product_id", "=", product.id),
        ], limit=1)

        if item:
            item.write({"fixed_price": price_val})
        else:
            pricelist_item_model.create({
                "pricelist_id": pricelist.id,
                "applied_on": "0_product_variant",
                "product_id": product.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "fixed_price": price_val,
                "min_quantity": 0,
            })
        return True

    def get_api_client(self):
        """Initializes and returns an instance of ShopifyApiClient."""
        self.ensure_one()
        if not self.shop_url or not self.access_token:
            raise UserError(_("Store URL and Admin API Access Token must be configured (enter directly or connect via OAuth)."))
        return ShopifyApiClient(
            shop_url=self.shop_url,
            access_token=self.access_token,
            api_version=self.api_version,
        )

    def action_test_connection(self):
        """Pings Shopify API to verify credentials and fetches default location."""
        self.ensure_one()
        try:
            client = self.get_api_client()
            shop_data = client.test_connection()
            shop_name = shop_data.get("name", self.name)

            # Auto-discover locations if not set
            if not self.shopify_location_id:
                locations = client.get_locations()
                if locations:
                    self.shopify_location_id = str(locations[0].get("id"))

            self.write({
                "state": "confirmed",
            })

            # Record history entry
            self.env["shopify.sync.history"].create({
                "name": f"Connection Verified: {shop_name}",
                "instance_id": self.id,
                "operation_type": "import",
                "entity_type": "instance",
                "status": "success",
                "message": f"Successfully connected to Shopify Store '{shop_name}' (Domain: {shop_data.get('domain')}, Currency: {shop_data.get('currency')}).",
            })

            return {
                "effect": {
                    "fadeout": "slow",
                    "message": _("🎉 Fantastic! Successfully connected to Shopify Store '%s'!") % shop_name,
                    "type": "rainbow_man",
                }
            }
        except Exception as e:
            self.write({"state": "error"})
            _logger.exception("Shopify connection test failed for instance ID %s", self.id)
            raise UserError(_("Connection test failed: %s") % str(e))

    def action_reset_draft(self):
        """Resets the instance back to draft state."""
        self.ensure_one()
        self.write({"state": "draft"})

    def action_open_sync_wizard(self):
        """Opens manual sync action wizard."""
        self.ensure_one()
        return {
            "name": _("Shopify Synchronization Wizard"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.sync.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_instance_id": self.id,
            },
        }

    def action_open_store_insights(self):
        """Opens the Power BI style Store Insights & Analytics Dashboard for this store."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "shopify_store_insights_dashboard",
            "name": _("%s - Store Insights") % self.name,
            "params": {
                "instance_id": self.id,
                "instance_name": self.name,
            },
            "context": {
                "active_instance_id": self.id,
                "default_instance_id": self.id,
            },
        }

    @api.model
    def get_store_insights_data(self, instance_id=None, period="all"):
        """Computes comprehensive Power BI style analytics metrics for Shopify Store(s)."""
        all_instances = self.search([])
        instances_data = [
            {
                "id": inst.id,
                "name": inst.name,
                "state": inst.state,
                "shop_url": inst.shop_url,
            }
            for inst in all_instances
        ]

        target_instance = None
        if instance_id:
            target_instance = self.browse(int(instance_id)).exists()
        if not target_instance and all_instances:
            target_instance = all_instances.filtered(lambda i: i.state == "confirmed")[:1] or all_instances[:1]

        sel_inst_id = target_instance.id if target_instance else False
        sel_inst_name = target_instance.name if target_instance else _("All Stores")
        sel_inst_state = target_instance.state if target_instance else "draft"
        sel_inst_url = target_instance.shop_url if target_instance else ""

        # Determine Currency Symbol
        currency_symbol = "$"
        if target_instance and target_instance.pricelist_id and target_instance.pricelist_id.currency_id:
            currency_symbol = target_instance.pricelist_id.currency_id.symbol or "$"
        elif target_instance and target_instance.company_id and target_instance.company_id.currency_id:
            currency_symbol = target_instance.company_id.currency_id.symbol or "$"
        elif self.env.company.currency_id:
            currency_symbol = self.env.company.currency_id.symbol or "$"

        # Date domain
        date_limit = None
        now = fields.Datetime.now()
        if period == "7d":
            date_limit = now - timedelta(days=7)
        elif period == "30d":
            date_limit = now - timedelta(days=30)
        elif period == "90d":
            date_limit = now - timedelta(days=90)
        elif period == "year":
            date_limit = now - timedelta(days=365)

        domain = []
        if sel_inst_id:
            domain.append(("instance_id", "=", sel_inst_id))
        if date_limit:
            domain.append(("create_date", ">=", date_limit))

        order_mappings = self.env["shopify.order.mapping"].search(domain, order="create_date desc")

        # Fallback check: If no order mappings exist, check if sale.order records exist with shopify_instance_id
        if not order_mappings and sel_inst_id:
            so_domain = [("shopify_instance_id", "=", sel_inst_id)]
            if date_limit:
                so_domain.append(("date_order", ">=", date_limit))
            direct_sale_orders = self.env["sale.order"].search(so_domain, order="date_order desc")
        else:
            direct_sale_orders = self.env["sale.order"].browse([])

        # Calculate KPIs
        total_orders = len(order_mappings) or len(direct_sale_orders)
        if order_mappings:
            total_sales = sum(order_mappings.mapped("amount_total"))
        elif direct_sale_orders:
            total_sales = sum(direct_sale_orders.mapped("amount_total"))
        else:
            total_sales = 0.0

        aov = (total_sales / total_orders) if total_orders > 0 else 0.0

        # Fulfillment breakdown
        if order_mappings:
            fulfilled_count = len(order_mappings.filtered(lambda o: o.fulfillment_status == "fulfilled"))
            unfulfilled_count = len(order_mappings.filtered(lambda o: o.fulfillment_status in ("unfulfilled", False)))
            partial_count = len(order_mappings.filtered(lambda o: o.fulfillment_status == "partial"))
        else:
            fulfilled_count = len(direct_sale_orders.filtered(lambda o: o.shopify_fulfillment_status == "fulfilled"))
            unfulfilled_count = len(direct_sale_orders.filtered(lambda o: o.shopify_fulfillment_status in ("unfulfilled", False)))
            partial_count = len(direct_sale_orders.filtered(lambda o: o.shopify_fulfillment_status == "partial"))

        fulfillment_rate = round((fulfilled_count / total_orders * 100), 1) if total_orders > 0 else 0.0

        # Financial Status breakdown
        financial_status_counts = {
            "paid": 0,
            "pending": 0,
            "authorized": 0,
            "partially_paid": 0,
            "refunded": 0,
            "voided": 0,
        }
        financial_status_amounts = {
            "paid": 0.0,
            "pending": 0.0,
            "authorized": 0.0,
            "partially_paid": 0.0,
            "refunded": 0.0,
            "voided": 0.0,
        }

        if order_mappings:
            for o in order_mappings:
                st = (o.financial_status or "pending").lower()
                amt = o.amount_total or 0.0
                if st not in financial_status_counts:
                    financial_status_counts[st] = 0
                    financial_status_amounts[st] = 0.0
                financial_status_counts[st] += 1
                financial_status_amounts[st] += amt
        elif direct_sale_orders:
            for so in direct_sale_orders:
                st = (so.shopify_financial_status or "pending").lower()
                amt = so.amount_total or 0.0
                if st not in financial_status_counts:
                    financial_status_counts[st] = 0
                    financial_status_amounts[st] = 0.0
                financial_status_counts[st] += 1
                financial_status_amounts[st] += amt

        fin_labels = []
        fin_counts = []
        fin_amounts = []
        fin_colors = []
        color_palette = {
            "paid": "#10B981",          # Emerald Green
            "pending": "#F59E0B",       # Amber
            "authorized": "#3B82F6",    # Blue
            "partially_paid": "#8B5CF6",# Violet
            "refunded": "#EF4444",      # Rose Red
            "voided": "#64748B",        # Slate
        }
        for st, count in financial_status_counts.items():
            if count > 0:
                fin_labels.append(st.replace("_", " ").title())
                fin_counts.append(count)
                fin_amounts.append(round(financial_status_amounts[st], 2))
                fin_colors.append(color_palette.get(st, "#0284C7"))

        # Fulfillment breakdown chart data
        ful_labels = [_("Fulfilled"), _("Unfulfilled"), _("Partially Fulfilled")]
        ful_counts = [fulfilled_count, unfulfilled_count, partial_count]
        ful_colors = ["#06B6D4", "#6366F1", "#EC4899"]

        # Sales Trend over time
        trend_dict = {}
        target_orders = order_mappings if order_mappings else direct_sale_orders
        for item in reversed(target_orders):
            dt = item.create_date if hasattr(item, "create_date") and item.create_date else False
            if not dt and hasattr(item, "order_id") and item.order_id:
                dt = item.order_id.date_order
            elif not dt and hasattr(item, "date_order"):
                dt = item.date_order
            if not dt:
                continue
            month_key = dt.strftime("%b %Y")
            if month_key not in trend_dict:
                trend_dict[month_key] = {"revenue": 0.0, "orders": 0}
            amt = item.amount_total or 0.0
            trend_dict[month_key]["revenue"] += amt
            trend_dict[month_key]["orders"] += 1

        trend_labels = list(trend_dict.keys())
        trend_revenue = [round(v["revenue"], 2) for v in trend_dict.values()]
        trend_orders = [v["orders"] for v in trend_dict.values()]

        # Top Selling Products and Categories
        top_products = []
        category_dict = {}
        if order_mappings:
            order_ids = order_mappings.mapped("order_id").ids
        else:
            order_ids = direct_sale_orders.ids

        if order_ids:
            lines = self.env["sale.order.line"].search([
                ("order_id", "in", order_ids),
                ("display_type", "=", False),
            ])
            prod_summary = {}
            for line in lines:
                pname = line.product_id.display_name or _("Unknown Product")
                if pname not in prod_summary:
                    prod_summary[pname] = {"qty": 0.0, "revenue": 0.0}
                prod_summary[pname]["qty"] += line.product_uom_qty
                prod_summary[pname]["revenue"] += line.price_total

                categ_name = line.product_id.categ_id.name or _("General")
                category_dict[categ_name] = category_dict.get(categ_name, 0.0) + line.price_total

            sorted_prods = sorted(prod_summary.items(), key=lambda x: x[1]["revenue"], reverse=True)[:6]
            for pname, pdata in sorted_prods:
                top_products.append({
                    "name": pname,
                    "qty": int(pdata["qty"]),
                    "revenue": round(pdata["revenue"], 2),
                    "revenue_formatted": f"{currency_symbol}{round(pdata['revenue'], 2):,.2f}",
                })

        cat_labels = list(category_dict.keys())[:6]
        cat_values = [round(category_dict[k], 2) for k in cat_labels]
        cat_colors = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4"]

        # Catalog Stats
        prod_count = target_instance.product_mapping_count if target_instance else self.env["shopify.template.mapping"].search_count([])
        customer_count = target_instance.customer_mapping_count if target_instance else self.env["shopify.partner.mapping"].search_count([])
        refund_count = target_instance.refund_mapping_count if target_instance else self.env["shopify.refund.mapping"].search_count([])

        # Recent Orders Table
        recent_orders = []
        if order_mappings:
            for o in order_mappings[:10]:
                recent_orders.append({
                    "id": o.id,
                    "order_id": o.order_id.id if o.order_id else False,
                    "shopify_order_number": o.shopify_order_number or f"#{o.id}",
                    "order_name": o.order_id.name if o.order_id else "",
                    "customer_name": o.partner_id.name if o.partner_id else _("Guest Customer"),
                    "date": o.create_date.strftime("%Y-%m-%d %H:%M") if o.create_date else "",
                    "amount": round(o.amount_total or 0.0, 2),
                    "amount_formatted": f"{currency_symbol}{(o.amount_total or 0.0):,.2f}",
                    "financial_status": o.financial_status or "pending",
                    "fulfillment_status": o.fulfillment_status or "unfulfilled",
                })
        elif direct_sale_orders:
            for so in direct_sale_orders[:10]:
                recent_orders.append({
                    "id": so.id,
                    "order_id": so.id,
                    "shopify_order_number": so.shopify_order_number or so.name,
                    "order_name": so.name,
                    "customer_name": so.partner_id.name if so.partner_id else _("Guest Customer"),
                    "date": so.date_order.strftime("%Y-%m-%d %H:%M") if so.date_order else "",
                    "amount": round(so.amount_total or 0.0, 2),
                    "amount_formatted": f"{currency_symbol}{(so.amount_total or 0.0):,.2f}",
                    "financial_status": so.shopify_financial_status or "pending",
                    "fulfillment_status": so.shopify_fulfillment_status or "unfulfilled",
                })

        return {
            "instances": instances_data,
            "selected_instance_id": sel_inst_id,
            "selected_instance_name": sel_inst_name,
            "selected_instance_state": sel_inst_state,
            "selected_instance_url": sel_inst_url,
            "selected_period": period,
            "currency": currency_symbol,
            "kpis": {
                "total_sales": round(total_sales, 2),
                "total_sales_formatted": f"{currency_symbol}{total_sales:,.2f}",
                "total_orders": total_orders,
                "aov": round(aov, 2),
                "aov_formatted": f"{currency_symbol}{aov:,.2f}",
                "fulfillment_rate": fulfillment_rate,
                "fulfilled_count": fulfilled_count,
                "unfulfilled_count": unfulfilled_count,
                "total_products": prod_count,
                "total_customers": customer_count,
                "refund_count": refund_count,
            },
            "sales_trend": {
                "labels": trend_labels,
                "revenue": trend_revenue,
                "orders": trend_orders,
            },
            "financial_breakdown": {
                "labels": fin_labels,
                "counts": fin_counts,
                "amounts": fin_amounts,
                "colors": fin_colors,
            },
            "fulfillment_breakdown": {
                "labels": ful_labels,
                "counts": ful_counts,
                "colors": ful_colors,
            },
            "top_products": top_products,
            "top_categories": {
                "labels": cat_labels,
                "values": cat_values,
                "colors": cat_colors,
            },
            "recent_orders": recent_orders,
        }

    def action_load_sample_insights_data(self, instance_id=None):
        """Maps up to 10 existing demo sale orders to Shopify instance for instant analytics testing."""
        inst = self.browse(instance_id).exists() if instance_id else self.search([("state", "=", "confirmed")], limit=1)
        if not inst:
            inst = self.search([], limit=1)
        if not inst:
            raise UserError(_("No Shopify store instance found to load demo analytics."))

        sale_orders = self.env["sale.order"].search([], limit=12)
        if not sale_orders:
            raise UserError(_("No sale orders found in the database to link as sample analytics."))

        statuses = [
            ("paid", "fulfilled"),
            ("paid", "fulfilled"),
            ("paid", "partial"),
            ("pending", "unfulfilled"),
            ("authorized", "unfulfilled"),
            ("partially_paid", "fulfilled"),
            ("refunded", "restocked"),
            ("paid", "fulfilled"),
            ("paid", "unfulfilled"),
            ("pending", "unfulfilled"),
        ]

        created_count = 0
        order_mapping_model = self.env["shopify.order.mapping"]
        for idx, so in enumerate(sale_orders):
            existing = order_mapping_model.search([
                ("instance_id", "=", inst.id),
                ("order_id", "=", so.id),
            ], limit=1)
            if existing:
                continue

            fin_st, ful_st = statuses[idx % len(statuses)]
            shopify_num = f"#{1001 + idx}"
            so.write({
                "shopify_instance_id": inst.id,
                "shopify_order_id": str(9000100 + idx),
                "shopify_order_number": shopify_num,
                "shopify_financial_status": fin_st,
                "shopify_fulfillment_status": ful_st,
            })
            order_mapping_model.create({
                "instance_id": inst.id,
                "order_id": so.id,
                "shopify_order_id": str(9000100 + idx),
                "shopify_order_number": shopify_num,
                "financial_status": fin_st,
                "fulfillment_status": ful_st,
            })
            created_count += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sample Insights Data Loaded"),
                "message": _("Successfully mapped %s orders with analytics metrics to %s!") % (created_count, inst.name),
                "type": "success",
                "sticky": False,
            },
        }

    # Stat button action helpers
    def action_view_orders(self):
        self.ensure_one()
        return {
            "name": _("Shopify Orders"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.order.mapping",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    def action_view_products(self):
        self.ensure_one()
        return {
            "name": _("Shopify Products"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.template.mapping",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    def action_view_categories(self):
        self.ensure_one()
        return {
            "name": _("Shopify Categories"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.category.mapping",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    def action_view_customers(self):
        self.ensure_one()
        return {
            "name": _("Shopify Customers"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.partner.mapping",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    def _get_or_create_category(self, store_categ_id, categ_title=None, categ_type="custom", handle=None, parent_id=None):
        """Resolves or dynamically creates a product.category and its shopify.category.mapping."""
        self.ensure_one()
        if not store_categ_id:
            return self.env["product.category"]

        store_categ_id_str = str(store_categ_id).strip()
        cat_map_model = self.env["shopify.category.mapping"]
        cat_model = self.env["product.category"]

        mapping = cat_map_model.search([
            ("instance_id", "=", self.id),
            ("shopify_collection_id", "=", store_categ_id_str),
        ], limit=1)
        if mapping:
            if categ_title and mapping.category_id.name != categ_title:
                mapping.category_id.write({"name": categ_title})
                mapping.write({"shopify_collection_title": categ_title})
            return mapping.category_id

        # Search existing product.category by name to avoid duplicate categories in Odoo
        title = (categ_title or f"Collection {store_categ_id_str}").strip()
        category = cat_model.search([("name", "=ilike", title)], limit=1)
        if not category:
            category_vals = {"name": title}
            if parent_id:
                category_vals["parent_id"] = parent_id
            category = cat_model.create(category_vals)

        cat_map_model.create({
            "instance_id": self.id,
            "category_id": category.id,
            "shopify_collection_id": store_categ_id_str,
            "shopify_collection_title": title,
            "shopify_handle": handle or "",
            "shopify_collection_type": categ_type or "custom",
        })
        return category

    def action_view_feeds(self):
        self.ensure_one()
        return {
            "name": _("Shopify Feeds"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.feed",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    def action_view_history(self):
        self.ensure_one()
        return {
            "name": _("Shopify Sync History"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.sync.history",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    def action_view_refunds(self):
        self.ensure_one()
        return {
            "name": _("Shopify Refunds"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.refund.mapping",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    def action_view_locations(self):
        self.ensure_one()
        return {
            "name": _("Shopify Location Mappings"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.location.mapping",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    def action_view_metafields(self):
        self.ensure_one()
        return {
            "name": _("Shopify Metafield Mappings"),
            "type": "ir.actions.act_window",
            "res_model": "shopify.metafield.mapping",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    def action_fetch_locations(self):
        """Fetches active fulfillment locations from Shopify and creates/updates mappings."""
        self.ensure_one()
        client = self.get_api_client()
        locations = client.get_locations()
        loc_map_model = self.env["shopify.location.mapping"]
        
        default_stock_loc = self.location_id or (self.warehouse_id.lot_stock_id if self.warehouse_id else False)
        if not default_stock_loc:
            default_stock_loc = self.env["stock.location"].search([
                ("usage", "=", "internal"),
                ("company_id", "in", [self.company_id.id, False])
            ], limit=1)

        created_count = 0
        for loc in locations:
            loc_id = str(loc.get("id"))
            loc_name = loc.get("name") or f"Location #{loc_id}"
            existing = loc_map_model.search([
                ("instance_id", "=", self.id),
                ("shopify_location_id", "=", loc_id)
            ], limit=1)
            is_primary = (self.shopify_location_id == loc_id) or (not self.shopify_location_id and not created_count)
            if existing:
                existing.write({
                    "shopify_location_name": loc_name,
                    "is_primary": is_primary,
                })
            else:
                loc_map_model.create({
                    "instance_id": self.id,
                    "shopify_location_id": loc_id,
                    "shopify_location_name": loc_name,
                    "warehouse_id": self.warehouse_id.id if self.warehouse_id else False,
                    "location_id": default_stock_loc.id if default_stock_loc else False,
                    "is_primary": is_primary,
                    "sync_stock": True,
                })
                created_count += 1
            if is_primary:
                self.shopify_location_id = loc_id

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Locations Synchronized"),
                "message": _("Discovered and synchronized %d Shopify location(s).") % len(locations),
                "type": "success",
                "sticky": False,
            }
        }

    def _get_metafield_owner_model_map(self):
        return {
            "PRODUCT": "product.template",
            "PRODUCTVARIANT": "product.product",
            "CUSTOMER": "res.partner",
            "ORDER": "sale.order",
        }

    def action_fetch_metafields(self, return_count=False):
        """Fetches Shopify metafield definitions and stages mapping rows."""
        self.ensure_one()
        client = self.get_api_client()
        owner_model_map = self._get_metafield_owner_model_map()
        definitions = client.fetch_metafield_definitions(owner_types=list(owner_model_map))
        mapping_model = self.env["shopify.metafield.mapping"]
        model_map = {
            model.model: model
            for model in self.env["ir.model"].search([("model", "in", list(owner_model_map.values()))])
        }
        count = 0
        for definition in definitions:
            owner_type = definition.get("ownerType")
            model_name = owner_model_map.get(owner_type)
            model = model_map.get(model_name)
            namespace = definition.get("namespace") or "custom"
            key = definition.get("key") or definition.get("name")
            if not model or not key:
                continue
            type_info = definition.get("type") or {}
            metafield_type = type_info.get("name") or type_info.get("category") or "single_line_text_field"
            vals = {
                "instance_id": self.id,
                "model_id": model.id,
                "namespace": namespace,
                "key": key,
                "metafield_type": metafield_type if metafield_type in dict(mapping_model._fields["metafield_type"].selection) else "single_line_text_field",
                "shopify_definition_id": definition.get("id"),
                "shopify_owner_type": owner_type,
                "description": definition.get("description"),
                "active": True,
            }
            mapping = mapping_model.search([
                ("instance_id", "=", self.id),
                ("model_id", "=", model.id),
                ("namespace", "=", namespace),
                ("key", "=", key),
            ], limit=1)
            if mapping:
                update_vals = dict(vals)
                update_vals.pop("active", None)
                mapping.write(update_vals)
            else:
                mapping_model.create(vals)
            count += 1

        if return_count:
            return count
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Metafields Fetched"),
                "message": _("Fetched %d Shopify metafield definition(s). Map Odoo fields as needed.") % count,
                "type": "success",
                "sticky": False,
            }
        }

    @api.model
    def cron_sync_orders(self):
        """Automated scheduled action to import new/updated orders across active stores."""
        instances = self.search([("state", "=", "confirmed"), ("active", "=", True)])
        for instance in instances:
            try:
                wizard = self.env["shopify.sync.wizard"].create({
                    "instance_id": instance.id,
                    "operation_type": "import",
                    "entity_type": "order",
                    "record_limit": 100,
                })
                wizard.action_execute_sync()
            except Exception as e:
                _logger.error("Cron sync orders failed for instance %s: %s", instance.name, str(e))

    @api.model
    def cron_sync_inventory(self):
        """Automated scheduled action to export stock changes to Shopify."""
        instances = self.search([("state", "=", "confirmed"), ("active", "=", True), ("sync_inventory_on_update", "=", True)])
        for instance in instances:
            try:
                wizard = self.env["shopify.sync.wizard"].create({
                    "instance_id": instance.id,
                    "operation_type": "export",
                    "entity_type": "stock",
                })
                wizard.action_execute_sync()
            except Exception as e:
                _logger.error("Cron sync inventory failed for instance %s: %s", instance.name, str(e))

    # -------------------------------------------------------------------------
    # Product Export & Bidirectional Synchronization Helpers
    # -------------------------------------------------------------------------

    def _get_export_option_lines(self, template):
        """Returns attributes configured to create variants for option mapping."""
        return template.attribute_line_ids.filtered(lambda l: l.attribute_id.create_variant != "no_variant")

    def _match_variant_for_shopify_options(self, template, sh_variant):
        """Finds matching product.product variant by comparing option1..option3 values."""
        attribute_lines = self._get_export_option_lines(template)
        if not attribute_lines:
            return template.product_variant_ids[:1]
        expected_values = {}
        for index, line in enumerate(attribute_lines[:3], start=1):
            val = sh_variant.get(f"option{index}")
            if val is not None:
                expected_values[line.attribute_id.id] = val
        if not expected_values:
            return self.env["product.product"]
        for variant in template.product_variant_ids:
            selected_values = {
                ptav.attribute_id.id: ptav.product_attribute_value_id.name
                for ptav in variant.product_template_attribute_value_ids
            }
            if all(selected_values.get(attr_id) == value for attr_id, value in expected_values.items()):
                return variant
        return self.env["product.product"]

    def _prepare_shopify_product_payload(self, template, template_mapping=None, metafields=None, publish=True):
        """Builds REST payload with Shopify options, prices from instance pricelist, and variants."""
        attribute_lines = self._get_export_option_lines(template)
        pricelist = self.pricelist_id
        variants = []
        for variant in template.product_variant_ids:
            selected_values = {
                ptav.attribute_id.id: ptav.product_attribute_value_id.name
                for ptav in variant.product_template_attribute_value_ids
            }
            price_val = variant.list_price
            if pricelist:
                try:
                    price_val = pricelist._get_product_price(variant, 1.0) or variant.list_price
                except Exception:
                    price_val = variant.list_price
            variant_payload = {
                "sku": variant.default_code or f"ODOO-{variant.id}",
                "price": str(price_val),
                "barcode": variant.barcode or "",
            }
            if variant.is_storable:
                variant_payload["inventory_management"] = "shopify"
            for index, line in enumerate(attribute_lines[:3], start=1):
                value = selected_values.get(line.attribute_id.id)
                if value:
                    variant_payload[f"option{index}"] = value
            if template_mapping:
                variant_mapping = template_mapping.variant_mapping_ids.filtered(lambda m: m.product_id == variant)[:1]
                if variant_mapping and variant_mapping.shopify_variant_id:
                    v_id = str(variant_mapping.shopify_variant_id)
                    variant_payload["id"] = int(v_id) if v_id.isdigit() else v_id
            variants.append(variant_payload)

        fallback_price = template.list_price
        if pricelist:
            try:
                first_var = template.product_variant_ids[:1]
                if first_var:
                    fallback_price = pricelist._get_product_price(first_var, 1.0) or template.list_price
            except Exception:
                fallback_price = template.list_price

        fallback_variant = {
            "price": str(fallback_price),
            "sku": template.default_code or f"ODOO-TMPL-{template.id}",
        }
        if template.is_storable:
            fallback_variant["inventory_management"] = "shopify"

        payload = {
            "title": template.name,
            "body_html": template.description_sale or "",
            "variants": variants or [fallback_variant],
        }
        if publish:
            payload["status"] = "active"
        if attribute_lines:
            payload["options"] = [
                {
                    "name": line.attribute_id.name,
                    "values": line.value_ids.mapped("name"),
                }
                for line in attribute_lines[:3]
            ]
        if metafields:
            payload["metafields"] = metafields
        return payload

    def _sync_initial_inventory_to_shopify(self, client, variant_maps):
        """Pushes current Odoo stock quantities to Shopify locations for newly exported variants."""
        synced_count = 0
        variant_maps = variant_maps.filtered(lambda m: m.shopify_inventory_item_id and m.product_id and m.product_id.is_storable)
        if not variant_maps:
            return synced_count

        loc_maps = self.location_mapping_ids.filtered(lambda l: l.sync_stock and l.active and l.location_id)
        if loc_maps:
            for lmap in loc_maps:
                for vmap in variant_maps:
                    qty = self.get_stock_quantity(vmap.product_id, lmap.location_id)
                    try:
                        client.update_inventory_level(
                            inventory_item_id=vmap.shopify_inventory_item_id,
                            location_id=lmap.shopify_location_id,
                            available_qty=qty,
                        )
                        synced_count += 1
                    except Exception as e:
                        _logger.warning("Failed to sync initial inventory for %s at %s: %s", vmap.product_id.display_name, lmap.shopify_location_name, str(e))
        elif self.shopify_location_id:
            stock_location = self.location_id or (self.warehouse_id.lot_stock_id if self.warehouse_id else False)
            for vmap in variant_maps:
                qty = self.get_stock_quantity(vmap.product_id, stock_location)
                try:
                    client.update_inventory_level(
                        inventory_item_id=vmap.shopify_inventory_item_id,
                        location_id=self.shopify_location_id,
                        available_qty=qty,
                    )
                    synced_count += 1
                except Exception as e:
                    _logger.warning("Failed to sync initial inventory for %s: %s", vmap.product_id.display_name, str(e))
        return synced_count

    def _sync_product_metafields_to_shopify(self, client, template, tmpl_map, variant_maps):
        """Pushes configured metafields for template and variants to Shopify."""
        metafield_count = 0
        wizard_helper = self.env["shopify.sync.wizard"]
        if hasattr(wizard_helper, "_collect_record_metafields"):
            tmpl_metafields = wizard_helper._collect_record_metafields(template, "product.template", self)
            for mf in tmpl_metafields:
                try:
                    client.set_metafield("products", tmpl_map.shopify_product_id, mf)
                    metafield_count += 1
                except Exception as e:
                    _logger.warning("Failed to push product metafield %s: %s", mf.get("key"), str(e))

            for vmap in variant_maps.filtered(lambda m: m.shopify_variant_id):
                var_metafields = wizard_helper._collect_record_metafields(vmap.product_id, "product.product", self)
                for mf in var_metafields:
                    try:
                        client.set_metafield("variants", vmap.shopify_variant_id, mf)
                        metafield_count += 1
                    except Exception as e:
                        _logger.warning("Failed to push variant metafield %s: %s", mf.get("key"), str(e))
        return metafield_count

    def _export_single_product(self, template, publish=True):
        """Exports a single product.template to this store instance."""
        self.ensure_one()
        client = self.get_api_client()

        mapping = self.env["shopify.template.mapping"].search([
            ("instance_id", "=", self.id),
            ("template_id", "=", template.id),
        ], limit=1)

        payload = self._prepare_shopify_product_payload(template, template_mapping=mapping, publish=publish)
        resp = client.create_product(payload)
        sh_prod = resp.get("product", {})
        shopify_product_id = str(sh_prod.get("id") or "")
        if not shopify_product_id:
            raise UserError(_("Failed to export product to Shopify. Empty response received."))

        if mapping:
            mapping.write({
                "shopify_product_id": shopify_product_id,
                "shopify_handle": sh_prod.get("handle", ""),
                "shopify_status": "active",
                "is_deleted_on_shopify": False,
            })
            tmpl_map = mapping
        else:
            tmpl_map = self.env["shopify.template.mapping"].create({
                "instance_id": self.id,
                "template_id": template.id,
                "shopify_product_id": shopify_product_id,
                "shopify_handle": sh_prod.get("handle", ""),
                "shopify_status": "active",
                "is_deleted_on_shopify": False,
            })

        new_variant_maps = self.env["shopify.product.mapping"]
        for sh_var in sh_prod.get("variants", []):
            var_sku = sh_var.get("sku")
            matched_var = self._match_variant_for_shopify_options(template, sh_var)
            if not matched_var and var_sku:
                matched_var = template.product_variant_ids.filtered(lambda v: v.default_code == var_sku)[:1]
            if not matched_var:
                matched_var = template.product_variant_ids[:1]
            if matched_var:
                vmap = self.env["shopify.product.mapping"].search([
                    ("instance_id", "=", self.id),
                    ("product_id", "=", matched_var[0].id),
                ], limit=1)
                vals = {
                    "template_mapping_id": tmpl_map.id,
                    "shopify_variant_id": str(sh_var["id"]),
                    "shopify_sku": var_sku or "",
                    "shopify_inventory_item_id": str(sh_var.get("inventory_item_id") or ""),
                }
                if vmap:
                    vmap.write(vals)
                else:
                    vals.update({
                        "instance_id": self.id,
                        "product_id": matched_var[0].id,
                    })
                    vmap = self.env["shopify.product.mapping"].create(vals)
                new_variant_maps |= vmap

        # Link product to collections on Shopify
        target_categories = template.shopify_category_ids or template.categ_id
        for cat in target_categories:
            cat_map = self.env["shopify.category.mapping"].search([
                ("instance_id", "=", self.id),
                ("category_id", "=", cat.id),
            ], limit=1)
            if cat_map and cat_map.shopify_collection_id and not cat_map.shopify_collection_id.startswith("type_"):
                try:
                    client.add_product_to_collection(shopify_product_id, cat_map.shopify_collection_id)
                except Exception:
                    pass

        # Push initial inventory & metafields
        self._sync_initial_inventory_to_shopify(client, new_variant_maps)
        self._sync_product_metafields_to_shopify(client, template, tmpl_map, new_variant_maps)

        self.env["shopify.sync.history"].create({
            "name": f"Exported Product: {template.name}",
            "instance_id": self.id,
            "operation_type": "export",
            "entity_type": "product",
            "status": "success",
            "record_count": 1,
            "message": f"Successfully exported product '{template.name}' to Shopify Store '{self.name}' (Shopify ID: {shopify_product_id}).",
        })

        return tmpl_map

    def _update_product_to_shopify(self, mapping):
        """Pushes latest Odoo product data to Shopify for an existing mapping."""
        self.ensure_one()
        client = self.get_api_client()
        template = mapping.template_id

        payload = self._prepare_shopify_product_payload(template, template_mapping=mapping)
        try:
            resp = client.update_product(mapping.shopify_product_id, payload)
        except Exception as e:
            if isinstance(e, ShopifyNotFoundError) or "404" in str(e) or "Not Found" in str(e):
                mapping.write({
                    "shopify_status": "deleted",
                    "is_deleted_on_shopify": True,
                })
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Product Deleted on Shopify"),
                        "message": _("Product #%s was not found on Shopify (404 Not Found). Marked as Deleted on Shopify.") % mapping.shopify_product_id,
                        "type": "danger",
                        "sticky": True,
                    }
                }
            raise UserError(_("Failed to update product on Shopify: %s") % str(e))

        sh_prod = resp.get("product", {})
        mapping.write({
            "shopify_status": sh_prod.get("status", "active"),
            "is_deleted_on_shopify": False,
            "shopify_handle": sh_prod.get("handle") or mapping.shopify_handle,
        })

        # Update variant mappings if returned
        for sh_var in sh_prod.get("variants", []):
            var_sku = sh_var.get("sku")
            matched_var = self._match_variant_for_shopify_options(template, sh_var)
            if not matched_var and var_sku:
                matched_var = template.product_variant_ids.filtered(lambda v: v.default_code == var_sku)[:1]
            if matched_var:
                vmap = mapping.variant_mapping_ids.filtered(lambda m: m.product_id == matched_var[0])[:1]
                if vmap:
                    vmap.write({
                        "shopify_variant_id": str(sh_var["id"]),
                        "shopify_sku": var_sku or "",
                        "shopify_inventory_item_id": str(sh_var.get("inventory_item_id") or ""),
                    })

        # Link collections
        target_categories = template.shopify_category_ids or template.categ_id
        for cat in target_categories:
            cat_map = self.env["shopify.category.mapping"].search([
                ("instance_id", "=", self.id),
                ("category_id", "=", cat.id),
            ], limit=1)
            if cat_map and cat_map.shopify_collection_id and not cat_map.shopify_collection_id.startswith("type_"):
                try:
                    client.add_product_to_collection(mapping.shopify_product_id, cat_map.shopify_collection_id)
                except Exception:
                    pass

        self._sync_product_metafields_to_shopify(client, template, mapping, mapping.variant_mapping_ids)

        self.env["shopify.sync.history"].create({
            "name": f"Pushed Product to Shopify: {template.name}",
            "instance_id": self.id,
            "operation_type": "export",
            "entity_type": "product",
            "status": "success",
            "record_count": 1,
            "message": f"Updated product '{template.name}' on Shopify store '{self.name}'.",
        })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Product Updated on Shopify"),
                "message": _("Successfully updated product '%s' on Shopify store '%s'.") % (template.name, self.name),
                "type": "success",
                "sticky": False,
            }
        }

    def _update_product_from_shopify(self, mapping):
        """Pulls latest product data from Shopify and synchronizes it into Odoo."""
        self.ensure_one()
        client = self.get_api_client()
        template = mapping.template_id

        try:
            sh_prod = client.fetch_product(mapping.shopify_product_id)
        except Exception as e:
            if isinstance(e, ShopifyNotFoundError) or "404" in str(e) or "Not Found" in str(e):
                mapping.write({
                    "shopify_status": "deleted",
                    "is_deleted_on_shopify": True,
                })
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Product Deleted on Shopify"),
                        "message": _("Product #%s was not found on Shopify (404 Not Found). Marked as Deleted on Shopify.") % mapping.shopify_product_id,
                        "type": "danger",
                        "sticky": True,
                    }
                }
            raise UserError(_("Failed to fetch product from Shopify: %s") % str(e))

        if not sh_prod:
            mapping.write({
                "shopify_status": "deleted",
                "is_deleted_on_shopify": True,
            })
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Product Deleted on Shopify"),
                    "message": _("Product #%s was not found on Shopify. Marked as Deleted on Shopify.") % mapping.shopify_product_id,
                    "type": "danger",
                    "sticky": True,
                }
            }

        # Update status & handle
        mapping.write({
            "shopify_status": sh_prod.get("status", "active"),
            "is_deleted_on_shopify": False,
            "shopify_handle": sh_prod.get("handle") or mapping.shopify_handle,
        })

        # Attach collects & metafields
        try:
            collects = client.fetch_collects(product_id=mapping.shopify_product_id)
            if collects:
                sh_prod["collection_ids"] = [str(c.get("collection_id")) for c in collects if c.get("collection_id")]
        except Exception:
            pass

        try:
            sh_prod["metafields"] = client.fetch_metafields("products", mapping.shopify_product_id)
        except Exception:
            pass

        # Create & process feed to run complete ingestion engine
        feed = self.env["shopify.feed"].create({
            "name": f"Product Update: {sh_prod.get('title', template.name)}",
            "instance_id": self.id,
            "feed_type": "product",
            "external_id": mapping.shopify_product_id,
            "raw_payload": json.dumps(sh_prod),
        })
        feed.action_process_feed()

        self.env["shopify.sync.history"].create({
            "name": f"Pulled Product from Shopify: {template.name}",
            "instance_id": self.id,
            "operation_type": "import",
            "entity_type": "product",
            "status": "success",
            "record_count": 1,
            "message": f"Updated product '{template.name}' in Odoo from Shopify store '{self.name}'.",
        })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Product Updated from Shopify"),
                "message": _("Successfully updated product '%s' in Odoo from Shopify store '%s'.") % (template.name, self.name),
                "type": "success",
                "sticky": False,
            }
        }

    def _check_shopify_product_status(self, mapping):
        """Verifies if a mapped product still exists on Shopify and updates status."""
        self.ensure_one()
        client = self.get_api_client()
        try:
            sh_prod = client.fetch_product(mapping.shopify_product_id)
            if sh_prod:
                status = sh_prod.get("status", "active")
                mapping.write({
                    "shopify_status": status,
                    "is_deleted_on_shopify": False,
                    "shopify_handle": sh_prod.get("handle") or mapping.shopify_handle,
                })
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Shopify Status Checked"),
                        "message": _("Product #%s is Active (%s) on Shopify store '%s'.") % (mapping.shopify_product_id, status, self.name),
                        "type": "success",
                        "sticky": False,
                    }
                }
            else:
                mapping.write({
                    "shopify_status": "deleted",
                    "is_deleted_on_shopify": True,
                })
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Deleted on Shopify"),
                        "message": _("Product #%s was not found on Shopify. Marked as Deleted on Shopify.") % mapping.shopify_product_id,
                        "type": "danger",
                        "sticky": True,
                    }
                }
        except Exception as e:
            if isinstance(e, ShopifyNotFoundError) or "404" in str(e) or "Not Found" in str(e):
                mapping.write({
                    "shopify_status": "deleted",
                    "is_deleted_on_shopify": True,
                })
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Deleted on Shopify"),
                        "message": _("Product #%s does not exist on Shopify store '%s' (404 Not Found). Marked as Deleted.") % (mapping.shopify_product_id, self.name),
                        "type": "danger",
                        "sticky": True,
                    }
                }
            raise UserError(_("Error checking product status on Shopify: %s") % str(e))
