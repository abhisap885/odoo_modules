# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck.
# See LICENSE file for full copyright and licensing details.

{
    "name": "Shopify Odoo Connector",
    "summary": """
        Sync Shopify with Odoo — products, orders, customers, inventory & fulfillment.
        Multi-store support, real-time webhooks, automated staging feeds, and full audit logs.
        Works with Odoo 19 Community, Enterprise, Odoo.sh and On-Premise.
    """,
    "description": """
Shopify Odoo Connector
Shopify Odoo Integration
Shopify Connector for Odoo
Odoo Shopify Sync
Shopify Odoo Product Sync
Shopify Odoo Order Sync
Shopify Odoo Inventory Sync
Shopify Odoo Customer Sync
Shopify Odoo Fulfillment
Shopify Multi Store Odoo
Shopify Webhook Odoo
Shopify Odoo eCommerce
Shopify Odoo 19
Shopify Odoo 18
Shopify Odoo 20
Odoo Shopify Integration App
Shopify Connector Odoo Community
Shopify Connector Odoo Enterprise
Shopify Odoo Mapping
Shopify Staging Feed Odoo
Shopify Odoo Sync History
Shopify Stock Sync Odoo
Shopify Product Import Odoo
Shopify Order Import Odoo
Shopify Customer Import Odoo
Odoo eCommerce Shopify Bridge
Shopify Odoo Automation
    """,
    "author": "Odooteck",
    "website": "https://store.odooteck.com/odoo-shopify-connector.html",
    "live_test_url": "https://odoodemo.odooteck.com/?module=odooteck_odoo_shopify_connector&version=19.0",
    "category": "eCommerce",
    "sequence": 1,
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
