# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

import json
from odoo.tests.common import TransactionCase
from odoo.tests import tagged

@tagged("post_install", "-at_install")
class TestShopifyConnector(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.company.id)], limit=1)

        # 1. Create Shopify Store Instance
        self.instance = self.env["shopify.instance"].create({
            "name": "Test Shopify Store",
            "shop_url": "https://unit-test.myshopify.com",
            "access_token": "shpat_test_secret_token",
            "api_version": "2025-01",
            "warehouse_id": self.warehouse.id,
            "company_id": self.company.id,
        })

    def test_01_instance_initialization(self):
        """Verify instance defaults and state."""
        self.assertEqual(self.instance.state, "draft")
        self.assertTrue(self.instance.active)
        self.assertEqual(self.instance.order_mapping_count, 0)
        self.assertEqual(self.instance.customer_mapping_count, 0)

    def test_02_customer_feed_processing(self):
        """Simulate incoming customer feed and verify partner mapping."""
        customer_payload = {
            "id": 987654321,
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "phone": "+1234567890",
        }

        feed = self.env["shopify.feed"].create({
            "name": "Customer Feed #987654321",
            "instance_id": self.instance.id,
            "feed_type": "customer",
            "external_id": "987654321",
            "raw_payload": json.dumps(customer_payload),
        })

        feed.action_process_feed()
        self.assertEqual(feed.state, "done")
        self.assertTrue(feed.partner_id)
        self.assertEqual(feed.partner_id.name, "Jane Doe")
        self.assertEqual(feed.partner_id.email, "jane.doe@example.com")

        # Verify mapping
        mapping = self.env["shopify.partner.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_customer_id", "=", "987654321")
        ])
        self.assertTrue(mapping)
        self.assertEqual(mapping.partner_id.id, feed.partner_id.id)
        self.assertEqual(self.instance.customer_mapping_count, 1)

        # Test customer action view
        action_cust = self.instance.action_view_customers()
        self.assertEqual(action_cust.get("res_model"), "shopify.partner.mapping")

    def test_03_product_feed_processing(self):
        """Simulate incoming product feed and verify template & variant mapping."""
        product_payload = {
            "id": 1122334455,
            "title": "Shopify Premium Hoodie",
            "handle": "shopify-premium-hoodie",
            "body_html": "<p>Comfortable cotton hoodie.</p>",
            "variants": [
                {
                    "id": 5544332211,
                    "sku": "HOODIE-BLK-M",
                    "price": "49.99",
                    "inventory_item_id": 99887766,
                }
            ],
        }

        feed = self.env["shopify.feed"].create({
            "name": "Product Feed #1122334455",
            "instance_id": self.instance.id,
            "feed_type": "product",
            "external_id": "1122334455",
            "raw_payload": json.dumps(product_payload),
        })

        feed.action_process_feed()
        self.assertEqual(feed.state, "done")
        self.assertTrue(feed.template_id)
        self.assertEqual(feed.template_id.name, "Shopify Premium Hoodie")

        # Verify Template Mapping
        tmpl_map = self.env["shopify.template.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_product_id", "=", "1122334455")
        ])
        self.assertTrue(tmpl_map)

        # Verify Variant Mapping
        var_map = self.env["shopify.product.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_variant_id", "=", "5544332211")
        ])
        self.assertTrue(var_map)
        self.assertEqual(var_map.shopify_sku, "HOODIE-BLK-M")

        # Verify Price in Default Pricelist
        self.assertTrue(self.instance.pricelist_id)
        pl_item = self.env["product.pricelist.item"].search([
            ("pricelist_id", "=", self.instance.pricelist_id.id),
            ("product_id", "=", var_map.product_id.id),
        ])
        self.assertTrue(pl_item)
        self.assertEqual(pl_item.fixed_price, 49.99)

    def test_03b_product_feed_reuses_existing_product_mapping(self):
        """A changed Shopify variant ID must update, not duplicate, a mapping."""
        payload = {
            "id": 1122334499,
            "title": "Shopify Replacement Variant",
            "variants": [{
                "id": 5544332299,
                "sku": "REPLACEMENT-SKU",
                "price": "29.99",
                "inventory_item_id": 99887799,
            }],
        }
        feed = self.env["shopify.feed"].create({
            "name": "Product Feed #1122334499",
            "instance_id": self.instance.id,
            "feed_type": "product",
            "external_id": "1122334499",
            "raw_payload": json.dumps(payload),
        })
        feed.action_process_feed()
        mapping = self.env["shopify.product.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_variant_id", "=", "5544332299"),
        ], limit=1)
        mapping.write({"shopify_variant_id": "obsolete-variant-id"})

        feed.write({"state": "draft"})
        feed.action_process_feed()

        self.assertEqual(feed.state, "done")
        self.assertEqual(mapping.shopify_variant_id, "5544332299")
        self.assertEqual(self.env["shopify.product.mapping"].search_count([
            ("instance_id", "=", self.instance.id),
            ("product_id", "=", mapping.product_id.id),
        ]), 1)

    def test_03c_product_options_create_variants_and_mappings(self):
        """Shopify option combinations must create distinct Odoo variants."""
        payload = {
            "id": 1122334500,
            "title": "Variant Product",
            "options": [
                {"name": "Size", "values": ["S", "M"]},
                {"name": "Colour", "values": ["Red"]},
            ],
            "variants": [
                {"id": 5544332300, "option1": "S", "option2": "Red", "sku": "S-RED", "price": "20"},
                {"id": 5544332301, "option1": "M", "option2": "Red", "sku": "M-RED", "price": "25"},
            ],
        }
        feed = self.env["shopify.feed"].create({
            "name": "Variant Product Feed",
            "instance_id": self.instance.id,
            "feed_type": "product",
            "external_id": "1122334500",
            "raw_payload": json.dumps(payload),
        })
        feed.action_process_feed()

        self.assertEqual(feed.state, "done")
        self.assertEqual(len(feed.template_id.product_variant_ids), 2)
        self.assertTrue(feed.template_id.is_storable)
        mappings = self.env["shopify.product.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("template_mapping_id", "=", self.env["shopify.template.mapping"].search([
                ("instance_id", "=", self.instance.id),
                ("shopify_product_id", "=", "1122334500"),
            ], limit=1).id),
        ])
        self.assertEqual(len(mappings), 2)
        self.assertEqual(len(mappings.mapped("product_id")), 2)

        wizard = self.env["shopify.sync.wizard"].create({"instance_id": self.instance.id})
        export_payload = wizard._prepare_shopify_product_payload(feed.template_id)
        self.assertEqual(export_payload["options"], [
            {"name": "Size", "values": ["S", "M"]},
            {"name": "Colour", "values": ["Red"]},
        ])
        self.assertEqual({variant["option1"] for variant in export_payload["variants"]}, {"S", "M"})
        map_s = mappings.filtered(lambda m: m.shopify_sku == "S-RED")
        map_m = mappings.filtered(lambda m: m.shopify_sku == "M-RED")
        pl_item_s = self.env["product.pricelist.item"].search([
            ("pricelist_id", "=", self.instance.pricelist_id.id),
            ("product_id", "=", map_s.product_id.id),
        ])
        pl_item_m = self.env["product.pricelist.item"].search([
            ("pricelist_id", "=", self.instance.pricelist_id.id),
            ("product_id", "=", map_m.product_id.id),
        ])
        self.assertTrue(pl_item_s)
        self.assertEqual(pl_item_s.fixed_price, 20.0)
        self.assertTrue(pl_item_m)
        self.assertEqual(pl_item_m.fixed_price, 25.0)
        self.assertEqual({variant["price"] for variant in export_payload["variants"]}, {"20.0", "25.0"})

    def test_03d_product_export_maps_variants_by_options_without_sku(self):
        """First export must map Shopify variants back to matching Odoo option combinations."""
        from unittest.mock import patch
        self.instance.write({"state": "confirmed"})
        self.env["product.template"].search([("sale_ok", "=", True)]).write({"sale_ok": False})
        attr_size = self.env["product.attribute"].create({"name": "Export Size", "create_variant": "always"})
        val_s = self.env["product.attribute.value"].create({"name": "S", "attribute_id": attr_size.id})
        val_m = self.env["product.attribute.value"].create({"name": "M", "attribute_id": attr_size.id})
        attr_colour = self.env["product.attribute"].create({"name": "Export Colour", "create_variant": "always"})
        val_red = self.env["product.attribute.value"].create({"name": "Red", "attribute_id": attr_colour.id})
        tmpl = self.env["product.template"].create({
            "name": "No SKU Variant Export",
            "sale_ok": True,
            "attribute_line_ids": [
                (0, 0, {"attribute_id": attr_size.id, "value_ids": [(6, 0, [val_s.id, val_m.id])]}),
                (0, 0, {"attribute_id": attr_colour.id, "value_ids": [(6, 0, [val_red.id])]}),
            ],
        })
        tmpl._create_variant_ids()

        wizard = self.env["shopify.sync.wizard"].create({
            "instance_id": self.instance.id,
            "operation_type": "export",
            "entity_type": "product",
            "record_limit": 1,
        })
        create_response = {
            "product": {
                "id": 1122334900,
                "handle": "no-sku-variant-export",
                "variants": [
                    {"id": 5544332701, "sku": "", "option1": "M", "option2": "Red", "inventory_item_id": 66554502},
                    {"id": 5544332700, "sku": "", "option1": "S", "option2": "Red", "inventory_item_id": 66554501},
                ],
            }
        }

        with patch.object(type(self.instance.get_api_client()), "create_product", return_value=create_response) as mocked_create:
            wizard.action_execute_sync()

        payload = mocked_create.call_args.args[0]
        self.assertEqual(payload["options"], [
            {"name": "Export Size", "values": ["S", "M"]},
            {"name": "Export Colour", "values": ["Red"]},
        ])
        self.assertEqual(
            {(variant.get("option1"), variant.get("option2")) for variant in payload["variants"]},
            {("S", "Red"), ("M", "Red")},
        )

        mapping_s = self.env["shopify.product.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_variant_id", "=", "5544332700"),
        ], limit=1)
        mapping_m = self.env["shopify.product.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_variant_id", "=", "5544332701"),
        ], limit=1)
        self.assertTrue(mapping_s)
        self.assertTrue(mapping_m)
        self.assertNotEqual(mapping_s.product_id, mapping_m.product_id)
        self.assertEqual(
            set(mapping_s.product_id.product_template_attribute_value_ids.mapped("product_attribute_value_id.name")),
            {"S", "Red"},
        )
        self.assertEqual(
            set(mapping_m.product_id.product_template_attribute_value_ids.mapped("product_attribute_value_id.name")),
            {"M", "Red"},
        )

    def test_04_order_feed_processing(self):
        """Simulate incoming sales order feed and verify sale.order creation."""
        order_payload = {
            "id": 99881122,
            "order_number": 1001,
            "name": "#1001",
            "financial_status": "paid",
            "fulfillment_status": "unfulfilled",
            "customer": {
                "id": 987654321,
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane.doe@example.com",
            },
            "line_items": [
                {
                    "id": 776655,
                    "variant_id": 5544332211,
                    "name": "Shopify Premium Hoodie - M",
                    "quantity": 2,
                    "price": "49.99",
                    "sku": "HOODIE-BLK-M",
                }
            ],
        }

        feed = self.env["shopify.feed"].create({
            "name": "Order Feed #1001",
            "instance_id": self.instance.id,
            "feed_type": "order",
            "external_id": "99881122",
            "raw_payload": json.dumps(order_payload),
        })

        feed.action_process_feed()
        self.assertEqual(feed.state, "done")
        self.assertTrue(feed.order_id)
        self.assertEqual(feed.order_id.origin, "Shopify #1001")
        self.assertEqual(len(feed.order_id.order_line), 1)

        # Verify Order Mapping
        order_map = self.env["shopify.order.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_order_id", "=", "99881122")
        ])
        self.assertTrue(order_map)
        self.assertEqual(order_map.shopify_order_number, "1001")
        self.assertEqual(order_map.financial_status, "paid")

    def test_05_location_mapping_and_routing(self):
        """Verify Shopify location mapping and stock location assignment."""
        loc_map = self.env["shopify.location.mapping"].create({
            "instance_id": self.instance.id,
            "shopify_location_id": "8877665544",
            "shopify_location_name": "Test Fulfillment Center",
            "warehouse_id": self.warehouse.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "sync_stock": True,
            "is_primary": True,
        })
        self.assertTrue(loc_map)
        self.assertEqual(loc_map.shopify_location_id, "8877665544")

        # Simulate order with this location_id
        order_payload = {
            "id": 99883344,
            "order_number": 1002,
            "name": "#1002",
            "location_id": 8877665544,
            "financial_status": "paid",
            "fulfillment_status": "unfulfilled",
            "line_items": [
                {
                    "id": 776699,
                    "variant_id": 5544332211,
                    "name": "Shopify Premium Hoodie - M",
                    "quantity": 1,
                    "price": "49.99",
                    "sku": "HOODIE-BLK-M",
                }
            ],
        }

        feed = self.env["shopify.feed"].create({
            "name": "Order Feed #1002",
            "instance_id": self.instance.id,
            "feed_type": "order",
            "external_id": "99883344",
            "raw_payload": json.dumps(order_payload),
        })
        feed.action_process_feed()
        self.assertEqual(feed.state, "done")
        self.assertEqual(feed.order_id.warehouse_id.id, self.warehouse.id)

    def test_06_metafield_mapping_and_processing(self):
        """Verify metafield mapping and value extraction into Odoo records."""
        # Map Shopify metafield custom.comment to partner comment field
        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        comment_field = self.env["ir.model.fields"].search([("model_id", "=", partner_model.id), ("name", "=", "comment")], limit=1)

        if comment_field:
            self.env["shopify.metafield.mapping"].create({
                "instance_id": self.instance.id,
                "model_id": partner_model.id,
                "field_id": comment_field.id,
                "namespace": "custom",
                "key": "customer_notes",
                "metafield_type": "single_line_text_field",
                "sync_direction": "both",
            })

            customer_payload = {
                "id": 123459999,
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "metafields": [
                    {
                        "namespace": "custom",
                        "key": "customer_notes",
                        "value": "VIP Client from New York",
                        "type": "single_line_text_field",
                    }
                ],
            }

            feed = self.env["shopify.feed"].create({
                "name": "Customer Metafield Test #123459999",
                "instance_id": self.instance.id,
                "feed_type": "customer",
                "external_id": "123459999",
                "raw_payload": json.dumps(customer_payload),
            })
            feed.action_process_feed()
            self.assertEqual(feed.state, "done")
            self.assertIn("VIP Client from New York", feed.partner_id.comment or "")

    def test_06b_product_sheet_metafield_values_import_and_export(self):
        """Custom product metafields should be stored on the product sheet and exportable."""
        product_model = self.env["ir.model"].search([("model", "=", "product.template")], limit=1)
        mapping = self.env["shopify.metafield.mapping"].create({
            "instance_id": self.instance.id,
            "model_id": product_model.id,
            "store_type": "custom",
            "namespace": "custom",
            "key": "material",
            "metafield_type": "single_line_text_field",
            "sync_direction": "both",
        })
        payload = {
            "id": 1122334700,
            "title": "Metafield Sheet Product",
            "metafields": [{
                "namespace": "custom",
                "key": "material",
                "value": "Organic cotton",
                "type": "single_line_text_field",
            }],
            "variants": [{
                "id": 5544332500,
                "sku": "META-SHEET",
                "price": "15.00",
            }],
        }
        feed = self.env["shopify.feed"].create({
            "name": "Metafield Sheet Product Feed",
            "instance_id": self.instance.id,
            "feed_type": "product",
            "external_id": "1122334700",
            "raw_payload": json.dumps(payload),
        })
        feed.action_process_feed()

        value_line = self.env["shopify.metafield.value"].search([
            ("instance_id", "=", self.instance.id),
            ("mapping_id", "=", mapping.id),
            ("product_tmpl_id", "=", feed.template_id.id),
        ], limit=1)
        self.assertEqual(feed.state, "done")
        self.assertTrue(value_line)
        self.assertEqual(value_line.value, "Organic cotton")

        wizard = self.env["shopify.sync.wizard"].create({"instance_id": self.instance.id})
        metafields = wizard._collect_record_metafields(feed.template_id, "product.template", self.instance)
        self.assertIn({
            "namespace": "custom",
            "key": "material",
            "value": "Organic cotton",
            "type": "single_line_text_field",
        }, metafields)

    def test_07_order_refund_processing(self):
        """Verify processing of order refunds and credit note creation."""
        # Enable refund credit notes
        self.instance.write({
            "auto_process_refunds": True,
            "auto_create_credit_notes": True,
        })

        order_payload = {
            "id": 77889900,
            "order_number": 1003,
            "name": "#1003",
            "financial_status": "paid",
            "line_items": [
                {
                    "id": 112288,
                    "variant_id": 5544332211,
                    "name": "Shopify Premium Hoodie - M",
                    "quantity": 1,
                    "price": "49.99",
                    "sku": "HOODIE-BLK-M",
                }
            ],
            "refunds": [
                {
                    "id": 55667788,
                    "note": "Damaged goods return",
                    "created_at": "2026-09-21T10:00:00Z",
                    "transactions": [
                        {
                            "id": 990011,
                            "amount": "49.99",
                            "status": "success",
                        }
                    ],
                }
            ],
        }

        feed = self.env["shopify.feed"].create({
            "name": "Order Feed #1003",
            "instance_id": self.instance.id,
            "feed_type": "order",
            "external_id": "77889900",
            "raw_payload": json.dumps(order_payload),
        })
        feed.action_process_feed()
        self.assertEqual(feed.state, "done")

        # Verify Refund Mapping
        refund_map = self.env["shopify.refund.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_refund_id", "=", "55667788"),
        ])
        self.assertTrue(refund_map)
        self.assertEqual(refund_map.amount, 49.99)
        self.assertEqual(refund_map.state, "processed")
        self.assertTrue(refund_map.credit_note_id)
        self.assertEqual(refund_map.credit_note_id.move_type, "out_refund")

    def test_08_location_stock_import_and_export(self):
        """Verify stock import and export by mapped location."""
        from unittest.mock import patch
        self.instance.write({"state": "confirmed"})
        tmpl = self.env["product.template"].create({
            "name": "Location Stock Test Product",
            "is_storable": True,
        })
        product = tmpl.product_variant_ids[0]

        tmpl_map = self.env["shopify.template.mapping"].create({
            "instance_id": self.instance.id,
            "template_id": tmpl.id,
            "shopify_product_id": "88776655",
        })
        self.env["shopify.product.mapping"].create({
            "instance_id": self.instance.id,
            "template_mapping_id": tmpl_map.id,
            "product_id": product.id,
            "shopify_variant_id": "77665544",
            "shopify_inventory_item_id": "66554433",
        })

        self.env["shopify.location.mapping"].create({
            "instance_id": self.instance.id,
            "shopify_location_id": "990011",
            "shopify_location_name": "Main Store Warehouse",
            "warehouse_id": self.warehouse.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "sync_stock": True,
        })

        mock_inv_levels = [
            {
                "inventory_item_id": 66554433,
                "location_id": 990011,
                "available": 42.0,
            }
        ]

        wizard = self.env["shopify.sync.wizard"].create({
            "instance_id": self.instance.id,
            "operation_type": "import",
            "entity_type": "stock",
        })

        with patch.object(type(self.instance.get_api_client()), "fetch_inventory_levels", return_value=mock_inv_levels):
            wizard.action_execute_sync()

        qty = product.with_context(location=self.warehouse.lot_stock_id.id).qty_available
        self.assertEqual(qty, 42.0)

    def test_08b_first_product_import_pulls_initial_inventory_once(self):
        """First product import should pull stock, later product updates should not overwrite it."""
        from unittest.mock import patch
        self.instance.write({"state": "confirmed"})
        self.env["shopify.location.mapping"].create({
            "instance_id": self.instance.id,
            "shopify_location_id": "990022",
            "shopify_location_name": "Initial Stock Location",
            "warehouse_id": self.warehouse.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "sync_stock": True,
        })
        payload = {
            "id": 1122334600,
            "title": "Initial Stock Product",
            "variants": [{
                "id": 5544332400,
                "sku": "INIT-STOCK",
                "price": "10.00",
                "inventory_item_id": 66554499,
            }],
        }
        feed = self.env["shopify.feed"].create({
            "name": "Initial Stock Product Feed",
            "instance_id": self.instance.id,
            "feed_type": "product",
            "external_id": "1122334600",
            "raw_payload": json.dumps(payload),
        })
        mock_levels = [{
            "inventory_item_id": 66554499,
            "location_id": 990022,
            "available": 37.0,
        }]
        with patch.object(type(self.instance.get_api_client()), "fetch_inventory_levels", return_value=mock_levels) as mocked_fetch:
            feed.action_process_feed()
            self.assertEqual(mocked_fetch.call_count, 1)

        product = self.env["shopify.product.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_variant_id", "=", "5544332400"),
        ], limit=1).product_id
        self.assertEqual(product.with_context(location=self.warehouse.lot_stock_id.id).qty_available, 37.0)

        feed.write({"state": "draft"})
        with patch.object(type(self.instance.get_api_client()), "fetch_inventory_levels", return_value=[dict(mock_levels[0], available=5.0)]) as mocked_fetch:
            feed.action_process_feed()
            self.assertEqual(mocked_fetch.call_count, 0)
        self.assertEqual(product.with_context(location=self.warehouse.lot_stock_id.id).qty_available, 37.0)

    def test_08c_first_product_export_pushes_initial_inventory_once(self):
        """First product export should push stock, later product updates should not."""
        from unittest.mock import patch
        self.instance.write({"state": "confirmed"})
        self.env["product.template"].search([("sale_ok", "=", True)]).write({"sale_ok": False})
        self.env["shopify.location.mapping"].create({
            "instance_id": self.instance.id,
            "shopify_location_id": "990033",
            "shopify_location_name": "Export Stock Location",
            "warehouse_id": self.warehouse.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "sync_stock": True,
        })
        tmpl = self.env["product.template"].create({
            "name": "Initial Export Stock Product",
            "is_storable": True,
            "sale_ok": True,
            "default_code": "EXPORT-STOCK",
        })
        product = tmpl.product_variant_ids[0]
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        quant.inventory_quantity = 19.0
        quant.action_apply_inventory()

        wizard = self.env["shopify.sync.wizard"].create({
            "instance_id": self.instance.id,
            "operation_type": "export",
            "entity_type": "product",
            "record_limit": 1,
        })
        create_response = {
            "product": {
                "id": 1122334800,
                "handle": "initial-export-stock-product",
                "variants": [{
                    "id": 5544332600,
                    "sku": "EXPORT-STOCK",
                    "inventory_item_id": 66554500,
                }],
            }
        }

        with patch.object(type(self.instance.get_api_client()), "create_product", return_value=create_response), \
                patch.object(type(self.instance.get_api_client()), "update_product", return_value={}) as mocked_update_product, \
                patch.object(type(self.instance.get_api_client()), "update_inventory_level", return_value={}) as mocked_update_inventory:
            wizard.action_execute_sync()
            mocked_update_inventory.assert_called_once_with(
                inventory_item_id="66554500",
                location_id="990033",
                available_qty=19,
            )
            self.assertEqual(mocked_update_product.call_count, 0)

            mocked_update_inventory.reset_mock()
            wizard.action_execute_sync()
            self.assertEqual(mocked_update_product.call_count, 1)
            self.assertEqual(mocked_update_inventory.call_count, 0)

    def test_08d_fetch_metafield_definitions(self):
        """Fetched Shopify definitions should create visible mapping rows for manual field mapping."""
        from unittest.mock import patch
        self.instance.write({"state": "confirmed"})
        definitions = [{
            "id": "gid://shopify/MetafieldDefinition/123",
            "name": "Material",
            "namespace": "custom",
            "key": "material",
            "description": "Product material",
            "ownerType": "PRODUCT",
            "type": {"name": "single_line_text_field", "category": "TEXT"},
        }]
        with patch.object(type(self.instance.get_api_client()), "fetch_metafield_definitions", return_value=definitions):
            count = self.instance.action_fetch_metafields(return_count=True)

        mapping = self.env["shopify.metafield.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("namespace", "=", "custom"),
            ("key", "=", "material"),
        ], limit=1)
        self.assertEqual(count, 1)
        self.assertTrue(mapping)
        self.assertTrue(mapping.active)
        self.assertFalse(mapping.field_id)
        self.assertEqual(mapping.model_name, "product.template")
        self.assertEqual(mapping.shopify_definition_id, "gid://shopify/MetafieldDefinition/123")

    def test_08e_manual_stock_update_realtime_sync(self):
        """Verify real-time stock update pushes correct quantity when stock is manually adjusted."""
        from unittest.mock import patch
        self.instance.write({
            "state": "confirmed",
            "sync_inventory_on_update": True,
        })
        lmap = self.env["shopify.location.mapping"].create({
            "instance_id": self.instance.id,
            "shopify_location_id": "990088",
            "shopify_location_name": "Manual Adjustment Warehouse",
            "warehouse_id": self.warehouse.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "sync_stock": True,
        })
        tmpl = self.env["product.template"].create({
            "name": "Manual Stock Test Product",
            "is_storable": True,
            "sale_ok": True,
            "default_code": "MANUAL-STOCK-1",
        })
        product = tmpl.product_variant_ids[0]
        tmpl_map = self.env["shopify.template.mapping"].create({
            "instance_id": self.instance.id,
            "template_id": tmpl.id,
            "shopify_product_id": "88770011",
        })
        self.env["shopify.product.mapping"].create({
            "instance_id": self.instance.id,
            "template_mapping_id": tmpl_map.id,
            "product_id": product.id,
            "shopify_variant_id": "77660022",
            "shopify_inventory_item_id": "66550033",
        })

        # Test 1: Updating stock via stock.quant action_apply_inventory
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        quant.inventory_quantity = 28.0
        with patch.object(type(self.instance.get_api_client()), "update_inventory_level", return_value={}) as mocked_update:
            quant.action_apply_inventory()
            mocked_update.assert_called_once_with(
                inventory_item_id="66550033",
                location_id="990088",
                available_qty=28,
            )

        # Test 2: Updating stock via direct product qty_available assignment
        with patch.object(type(self.instance.get_api_client()), "update_inventory_level", return_value={}) as mocked_update_direct:
            product.qty_available = 45.0
            mocked_update_direct.assert_called_once_with(
                inventory_item_id="66550033",
                location_id="990088",
                available_qty=45,
            )

    def test_09_oauth_authorization_and_token_exchange(self):
        """Verify Shopify OAuth 2.0 URL creation and code exchange."""
        oauth_instance = self.env["shopify.instance"].create({
            "name": "OAuth Test Store",
            "shop_url": "https://oauth-store.myshopify.com",
            "auth_method": "oauth",
            "client_id": "test_client_key_123",
            "client_secret": "test_client_secret_xyz",
            "warehouse_id": self.warehouse.id,
            "company_id": self.company.id,
        })

        # 1. Verify redirect URL generation
        auth_action = oauth_instance.action_start_oauth()
        self.assertEqual(auth_action["type"], "ir.actions.act_url")
        self.assertIn("oauth-store.myshopify.com/admin/oauth/authorize", auth_action["url"])
        self.assertIn("client_id=test_client_key_123", auth_action["url"])
        self.assertIn(f"state={oauth_instance.id}", auth_action["url"])

        # 2. Verify token exchange via code
        from unittest.mock import patch, MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "access_token": "shpat_mock_exchanged_token_999",
            "scope": "read_products,write_products",
        }

        with patch("requests.post", return_value=mock_response):
            oauth_instance.connect_with_oauth_code("sample_auth_code_abc", "oauth-store.myshopify.com")

        self.assertEqual(oauth_instance.state, "confirmed")
        self.assertEqual(oauth_instance.access_token, "shpat_mock_exchanged_token_999")

    def test_10_customer_addresses_hierarchy(self):
        """Verify that customer import properly creates parent contact and child invoice/delivery addresses."""
        customer_payload = {
            "id": 9911223344,
            "first_name": "Alexander",
            "last_name": "Hamilton",
            "email": "alex.hamilton@treasury.gov",
            "phone": "+15551234567",
            "default_address": {
                "id": 1101,
                "first_name": "Alexander",
                "last_name": "Hamilton",
                "company": "Bank of NY",
                "address1": "48 Wall Street",
                "city": "New York",
                "province_code": "NY",
                "country_code": "US",
                "zip": "10005",
                "phone": "+15551234567",
                "default": True,
            },
            "addresses": [
                {
                    "id": 1101,
                    "first_name": "Alexander",
                    "last_name": "Hamilton",
                    "company": "Bank of NY",
                    "address1": "48 Wall Street",
                    "city": "New York",
                    "province_code": "NY",
                    "country_code": "US",
                    "zip": "10005",
                    "phone": "+15551234567",
                    "default": True,
                },
                {
                    "id": 1102,
                    "first_name": "Alexander",
                    "last_name": "Hamilton",
                    "company": "Grange Estate",
                    "address1": "414 W 141st St",
                    "city": "New York",
                    "province_code": "NY",
                    "country_code": "US",
                    "zip": "10031",
                    "phone": "+15559876543",
                    "default": False,
                },
            ],
        }

        feed = self.env["shopify.feed"].create({
            "name": "Customer Feed #9911223344",
            "instance_id": self.instance.id,
            "feed_type": "customer",
            "external_id": "9911223344",
            "raw_payload": json.dumps(customer_payload),
        })

        feed.action_process_feed()
        self.assertEqual(feed.state, "done")
        parent = feed.partner_id
        self.assertTrue(parent)
        self.assertEqual(parent.name, "Alexander Hamilton")
        self.assertEqual(parent.email, "alex.hamilton@treasury.gov")
        self.assertEqual(parent.street, "48 Wall Street")
        self.assertEqual(parent.city, "New York")
        self.assertEqual(parent.zip, "10005")

        # Verify child addresses
        children = self.env["res.partner"].search([("parent_id", "=", parent.id)])
        self.assertGreaterEqual(len(children), 2)
        invoice_addrs = children.filtered(lambda c: c.type == "invoice")
        delivery_addrs = children.filtered(lambda c: c.type == "delivery")
        self.assertTrue(invoice_addrs)
        self.assertTrue(delivery_addrs)
        self.assertEqual(delivery_addrs[0].street, "414 W 141st St")
        self.assertEqual(delivery_addrs[0].zip, "10031")

    def test_11_order_complete_workflow_taxes_discounts_invoicing_delivery(self):
        """Verify full order import with taxes, discounts, shipping, invoice posting, payment, and delivery."""
        self.instance.write({
            "auto_validate_orders": True,
            "auto_create_invoices": True,
            "auto_paid_invoices": True,
            "auto_deliver_orders": True,
        })

        order_payload = {
            "id": 888777666,
            "order_number": 2005,
            "name": "#2005",
            "financial_status": "paid",
            "fulfillment_status": "fulfilled",
            "taxes_included": False,
            "payment_gateway_names": ["shopify_payments"],
            "created_at": "2026-09-24T08:30:00Z",
            "customer": {
                "id": 77661122,
                "first_name": "Thomas",
                "last_name": "Jefferson",
                "email": "thomas.jefferson@monticello.org",
            },
            "billing_address": {
                "first_name": "Thomas",
                "last_name": "Jefferson",
                "address1": "931 Thomas Jefferson Pkwy",
                "city": "Charlottesville",
                "province_code": "VA",
                "country_code": "US",
                "zip": "22902",
            },
            "shipping_address": {
                "first_name": "Thomas",
                "last_name": "Jefferson",
                "address1": "1600 Pennsylvania Avenue NW",
                "city": "Washington",
                "province_code": "DC",
                "country_code": "US",
                "zip": "20500",
            },
            "line_items": [
                {
                    "id": 554411,
                    "variant_id": 9988111,
                    "name": "Constitution Quill Pen",
                    "quantity": 2,
                    "price": "50.00",
                    "sku": "PEN-QUILL-01",
                    "discount_allocations": [
                        {
                            "allocated_amount": "10.00",
                        }
                    ],
                    "tax_lines": [
                        {
                            "title": "State Sales Tax",
                            "rate": 0.05,
                            "price": "4.50",
                        }
                    ],
                }
            ],
            "shipping_lines": [
                {
                    "title": "Express Courier",
                    "price": "15.00",
                    "tax_lines": [
                        {
                            "title": "State Sales Tax",
                            "rate": 0.05,
                            "price": "0.75",
                        }
                    ],
                }
            ],
            "discount_applications": [
                {
                    "title": "WELCOME5",
                    "value": "5.00",
                    "allocation_method": "one",
                    "target_type": "line_item",
                }
            ],
        }

        feed = self.env["shopify.feed"].create({
            "name": "Order Feed #2005",
            "instance_id": self.instance.id,
            "feed_type": "order",
            "external_id": "888777666",
            "raw_payload": json.dumps(order_payload),
        })

        feed.action_process_feed()
        self.assertEqual(feed.state, "done")
        sale_order = feed.order_id
        self.assertTrue(sale_order)

        # 1. Partner and Address Separation
        self.assertEqual(sale_order.partner_id.name, "Thomas Jefferson")
        self.assertEqual(sale_order.partner_invoice_id.type, "invoice")
        self.assertIn("931 Thomas Jefferson Pkwy", sale_order.partner_invoice_id.street)
        self.assertEqual(sale_order.partner_shipping_id.type, "delivery")
        self.assertIn("1600 Pennsylvania Avenue", sale_order.partner_shipping_id.street)

        # 2. Line Items, Discounts, Shipping
        # Lines should include: 1 product line + 1 shipping line + 1 order manual discount line
        self.assertEqual(len(sale_order.order_line), 3)

        product_line = sale_order.order_line.filtered(lambda l: l.product_id.default_code == "PEN-QUILL-01")
        self.assertTrue(product_line)
        self.assertEqual(product_line.discount, 10.0)  # 10.00 / 100.00 = 10%
        self.assertTrue(product_line.tax_ids)
        self.assertEqual(product_line.tax_ids[0].amount, 5.0)

        shipping_line = sale_order.order_line.filtered(lambda l: "Shipping" in l.name)
        self.assertTrue(shipping_line)
        self.assertEqual(shipping_line.price_unit, 15.00)

        discount_line = sale_order.order_line.filtered(lambda l: "Discount" in l.name)
        self.assertTrue(discount_line)
        self.assertEqual(discount_line.price_unit, -5.00)

        # 3. Order Confirmation & Invoicing
        self.assertEqual(sale_order.state, "sale")
        self.assertTrue(sale_order.invoice_ids)
        invoice = sale_order.invoice_ids[0]
        self.assertEqual(invoice.state, "posted")
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))

        # 4. Delivery Validation
        self.assertTrue(sale_order.picking_ids)
        picking = sale_order.picking_ids[0]
        self.assertEqual(picking.state, "done")
        self.assertTrue(picking.shopify_fulfillment_synced)

    def test_12_multi_company_defaults_and_dynamic_pricelist(self):
        """Verify default warehouse/company/pricelist, onchange sync, dynamic pricelist creation, and multi-company isolation."""
        # 1. Setup second company and warehouse
        eur_currency = self.env.ref("base.EUR")
        company_2 = self.env["res.company"].create({
            "name": "Second Multi-Company Store Ltd",
            "currency_id": eur_currency.id,
        })
        warehouse_2 = self.env["stock.warehouse"].create({
            "name": "Second Multi-Company WH",
            "code": "SMCW",
            "company_id": company_2.id,
        })

        # 2. Test instance defaults
        new_instance = self.env["shopify.instance"].new({})
        self.assertTrue(new_instance.warehouse_id)
        self.assertEqual(new_instance.company_id, new_instance.warehouse_id.company_id)
        self.assertTrue(new_instance.pricelist_id)
        self.assertIn(new_instance.pricelist_id.company_id.id, (new_instance.company_id.id, False))

        # 3. Test onchange warehouse_id updates company_id & location_id
        new_instance.warehouse_id = warehouse_2
        new_instance._onchange_warehouse_id()
        self.assertEqual(new_instance.company_id, company_2)
        self.assertEqual(new_instance.location_id, warehouse_2.lot_stock_id)

        # 4. Test onchange company_id updates warehouse_id, pricelist_id & location_id
        new_instance.company_id = self.company
        new_instance._onchange_company_id()
        self.assertEqual(new_instance.warehouse_id.company_id, self.company)
        self.assertEqual(new_instance.location_id, new_instance.warehouse_id.lot_stock_id)
        self.assertIn(new_instance.pricelist_id.company_id.id, (self.company.id, False))

        # 5. Test dynamic pricelist creation per currency and company
        inst_2 = self.env["shopify.instance"].create({
            "name": "EUR Shopify Store",
            "shop_url": "https://eur-store.myshopify.com",
            "auth_method": "token",
            "access_token": "shpat_eur_test_token",
            "company_id": company_2.id,
            "warehouse_id": warehouse_2.id,
            "state": "confirmed",
        })
        self.assertEqual(inst_2.company_id, company_2)
        self.assertEqual(inst_2.warehouse_id, warehouse_2)

        # Dynamic pricelist for EUR
        pl_eur = inst_2._get_or_create_pricelist_for_currency("EUR")
        self.assertTrue(pl_eur.active)
        self.assertEqual(pl_eur.currency_id.name, "EUR")
        self.assertEqual(pl_eur.company_id, company_2)

        # Dynamic pricelist for USD on same EUR company store
        pl_usd = inst_2._get_or_create_pricelist_for_currency("USD")
        self.assertTrue(pl_usd.active)
        self.assertEqual(pl_usd.currency_id.name, "USD")
        self.assertEqual(pl_usd.company_id, company_2)

        # 6. Test Order processing assigns resolved company & currency pricelist
        order_payload = {
            "id": 8899001122,
            "order_number": 5055,
            "currency": "EUR",
            "financial_status": "authorized",
            "fulfillment_status": "unfulfilled",
            "customer": {
                "id": 44332211,
                "first_name": "Multi",
                "last_name": "Company User",
                "email": "multicompany@example.com",
            },
            "line_items": [{
                "id": 99887766,
                "name": "Multi-Company Product",
                "price": "45.00",
                "quantity": 1,
                "sku": "MC-EUR-01",
            }],
        }
        feed = self.env["shopify.feed"].create({
            "name": "Order #5055 Feed",
            "instance_id": inst_2.id,
            "feed_type": "order",
            "external_id": "8899001122",
            "raw_payload": json.dumps(order_payload),
        })
        feed.action_process_feed()
        self.assertEqual(feed.state, "done")
        sale_order = feed.order_id
        self.assertEqual(sale_order.company_id, company_2)
        self.assertEqual(sale_order.warehouse_id, warehouse_2)
        self.assertEqual(sale_order.pricelist_id, pl_eur)
        self.assertEqual(sale_order.currency_id.name, "EUR")

        # 7. Test Multi-Company Stock Isolation
        tmpl = self.env["product.template"].create({
            "name": "Multi Company Storable Product",
            "is_storable": True,
            "sale_ok": True,
            "default_code": "MC-STOCK-ISO",
        })
        prod = tmpl.product_variant_ids[0]
        # Add stock in Company 1 warehouse only
        quant_c1 = self.env["stock.quant"].create({
            "product_id": prod.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "company_id": self.company.id,
        })
        quant_c1.inventory_quantity = 50.0
        quant_c1.action_apply_inventory()

        # Company 1 instance sees 50
        qty_c1 = self.instance.get_stock_quantity(prod)
        self.assertEqual(qty_c1, 50)

        # Company 2 instance sees 0 (stock isolated!)
        qty_c2 = inst_2.get_stock_quantity(prod)
        self.assertEqual(qty_c2, 0)

    def test_13_product_import_default_pricelist_integration(self):
        """Verify product import writes prices into the instance's default pricelist and update works."""
        # Ensure instance has default pricelist
        pricelist = self.instance.pricelist_id
        self.assertTrue(pricelist)

        # 1. Import product with variant price 75.50
        payload = {
            "id": 9988776655,
            "title": "Pricelist Test Watch",
            "variants": [{
                "id": 4433221100,
                "sku": "PL-WATCH-01",
                "price": "75.50",
                "inventory_item_id": 11224455,
            }],
        }
        feed = self.env["shopify.feed"].create({
            "name": "Product Feed #9988776655",
            "instance_id": self.instance.id,
            "feed_type": "product",
            "external_id": "9988776655",
            "raw_payload": json.dumps(payload),
        })
        feed.action_process_feed()
        self.assertEqual(feed.state, "done")

        prod_map = self.env["shopify.product.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_variant_id", "=", "4433221100"),
        ], limit=1)
        self.assertTrue(prod_map)
        variant = prod_map.product_id

        # Verify fixed_price in default pricelist is 75.50
        item = self.env["product.pricelist.item"].search([
            ("pricelist_id", "=", pricelist.id),
            ("applied_on", "=", "0_product_variant"),
            ("product_id", "=", variant.id),
        ], limit=1)
        self.assertTrue(item)
        self.assertEqual(item.fixed_price, 75.50)

        # 2. Update price in Shopify to 89.99 and re-import
        update_payload = {
            "id": 9988776655,
            "title": "Pricelist Test Watch",
            "variants": [{
                "id": 4433221100,
                "sku": "PL-WATCH-01",
                "price": "89.99",
                "inventory_item_id": 11224455,
            }],
        }
        update_feed = self.env["shopify.feed"].create({
            "name": "Product Feed #9988776655-update",
            "instance_id": self.instance.id,
            "feed_type": "product",
            "external_id": "9988776655",
            "raw_payload": json.dumps(update_payload),
        })
        update_feed.action_process_feed()
        self.assertEqual(update_feed.state, "done")

        # Verify pricelist item updated cleanly without duplication
        items = self.env["product.pricelist.item"].search([
            ("pricelist_id", "=", pricelist.id),
            ("applied_on", "=", "0_product_variant"),
            ("product_id", "=", variant.id),
        ])
        self.assertEqual(len(items), 1)
        self.assertEqual(items.fixed_price, 89.99)

    def test_14_category_import_export_and_product_categories(self):
        """Verify Category/Collection import via feeds, product import category resolution, and category export."""
        from unittest.mock import patch

        # 1. Test Category Import via Staging Feed
        cat_payload = {
            "id": 88001122,
            "title": "Summer Collection",
            "handle": "summer-collection",
            "collection_type": "custom",
        }
        feed = self.env["shopify.feed"].create({
            "name": "Category Feed #88001122",
            "instance_id": self.instance.id,
            "feed_type": "category",
            "external_id": "88001122",
            "raw_payload": json.dumps(cat_payload),
        })
        feed.action_process_feed()
        self.assertEqual(feed.state, "done")
        self.assertTrue(feed.category_id)
        self.assertEqual(feed.category_id.name, "Summer Collection")

        # Verify shopify.category.mapping
        cat_mapping = self.env["shopify.category.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_collection_id", "=", "88001122"),
        ], limit=1)
        self.assertTrue(cat_mapping)
        self.assertEqual(cat_mapping.category_id, feed.category_id)
        self.assertEqual(cat_mapping.shopify_collection_title, "Summer Collection")
        self.assertEqual(cat_mapping.shopify_collection_type, "custom")

        # Verify instance stat metric
        self.instance._compute_metrics()
        self.assertGreaterEqual(self.instance.category_mapping_count, 1)

        # 2. Test Product Import resolving existing and new collections + product_type
        prod_payload = {
            "id": 99112233,
            "title": "Floral Beach Dress",
            "product_type": "Dresses",
            "collections": [
                {"id": 88001122, "title": "Summer Collection"},
                {"id": 88003344, "title": "Beachwear", "handle": "beachwear"},
            ],
            "variants": [{
                "id": 77112233,
                "sku": "FBD-01",
                "price": "45.00",
                "inventory_item_id": 66112233,
            }],
        }
        prod_feed = self.env["shopify.feed"].create({
            "name": "Product Feed #99112233",
            "instance_id": self.instance.id,
            "feed_type": "product",
            "external_id": "99112233",
            "raw_payload": json.dumps(prod_payload),
        })
        prod_feed.action_process_feed()
        self.assertEqual(prod_feed.state, "done")
        template = prod_feed.template_id
        self.assertTrue(template)

        # Template should have shopify_category_ids containing Summer Collection, Beachwear, and Dresses
        cat_names = set(template.shopify_category_ids.mapped("name"))
        self.assertIn("Summer Collection", cat_names)
        self.assertIn("Beachwear", cat_names)
        self.assertIn("Dresses", cat_names)
        self.assertTrue(template.categ_id)

        # Beachwear should also now be mapped
        beachwear_map = self.env["shopify.category.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("shopify_collection_id", "=", "88003344"),
        ], limit=1)
        self.assertTrue(beachwear_map)
        self.assertEqual(beachwear_map.shopify_collection_title, "Beachwear")

        # 3. Test Category Export via Wizard
        self.instance.write({"state": "confirmed"})
        new_category = self.env["product.category"].create({"name": "Winter Parkas"})

        wizard = self.env["shopify.sync.wizard"].create({
            "instance_id": self.instance.id,
            "operation_type": "export",
            "entity_type": "category",
            "record_limit": 10,
        })

        col_id_seq = [99554433]
        def _mock_create_collection(payload):
            cid = col_id_seq[0]
            col_id_seq[0] += 1
            return {
                "custom_collection": {
                    "id": cid,
                    "title": payload.get("title", "Collection"),
                    "handle": payload.get("title", "col").lower().replace(" ", "-"),
                }
            }

        with patch.object(type(self.instance.get_api_client()), "create_collection", side_effect=_mock_create_collection) as mock_create_col:
            wizard.action_execute_sync()

        # Check export mapping created for Winter Parkas
        parka_map = self.env["shopify.category.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("category_id", "=", new_category.id),
        ], limit=1)
        self.assertTrue(parka_map)
        self.assertEqual(parka_map.category_id, new_category)
        self.assertEqual(parka_map.shopify_collection_title, "Winter Parkas")

        # 4. Test Product Export attaching product to Shopify Collection
        self.env["product.template"].search([("sale_ok", "=", True)]).write({"sale_ok": False})
        product_tmpl = self.env["product.template"].create({
            "name": "Sub-Zero Heavy Parka",
            "categ_id": new_category.id,
            "shopify_category_ids": [(6, 0, [new_category.id])],
            "sale_ok": True,
        })
        prod_export_wizard = self.env["shopify.sync.wizard"].create({
            "instance_id": self.instance.id,
            "operation_type": "export",
            "entity_type": "product",
            "record_limit": 1,
        })
        mock_prod_res = {
            "product": {
                "id": 1234567800,
                "handle": "sub-zero-heavy-parka",
                "variants": [{
                    "id": 9876543200,
                    "sku": "SZ-PARKA",
                    "inventory_item_id": 8765432100,
                }]
            }
        }
        with patch.object(type(self.instance.get_api_client()), "create_product", return_value=mock_prod_res), \
             patch.object(type(self.instance.get_api_client()), "add_product_to_collection", return_value={"collect": {"id": 1}}) as mock_add_col:
            prod_export_wizard.action_execute_sync()

        mock_add_col.assert_called_with("1234567800", parka_map.shopify_collection_id)

    def test_15_single_product_export_and_bidirectional_update_with_delete_detection(self):
        """Verify single product export wizard, bidirectional update buttons, and deleted on shopify tracking."""
        from unittest.mock import patch
        from odoo.addons.odoo_shopify_connector.models.shopify_client import ShopifyNotFoundError

        self.instance.write({"state": "confirmed"})

        # Create product template
        tmpl = self.env["product.template"].create({
            "name": "Leather Travel Bag",
            "list_price": 95.0,
            "default_code": "LTB-001",
            "sale_ok": True,
        })

        # 1. Test Export Button on Product Template (Wizard initialization & Multi-Instance)
        action = tmpl.action_shopify_export_product()
        self.assertEqual(action.get("res_model"), "shopify.product.export.wizard")
        self.assertEqual(action.get("context", {}).get("default_template_id"), tmpl.id)
        self.assertEqual(action.get("context", {}).get("default_instance_id"), self.instance.id)

        # 2. Test Single Product Export via Wizard
        wizard = self.env["shopify.product.export.wizard"].create({
            "template_id": tmpl.id,
            "instance_id": self.instance.id,
            "publish": True,
        })
        mock_create_res = {
            "product": {
                "id": 99881122,
                "title": "Leather Travel Bag",
                "handle": "leather-travel-bag",
                "status": "active",
                "variants": [{
                    "id": 88771122,
                    "sku": "LTB-001",
                    "price": "95.00",
                    "inventory_item_id": 77661122,
                }],
            }
        }
        with patch.object(type(self.instance.get_api_client()), "create_product", return_value=mock_create_res):
            wizard.action_export_product()

        # Check mapping created
        mapping = self.env["shopify.template.mapping"].search([
            ("instance_id", "=", self.instance.id),
            ("template_id", "=", tmpl.id),
        ], limit=1)
        self.assertTrue(mapping)
        self.assertEqual(mapping.shopify_product_id, "99881122")
        self.assertEqual(mapping.shopify_status, "active")
        self.assertFalse(mapping.is_deleted_on_shopify)

        # 3. Test Odoo to Shopify Update (Push)
        tmpl.write({"name": "Deluxe Leather Travel Bag", "list_price": 105.0})
        mock_update_res = {
            "product": {
                "id": 99881122,
                "title": "Deluxe Leather Travel Bag",
                "status": "active",
                "handle": "deluxe-leather-travel-bag",
                "variants": [{
                    "id": 88771122,
                    "sku": "LTB-001",
                    "price": "105.00",
                    "inventory_item_id": 77661122,
                }],
            }
        }
        with patch.object(type(self.instance.get_api_client()), "update_product", return_value=mock_update_res) as mock_update:
            res_notif = mapping.action_odoo_to_shopify()
            self.assertEqual(res_notif.get("params", {}).get("type"), "success")

        payload_sent = mock_update.call_args[0][1]
        self.assertEqual(payload_sent["title"], "Deluxe Leather Travel Bag")
        self.assertEqual(mapping.shopify_handle, "deluxe-leather-travel-bag")

        # 4. Test Shopify to Odoo Update (Pull)
        mock_pull_res = {
            "id": 99881122,
            "title": "Premium Leather Travel Bag",
            "body_html": "<p>Finest Italian Leather</p>",
            "status": "active",
            "handle": "premium-leather-travel-bag",
            "variants": [{
                "id": 88771122,
                "sku": "LTB-001",
                "price": "120.00",
                "inventory_item_id": 77661122,
            }],
        }
        with patch.object(type(self.instance.get_api_client()), "fetch_product", return_value=mock_pull_res), \
             patch.object(type(self.instance.get_api_client()), "fetch_collects", return_value=[]), \
             patch.object(type(self.instance.get_api_client()), "fetch_metafields", return_value=[]):
            res_pull = mapping.action_shopify_to_odoo()
            self.assertEqual(res_pull.get("params", {}).get("type"), "success")

        # Product template name in Odoo updated
        tmpl.invalidate_recordset(["name"])
        self.assertEqual(tmpl.name, "Premium Leather Travel Bag")
        self.assertFalse(mapping.is_deleted_on_shopify)

        # 5. Test Product Deleted on Shopify Detection (HTTP 404)
        with patch.object(type(self.instance.get_api_client()), "fetch_product", side_effect=ShopifyNotFoundError("404 Not Found")):
            res_del_pull = mapping.action_shopify_to_odoo()
            self.assertEqual(res_del_pull.get("params", {}).get("type"), "danger")

        # Mapping must now show Deleted on Shopify
        self.assertTrue(mapping.is_deleted_on_shopify)
        self.assertEqual(mapping.shopify_status, "deleted")

        # Live status check also confirms deleted
        with patch.object(type(self.instance.get_api_client()), "fetch_product", side_effect=ShopifyNotFoundError("404 Not Found")):
            res_check = mapping.action_check_shopify_status()
            self.assertEqual(res_check.get("params", {}).get("type"), "danger")
        self.assertTrue(mapping.is_deleted_on_shopify)

        # 6. Test Re-export when previously marked as deleted
        with patch.object(type(self.instance.get_api_client()), "create_product", return_value={
            "product": {"id": 99889999, "title": "Premium Leather Travel Bag", "status": "active", "variants": []}
        }):
            reexport_wizard = self.env["shopify.product.export.wizard"].create({
                "template_id": tmpl.id,
                "instance_id": self.instance.id,
            })
            reexport_wizard.action_export_product()

        self.assertEqual(mapping.shopify_product_id, "99889999")
        self.assertFalse(mapping.is_deleted_on_shopify)
        self.assertEqual(mapping.shopify_status, "active")

    def test_26_kanban_view_and_metrics(self):
        """Verify Shopify Store kanban view architecture and all metric actions."""
        kanban_view = self.env.ref("odoo_shopify_connector.view_shopify_instance_kanban")
        self.assertTrue(kanban_view)
        self.assertEqual(kanban_view.type, "kanban")

        # Test action definitions for all objects
        self.assertEqual(self.instance.action_view_orders()["res_model"], "shopify.order.mapping")
        self.assertEqual(self.instance.action_view_products()["res_model"], "shopify.template.mapping")
        self.assertEqual(self.instance.action_view_categories()["res_model"], "shopify.category.mapping")
        self.assertEqual(self.instance.action_view_customers()["res_model"], "shopify.partner.mapping")
        self.assertEqual(self.instance.action_view_refunds()["res_model"], "shopify.refund.mapping")
        self.assertEqual(self.instance.action_view_locations()["res_model"], "shopify.location.mapping")
        self.assertEqual(self.instance.action_view_metafields()["res_model"], "shopify.metafield.mapping")
        self.assertEqual(self.instance.action_view_feeds()["res_model"], "shopify.feed")
        self.assertEqual(self.instance.action_view_history()["res_model"], "shopify.sync.history")

        # Verify action window view_mode includes kanban first
        act = self.env.ref("odoo_shopify_connector.action_shopify_instance")
        self.assertTrue(act.view_mode.startswith("kanban"))

    def test_27_form_view_and_connection_animation(self):
        """Verify modern form view structure and rainbow_man connection celebration animation."""
        from unittest.mock import patch
        form_view = self.env.ref("odoo_shopify_connector.view_shopify_instance_form")
        self.assertTrue(form_view)
        self.assertEqual(form_view.type, "form")

        # Mock shop connection
        with patch.object(type(self.instance.get_api_client()), "test_connection", return_value={"name": "Test Shopify Store", "domain": "unit-test.myshopify.com", "currency": "USD"}), \
             patch.object(type(self.instance.get_api_client()), "get_locations", return_value=[{"id": 112233}]):
            res = self.instance.action_test_connection()

        self.assertEqual(self.instance.state, "confirmed")
        self.assertIn("effect", res)
        self.assertEqual(res["effect"].get("type"), "rainbow_man")
        self.assertIn("Test Shopify Store", res["effect"].get("message", ""))

    def test_28_onboarding_and_setup_plan(self):
        """Verify dynamic onboarding plan calculation, step badges, and collapsible panel."""
        # 1. Initial State: draft, warehouse set, sync_inventory_on_update=True -> 50%
        self.assertTrue(self.instance.show_onboarding_panel)
        self.assertFalse(self.instance.onboarding_step_connection)
        self.assertTrue(self.instance.onboarding_step_logistics)
        self.assertTrue(self.instance.onboarding_step_automations)
        self.assertEqual(self.instance.onboarding_progress, 50)

        # 2. Toggle panel visibility
        self.instance.action_toggle_onboarding()
        self.assertFalse(self.instance.show_onboarding_panel)
        self.instance.action_toggle_onboarding()
        self.assertTrue(self.instance.show_onboarding_panel)

        # 3. Complete Step 3: Financials (Pricelist & Payment Journal)
        journal = self.env["account.journal"].search([
            ("type", "in", ("bank", "cash")),
            ("company_id", "=", self.company.id),
        ], limit=1)
        if not journal:
            journal = self.env["account.journal"].create({
                "name": "Shopify Bank Journal",
                "type": "bank",
                "code": "SHPBK",
                "company_id": self.company.id,
            })
        self.instance.payment_journal_id = journal
        self.assertTrue(self.instance.onboarding_step_financials)
        self.assertEqual(self.instance.onboarding_progress, 75)

        # 4. Complete Step 1: Confirm connection
        self.instance.state = "confirmed"
        self.assertTrue(self.instance.onboarding_step_connection)
        self.assertEqual(self.instance.onboarding_progress, 100)

    def test_29_onboarding_wizard_and_stage_actions(self):
        """Verify onboarding wizard views, step stage buttons, field persistence, and sync wizard launch."""
        from unittest.mock import patch

        # 1. Test Stage Action Methods on shopify.instance
        act_conn = self.instance.action_open_step_connection()
        self.assertEqual(act_conn.get("res_model"), "shopify.onboarding.wizard")
        self.assertEqual(act_conn.get("context", {}).get("default_current_step"), "connection")

        act_log = self.instance.action_open_step_logistics()
        self.assertEqual(act_log.get("res_model"), "shopify.onboarding.wizard")
        self.assertEqual(act_log.get("context", {}).get("default_current_step"), "logistics")

        act_fin = self.instance.action_open_step_financials()
        self.assertEqual(act_fin.get("res_model"), "shopify.onboarding.wizard")
        self.assertEqual(act_fin.get("context", {}).get("default_current_step"), "financials")

        act_auto = self.instance.action_open_step_automations()
        self.assertEqual(act_auto.get("res_model"), "shopify.onboarding.wizard")
        self.assertEqual(act_auto.get("context", {}).get("default_current_step"), "automations")

        act_plan = self.instance.action_open_onboarding_wizard()
        self.assertEqual(act_plan.get("res_model"), "shopify.onboarding.wizard")

        # 2. Instantiate Onboarding Wizard with context
        wizard = self.env["shopify.onboarding.wizard"].with_context(
            default_instance_id=self.instance.id,
            default_current_step="connection"
        ).create({})

        self.assertEqual(wizard.instance_id.id, self.instance.id)
        self.assertEqual(wizard.current_step, "connection")
        self.assertEqual(wizard.shop_url, self.instance.shop_url)
        self.assertEqual(wizard.warehouse_id.id, self.instance.warehouse_id.id)

        # 3. Test Wizard Step Navigation
        wizard.action_next_step()
        self.assertEqual(wizard.current_step, "logistics")

        wizard.action_next_step()
        self.assertEqual(wizard.current_step, "financials")

        wizard.action_prev_step()
        self.assertEqual(wizard.current_step, "logistics")

        wizard.action_go_step_automations()
        self.assertEqual(wizard.current_step, "automations")

        # 4. Modify Values in Step 4 and Save
        wizard.auto_validate_orders = True
        wizard.auto_create_invoices = True
        wizard.action_save_and_close()

        self.assertTrue(self.instance.auto_validate_orders)
        self.assertTrue(self.instance.auto_create_invoices)

        # 5. Test Launch Sync Wizard from Onboarding Step 4
        sync_act = wizard.action_save_and_launch_sync()
        self.assertEqual(sync_act.get("res_model"), "shopify.sync.wizard")

        # 6. Verify Wizard View & Action Definitions
        view_wiz = self.env.ref("odoo_shopify_connector.view_shopify_onboarding_wizard_form")
        self.assertTrue(view_wiz)
        act_wiz = self.env.ref("odoo_shopify_connector.action_shopify_onboarding_wizard")
        self.assertTrue(act_wiz)

    def test_39_store_create_wizard(self):
        """Verify Quick Create Store Wizard functionality and instant creation."""
        from odoo.exceptions import ValidationError

        # 1. Verify Wizard Window Action
        action_ref = self.env.ref("odoo_shopify_connector.action_shopify_store_create_wizard")
        self.assertTrue(action_ref)
        self.assertEqual(action_ref.target, "new")
        self.assertEqual(action_ref.res_model, "shopify.store.create.wizard")

        # 2. Test Validation Error when token is missing
        wiz_missing_token = self.env["shopify.store.create.wizard"].create({
            "name": "Missing Token Store",
            "shop_url": "https://missing-token.myshopify.com",
            "auth_method": "token",
            "access_token": False,
            "warehouse_id": self.warehouse.id,
            "company_id": self.company.id,
        })
        with self.assertRaises(ValidationError):
            wiz_missing_token.action_create_store()

        # 3. Create Store Wizard with valid data (test_connection_now=False)
        store_wiz = self.env["shopify.store.create.wizard"].create({
            "name": "Quick Created Boutique",
            "shop_url": "https://quick-boutique.myshopify.com",
            "auth_method": "token",
            "access_token": "shpat_quick_token_12345",
            "warehouse_id": self.warehouse.id,
            "company_id": self.company.id,
            "test_connection_now": False,
        })

        res = store_wiz.action_create_store()
        self.assertEqual(res.get("type"), "ir.actions.client")
        self.assertEqual(res.get("tag"), "display_notification")
        self.assertEqual(res.get("params", {}).get("next", {}).get("type"), "ir.actions.act_window_close")

        # 4. Verify Instance was created properly in database
        new_inst = self.env["shopify.instance"].search([("shop_url", "=", "https://quick-boutique.myshopify.com")])
        self.assertTrue(new_inst)
        self.assertEqual(new_inst.name, "Quick Created Boutique")
        self.assertEqual(new_inst.warehouse_id.id, self.warehouse.id)
        self.assertEqual(new_inst.company_id.id, self.company.id)
        self.assertEqual(new_inst.state, "draft")
