# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck.
# See LICENSE file for full copyright and licensing details.

{
    "name": "Shopify Connector for Odoo 19",
    "summary": "Connect Shopify stores with Odoo 19 for product, order, customer, inventory, and fulfillment workflows.",
    "description": """
Shopify Connector for Odoo 19
=============================

Connect Shopify stores to Odoo 19 and manage integration activity from your Odoo workspace.

Features include:
* Configure multiple Shopify store connections.
* Review product, variant, order, customer, and collection staging feeds.
* Maintain Shopify-to-Odoo product, variant, and order mappings.
* Sync stock levels to Shopify locations and update fulfillment information after delivery validation.
* Verify incoming webhooks with HMAC-SHA256 signatures.
* Review synchronization history, results, record counts, and logs.

Compatible with Odoo 19 Community and Enterprise, Odoo.sh, and On-Premise.
    """,
    "author": "Odooteck",
    "category": "eCommerce",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
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
    "images": ["static/description/Banner.gif"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "pre_init_hook": "pre_init_check",
}
