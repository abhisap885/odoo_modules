from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _is_stock_visibility_enabled(self):
        website = self.website_id or self.env['website'].get_current_website()
        return website.product_variant_stock_visibility_enabled

    def _get_out_of_stock_attribute_value_ids(self, combination):
        """Return the product.template.attribute.value records that would
        resolve to an out-of-stock variant, given the currently selected
        ``combination`` (a partial or full product.template.attribute.value
        recordset for this template).

        A value on a given attribute line is out of stock when every
        existing variant that matches it together with the values already
        selected on the *other* lines has no free quantity and the template
        does not allow selling out of stock.
        """
        self.ensure_one()
        out_of_stock = self.env['product.template.attribute.value']
        if not self._is_stock_visibility_enabled():
            return out_of_stock
        if not self.is_storable:
            return out_of_stock

        # Called from a public (anonymous shopper) route: reading stock levels
        # requires Inventory access, which public/portal users don't have.
        template = self.sudo()

        # no_variant values never appear on any variant's combination, so leaving
        # them in would make the subset check below fail for every other line.
        combination = combination._without_no_variant_attributes()

        for line in template.attribute_line_ids:
            other_selected = combination.filtered(lambda p, line=line: p.attribute_line_id != line)
            for ptav in line.product_template_value_ids:
                if not ptav.ptav_active:
                    continue
                trial_ids = set(other_selected.ids) | {ptav.id}
                variants = template.product_variant_ids.filtered(
                    lambda v, trial_ids=trial_ids: trial_ids <= set(v.product_template_attribute_value_ids.ids)
                )
                if not variants:
                    # No existing variant matches this value with the current
                    # selection: nothing to flag as out of stock here, the
                    # combination is simply not producible (handled elsewhere).
                    continue
                in_stock = any(
                    template.allow_out_of_stock_order or variant.free_qty > 0
                    for variant in variants
                )
                if not in_stock:
                    out_of_stock |= ptav
        return out_of_stock
