{
    'name': 'Variant Stock Visibility',
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Odoo 19 Website eCommerce product variant stock visibility: grey out, disable, strike through and block out-of-stock product options, combinations, sizes and colors on the online shop',
    'description': """
Product Variant Stock Visibility
=================================
Prevents shoppers from selecting out-of-stock product variant options
(size, color, ...) on eCommerce product pages. Options that would resolve
to an out-of-stock variant are shown greyed out, struck through and
badged "Out of Stock", and are disabled from selection.

Controlled by a single checkbox in Website > Settings.
""",
    'author': 'Odooteck',
    'author_email': 'odooteck.apps@gmail.com',
    'license': 'OPL-1',
    'depends': ['website_sale_stock'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'odooteck_variant_stock_visibility/static/src/js/website_sale_stock_visibility.js',
            'odooteck_variant_stock_visibility/static/src/scss/website_sale_stock_visibility.scss',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': True,
}
