# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class ShopifySyncHistory(models.Model):
    _name = "shopify.sync.history"
    _description = "Shopify Synchronization History & Audit Log"
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Operation Summary", required=True)

    @api.depends("name", "operation_type", "entity_type")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or f"{rec.operation_type or 'Sync'} - {rec.entity_type or 'Log'} #{rec.id}"
    instance_id = fields.Many2one("shopify.instance", string="Shopify Store", required=True, ondelete="cascade")
    operation_type = fields.Selection(
        selection=[
            ("import", "Data Import"),
            ("export", "Data Export"),
            ("webhook", "Real-Time Webhook"),
        ],
        string="Action Type",
        required=True,
    )
    entity_type = fields.Selection(
        selection=[
            ("order", "Sales Orders"),
            ("product", "Products & Variants"),
            ("category", "Categories / Collections"),
            ("customer", "Customers"),
            ("stock", "Inventory Levels"),
            ("metafield", "Metafield Definitions"),
            ("instance", "Store Connection"),
        ],
        string="Resource Entity",
        required=True,
    )
    status = fields.Selection(
        selection=[
            ("success", "Success"),
            ("warning", "Warning"),
            ("failed", "Failed"),
        ],
        string="Status",
        default="success",
        required=True,
    )
    record_count = fields.Integer(string="Processed Records", default=0)
    message = fields.Text(string="Log Details")
