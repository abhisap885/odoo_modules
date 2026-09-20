from odoo import http
from odoo.http import request


class ProductVariantStockVisibilityController(http.Controller):

    @http.route(
        '/website_sale/get_out_of_stock_values',
        type='json', auth='public', website=True, methods=['POST'],
    )
    def get_out_of_stock_values(self, product_template_id, combination_ids=None):
        """Return the attribute value ids that would resolve to an
        out-of-stock variant given the currently selected combination.
        """
        template = request.env['product.template'].browse(int(product_template_id)).exists()
        if not template:
            return {'out_of_stock_value_ids': []}
        combination = request.env['product.template.attribute.value'].browse(
            [int(i) for i in (combination_ids or [])]
        ).exists()
        out_of_stock = template._get_out_of_stock_attribute_value_ids(combination)
        return {'out_of_stock_value_ids': out_of_stock.ids}
