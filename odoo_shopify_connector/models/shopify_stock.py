# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    shopify_fulfillment_synced = fields.Boolean(
        string="Shopify Fulfillment Synced",
        default=False,
        copy=False,
    )

    def button_validate(self):
        """Overrides validate button to push fulfillment tracking numbers to Shopify."""
        res = super(StockPicking, self).button_validate()
        for picking in self:
            if picking.state == "done" and picking.sale_id and not picking.shopify_fulfillment_synced:
                order_map = self.env["shopify.order.mapping"].search([
                    ("order_id", "=", picking.sale_id.id)
                ], limit=1)
                if order_map:
                    picking._push_shopify_fulfillment(order_map)
        return res

    def _push_shopify_fulfillment(self, order_map):
        self.ensure_one()
        instance = order_map.instance_id
        if instance.state != "confirmed":
            return
        try:
            client = instance.get_api_client()
            tracking_number = getattr(self, "carrier_tracking_ref", "") or (self.origin or "")
            carrier = getattr(self, "carrier_id", False)
            carrier_name = carrier.name if carrier else ""

            client.create_fulfillment(
                order_id=order_map.shopify_order_id,
                tracking_number=tracking_number,
                tracking_company=carrier_name,
            )
            self.shopify_fulfillment_synced = True
            order_map.fulfillment_status = "fulfilled"

            self.env["shopify.sync.history"].create({
                "name": f"Fulfillment Synced for {self.name}",
                "instance_id": instance.id,
                "operation_type": "export",
                "entity_type": "order",
                "status": "success",
                "message": f"Successfully updated fulfillment for Shopify Order #{order_map.shopify_order_number} (Tracking: {tracking_number}).",
            })
        except Exception as e:
            _logger.exception("Failed to sync fulfillment to Shopify for picking %s: %s", self.name, str(e))
            self.env["shopify.sync.history"].create({
                "name": f"Fulfillment Failed for {self.name}",
                "instance_id": instance.id,
                "operation_type": "export",
                "entity_type": "order",
                "status": "warning",
                "message": f"Could not sync fulfillment: {str(e)}",
            })


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, *args, **kwargs):
        res = super()._action_done(*args, **kwargs)
        res._shopify_sync_inventory_after_done()
        return res

    def _shopify_location_contains(self, location, root_location):
        if not location or not root_location:
            return False
        return bool(self.env["stock.location"].search_count([
            ("id", "=", location.id),
            ("id", "child_of", root_location.id),
        ]))

    def _shopify_move_touches_location(self, move, stock_location):
        return (
            self._shopify_location_contains(move.location_id, stock_location)
            or self._shopify_location_contains(move.location_dest_id, stock_location)
        )

    def _shopify_move_is_from_instance_order(self, move, instance):
        sale_order = move.sale_line_id.order_id if move.sale_line_id else False
        if not sale_order and move.origin:
            sale_order = self.env["sale.order"].search([("name", "=", move.origin)], limit=1)
        if not sale_order:
            return False
        return bool(self.env["shopify.order.mapping"].search([
            ("instance_id", "=", instance.id),
            ("order_id", "=", sale_order.id),
        ], limit=1))

    def _shopify_primary_stock_location(self, instance):
        stock_location = instance.location_id or (instance.warehouse_id.lot_stock_id if instance.warehouse_id else False)
        if not stock_location:
            stock_location = self.env["stock.location"].search([
                ("usage", "=", "internal"),
                ("company_id", "in", [instance.company_id.id, False]),
            ], limit=1)
        return stock_location

    def _shopify_sync_inventory_after_done(self):
        if self.env.context.get("skip_shopify_realtime_inventory"):
            return

        product_map_model = self.env["shopify.product.mapping"]
        jobs = {}

        for move in self:
            product = move.product_id
            if not product or not product.is_storable:
                continue

            variant_maps = product_map_model.search([
                ("product_id", "=", product.id),
                ("shopify_inventory_item_id", "!=", False),
            ])
            for vmap in variant_maps:
                instance = vmap.instance_id
                if not instance.active or instance.state != "confirmed" or not instance.sync_inventory_on_update:
                    continue
                if move.picking_type_id.code == "outgoing" and self._shopify_move_is_from_instance_order(move, instance):
                    continue

                loc_maps = instance.location_mapping_ids.filtered(lambda l: l.sync_stock and l.active and l.location_id)
                if loc_maps:
                    for lmap in loc_maps:
                        if self._shopify_move_touches_location(move, lmap.location_id):
                            jobs[(vmap.id, lmap.id)] = (vmap, lmap)
                elif instance.shopify_location_id:
                    stock_location = self._shopify_primary_stock_location(instance)
                    if self._shopify_move_touches_location(move, stock_location):
                        jobs[(vmap.id, False)] = (vmap, False)

        if jobs:
            self._shopify_run_inventory_sync_jobs(list(jobs.values()))

    def _shopify_run_inventory_sync_jobs(self, jobs):
        history_model = self.env["shopify.sync.history"]
        success_by_instance = {}
        errors_by_instance = {}
        clients = {}

        for vmap, lmap in jobs:
            instance = vmap.instance_id
            if instance.id not in clients:
                clients[instance.id] = instance.get_api_client()
            client = clients[instance.id]
            location_id = lmap.shopify_location_id if lmap else instance.shopify_location_id
            if not location_id:
                _logger.warning("No Shopify location found for instance %s while syncing variant %s", instance.name, vmap.product_id.display_name)
                continue
            target_stock_location = lmap.location_id if lmap else self._shopify_primary_stock_location(instance)
            qty = instance.get_stock_quantity(vmap.product_id, target_stock_location)
            try:
                client.update_inventory_level(
                    inventory_item_id=vmap.shopify_inventory_item_id,
                    location_id=location_id,
                    available_qty=qty,
                )
                success_by_instance[instance] = success_by_instance.get(instance, 0) + 1
            except Exception as e:
                _logger.warning(
                    "Failed to sync real-time Shopify inventory for %s at location %s: %s",
                    vmap.product_id.display_name,
                    lmap.shopify_location_name if lmap else instance.shopify_location_id,
                    str(e),
                )
                errors_by_instance.setdefault(instance, []).append("%s: %s" % (vmap.product_id.display_name, str(e)))

        for instance, count in success_by_instance.items():
            instance.last_inventory_sync = fields.Datetime.now()
            history_model.create({
                "name": f"Real-time Inventory Synced ({count} items)",
                "instance_id": instance.id,
                "operation_type": "export",
                "entity_type": "stock",
                "status": "success",
                "record_count": count,
                "message": f"Updated Shopify stock for {count} product-location combination(s) after Odoo stock movement.",
            })

        for instance, errors in errors_by_instance.items():
            history_model.create({
                "name": "Real-time Inventory Sync Failed",
                "instance_id": instance.id,
                "operation_type": "export",
                "entity_type": "stock",
                "status": "warning",
                "record_count": len(errors),
                "message": "\n".join(errors[:5]),
            })
