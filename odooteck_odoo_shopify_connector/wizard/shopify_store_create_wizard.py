# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ShopifyStoreCreateWizard(models.TransientModel):
    _name = "shopify.store.create.wizard"
    _description = "Quick Create Shopify Store Wizard"

    @api.model
    def _default_warehouse_id(self):
        wh = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        if not wh:
            wh = self.env["stock.warehouse"].search([], limit=1)
        return wh

    @api.model
    def _default_company_id(self):
        wh = self._default_warehouse_id()
        return wh.company_id if wh else self.env.company

    @api.model
    def _default_pricelist_id(self):
        company = self._default_company_id()
        pricelist = self.env["product.pricelist"].search([
            ("active", "=", True),
            ("company_id", "in", [company.id, False]),
        ], limit=1)
        return pricelist

    name = fields.Char(string="Store Name", required=True, default="My Shopify Store")
    shop_url = fields.Char(
        string="Shopify Store URL",
        required=True,
        help="The primary URL of your Shopify store (e.g. https://my-brand.myshopify.com).",
    )
    auth_method = fields.Selection(
        [
            ("token", "Admin API Access Token (Recommended)"),
            ("oauth", "Shopify OAuth 2.0 (Custom App)"),
        ],
        string="Authentication Method",
        default="token",
        required=True,
    )
    access_token = fields.Char(
        string="Admin API Access Token",
        help="Access token copied from your Shopify Custom App (starts with shpat_).",
    )
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
        required=True,
    )
    client_id = fields.Char(string="Client ID (API Key)")
    client_secret = fields.Char(string="Client Secret")

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
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Default Pricelist",
        default=_default_pricelist_id,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    test_connection_now = fields.Boolean(
        string="Test & Connect Immediately",
        default=True,
        help="If checked, the connector will authenticate with Shopify right away upon store creation.",
    )

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        if self.warehouse_id and self.warehouse_id.company_id and self.warehouse_id.company_id != self.company_id:
            self.company_id = self.warehouse_id.company_id

    def action_create_store(self):
        """Creates the Shopify store instance, optionally tests connection, and stays on kanban view."""
        self.ensure_one()

        if self.auth_method == "token" and not self.access_token:
            raise ValidationError(_("Please provide the Admin API Access Token before creating the store."))

        vals = {
            "name": self.name.strip(),
            "shop_url": self.shop_url.strip(),
            "auth_method": self.auth_method,
            "access_token": self.access_token.strip() if self.access_token else False,
            "api_version": self.api_version,
            "client_id": self.client_id.strip() if self.client_id else False,
            "client_secret": self.client_secret.strip() if self.client_secret else False,
            "warehouse_id": self.warehouse_id.id,
            "company_id": self.company_id.id,
        }
        if self.pricelist_id:
            vals["pricelist_id"] = self.pricelist_id.id

        instance = self.env["shopify.instance"].create(vals)

        # Immediate Connection Verification
        if self.test_connection_now and instance.auth_method == "token" and instance.access_token:
            try:
                instance.action_test_connection()
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Shopify Store Connected & Live!"),
                        "message": _("Store '%s' successfully created and connected to Shopify.") % instance.name,
                        "type": "success",
                        "sticky": False,
                        "next": {"type": "ir.actions.act_window_close"},
                    },
                }
            except Exception as e:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Store Created as Draft"),
                        "message": _("Store '%s' created in draft state. Connection test note: %s") % (instance.name, str(e)),
                        "type": "warning",
                        "sticky": True,
                        "next": {"type": "ir.actions.act_window_close"},
                    },
                }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Shopify Store Created"),
                "message": _("Store '%s' successfully created! Use the Setup Plan to configure credentials.") % instance.name,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
