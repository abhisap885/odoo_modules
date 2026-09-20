from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    product_variant_stock_visibility_enabled = fields.Boolean(
        string='Grey Out Out-of-Stock Variant Options',
        default=True,
        help='On the shop product page, grey out, strike through and disable '
             'attribute value options that would resolve to an out-of-stock variant.',
    )
