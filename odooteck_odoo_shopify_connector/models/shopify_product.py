# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck.
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _

class ProductTemplate(models.Model):
    _inherit = "product.template"

    shopify_template_mapping_ids = fields.One2many(
        "shopify.template.mapping",
        "template_id",
        string="Shopify Product Mappings",
        readonly=True,
    )
    shopify_metafield_value_ids = fields.One2many(
        "shopify.metafield.value",
        "product_tmpl_id",
        string="Shopify Metafields",
        domain=[("model_name", "=", "product.template")],
        copy=False,
    )
    shopify_category_ids = fields.Many2many(
        "product.category",
        "product_template_shopify_category_rel",
        "product_tmpl_id",
        "categ_id",
        string="Shopify Collections",
        help="All Shopify collections/categories this product belongs to.",
    )

    def action_shopify_export_product(self):
        """Opens wizard to export this product to a selected Shopify store."""
        self.ensure_one()
        mapped_instance_ids = self.shopify_template_mapping_ids.filtered(lambda m: not m.is_deleted_on_shopify).mapped("instance_id.id")
        unmapped_instances = self.env["shopify.instance"].search([
            ("state", "=", "confirmed"),
            ("id", "not in", mapped_instance_ids),
        ])
        default_instance = unmapped_instances[:1] or self.env["shopify.instance"].search([("state", "=", "confirmed")], limit=1)

        return {
            "type": "ir.actions.act_window",
            "name": _("Export Product to Shopify"),
            "res_model": "shopify.product.export.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_template_id": self.id,
                "default_instance_id": default_instance.id if default_instance else False,
            },
        }

class ProductProduct(models.Model):
    _inherit = "product.product"

    shopify_variant_mapping_ids = fields.One2many(
        "shopify.product.mapping",
        "product_id",
        string="Shopify Variant Mappings",
        readonly=True,
    )
    shopify_metafield_value_ids = fields.One2many(
        "shopify.metafield.value",
        "product_id",
        string="Shopify Metafields",
        domain=[("model_name", "=", "product.product")],
        copy=False,
    )

class ProductCategory(models.Model):
    _inherit = "product.category"

    shopify_category_mapping_ids = fields.One2many(
        "shopify.category.mapping",
        "category_id",
        string="Shopify Collection Mappings",
        readonly=True,
    )
