from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    product_variant_stock_visibility_enabled = fields.Boolean(
        related='website_id.product_variant_stock_visibility_enabled',
        readonly=False,
    )
