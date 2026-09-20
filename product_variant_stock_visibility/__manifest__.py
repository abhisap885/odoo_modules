{
    'name': 'Variant Stock Visibility',
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Grey out and block selection of out-of-stock product variant options on the website shop',
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
    'license': 'Other proprietary',
    'depends': ['website_sale_stock'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'product_variant_stock_visibility/static/src/js/website_sale_stock_visibility.js',
            'product_variant_stock_visibility/static/src/scss/website_sale_stock_visibility.scss',
        ],
    },
    'images': [
        'static/description/banner.gif',
    ],
    'installable': True,
    'application': True,
}
