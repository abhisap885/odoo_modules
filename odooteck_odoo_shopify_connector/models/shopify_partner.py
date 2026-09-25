# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class ResPartner(models.Model):
    _inherit = "res.partner"

    shopify_customer_mapping_ids = fields.One2many(
        "shopify.partner.mapping",
        "partner_id",
        string="Shopify Customer Mappings",
        readonly=True,
    )
