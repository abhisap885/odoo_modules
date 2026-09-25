# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck (<https://www.odooteck.com/>).
# See LICENSE file for full copyright and licensing details.

{
    "name": "Shopify Odoo Connector",
    "summary": "Shopify connector for Odoo 19: eCommerce product, order, customer, inventory and fulfillment sync.",
    "description": """
Shopify Odoo Connector
========================================
A Shopify Odoo connector for eCommerce data synchronization on Odoo 19:
- Product, variant, order, customer, inventory, and fulfillment synchronization.
- Direct Shopify Admin REST API integration (no third-party dependencies).
- Multi-instance support: Connect and manage multiple Shopify stores in one Odoo database.
- Staging queue (Feeds) for resilient, loss-free data ingestion.
- Bidirectional mapping for products, variants, orders, customers, collections, and taxes.
- Real-time stock level synchronization from Odoo warehouses to Shopify locations.
- Fulfillment tracking synchronization upon delivery confirmation.
- Secure webhooks with HMAC-SHA256 signature verification.
- Odoo 19 3-Tier Security compliant (res.groups.privilege).
    """,
    "author": "Odooteck",
    "website": "https://www.odooteck.com",
    "category": "eCommerce",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "price": 100.0,
    "currency": "USD",
    "depends": [
        "base",
        "sale_management",
        "stock",
        "account",
    ],
    "data": [
        # 1. Security (Privileges, Groups, Access Control Lists)
        "security/security.xml",
        "security/ir.model.access.csv",

        # 2. System Data & Scheduled Actions
        "data/data.xml",
        "data/cron.xml",

        # 3. Wizards (loaded before views referencing wizard actions)
        "views/shopify_sync_wizard_views.xml",
        "views/shopify_product_export_wizard_views.xml",
        "views/shopify_onboarding_wizard_views.xml",
        "views/shopify_store_create_wizard_views.xml",

        # 4. Core Views
        "views/shopify_instance_views.xml",
        "views/shopify_feed_views.xml",
        "views/shopify_mapping_views.xml",
        "views/shopify_sync_history_views.xml",
        "views/inherited_views.xml",

        # 5. Menus (Hierarchy & Actions)
        "views/menus.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "odooteck_odoo_shopify_connector/static/src/scss/shopify_kanban.scss",
            "odooteck_odoo_shopify_connector/static/src/scss/shopify_insights.scss",
            "odooteck_odoo_shopify_connector/static/src/js/shopify_insights_dashboard.js",
            "odooteck_odoo_shopify_connector/static/src/xml/shopify_insights_dashboard.xml",
        ],
    },
    "images": ["static/description/banner.gif"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "pre_init_hook": "pre_init_check",
}
