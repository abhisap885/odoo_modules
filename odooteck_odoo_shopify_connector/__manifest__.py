# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck.
# See LICENSE file for full copyright and licensing details.

{
    "name": "Shopify Odoo Connector | Multi-Store Shopify Integration",
    "summary": """
        Connect Shopify stores with Odoo 19. Real-time bi-directional sync for products, variants, multi-location stock, sales orders, customers, metafields, refunds, and fulfillment tracking via Shopify GraphQL API.
    """,
    "description": """
Shopify Odoo Connector
Shopify Odoo Integration
Shopify Connector for Odoo 19
Odoo 19 Shopify Connector
Odoo Shopify Integration
Shopify Multi Store Odoo
Shopify Multi Location Inventory Odoo
Shopify Stock Sync by Warehouse
Shopify Inventory Management Odoo
Shopify Product Sync Odoo
Shopify Product Export Odoo
Shopify Product Variant Import Odoo
Shopify Order Sync Odoo
Shopify Sales Order Import Odoo
Shopify Order Management Odoo 19
Shopify Customer Sync Odoo
Shopify Fulfillment Tracking Odoo
Shopify Delivery Tracking Sync
Shopify Refund Credit Note Odoo
Shopify Return Management Odoo
Shopify Metafields Sync Odoo
Shopify Declarative Metafields Odoo
Shopify GraphQL API Odoo
Shopify OAuth 2.0 Odoo
Shopify Webhook HMAC SHA256 Odoo
Shopify Staging Feeds Odoo
Shopify Lossless Queue Odoo
Shopify Auto Invoice Odoo
Shopify Dropshipping Odoo
Shopify B2B Wholesale Odoo
Shopify POS Sync Odoo
Shopify eCommerce Bridge Odoo
Shopify Connector Odoo Community
Shopify Connector Odoo Enterprise
Shopify Connector Odoo.sh
Shopify Connector On Premise
Odoo Shopify App
Shopify Integration App for Odoo
    """,
    "author": "Odooteck",
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
    "images": ["static/description/banner.png"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "pre_init_hook": "pre_init_check",
}
