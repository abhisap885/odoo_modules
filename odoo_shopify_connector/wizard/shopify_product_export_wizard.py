# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ShopifyProductExportWizard(models.TransientModel):
    _name = "shopify.product.export.wizard"
    _description = "Export Single Product to Shopify Store"

    template_id = fields.Many2one("product.template", string="Product Template", required=True, readonly=True)
    instance_id = fields.Many2one(
        "shopify.instance",
        string="Shopify Store",
        required=True,
        domain=[("state", "=", "confirmed")],
    )
    publish = fields.Boolean(
        string="Publish on Shopify",
        default=True,
        help="If checked, the product will be set to 'active' on Shopify. Otherwise it will be saved as 'draft'.",
    )

    def action_export_product(self):
        self.ensure_one()
        instance = self.instance_id
        template = self.template_id

        # Check existing active mapping
        existing_mapping = self.env["shopify.template.mapping"].search([
            ("instance_id", "=", instance.id),
            ("template_id", "=", template.id),
        ], limit=1)

        if existing_mapping and not existing_mapping.is_deleted_on_shopify:
            raise UserError(
                _("This product is already mapped to '%s' (Shopify ID: %s).\n"
                  "Please use the 'Odoo to Shopify' update button in the mappings list to push changes.")
                % (instance.name, existing_mapping.shopify_product_id)
            )

        tmpl_map = instance._export_single_product(template, publish=self.publish)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Product Exported"),
                "message": _("Product '%s' successfully exported to Shopify store '%s' (Shopify ID: %s).")
                           % (template.name, instance.name, tmpl_map.shopify_product_id),
                "type": "success",
                "sticky": False,
            }
        }
