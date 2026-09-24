# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    shopify_instance_id = fields.Many2one("shopify.instance", string="Shopify Store", copy=False)
    shopify_order_id = fields.Char(string="Shopify Order ID", copy=False, index=True)
    shopify_order_number = fields.Char(string="Shopify Order #", copy=False)
    shopify_financial_status = fields.Char(string="Shopify Financial Status", copy=False)
    shopify_fulfillment_status = fields.Char(string="Shopify Fulfillment Status", copy=False)

    shopify_mapping_ids = fields.One2many(
        "shopify.order.mapping",
        "order_id",
        string="Shopify Order Mappings",
        readonly=True,
    )
