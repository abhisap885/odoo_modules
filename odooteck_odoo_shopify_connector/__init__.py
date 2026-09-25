# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck.
# See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard
from . import controllers

def pre_init_check(*args, **kwargs):
    from odoo.service import common
    from odoo.exceptions import UserError
    version_info = common.exp_version()
    server_serie = version_info.get("server_serie", "")
    if server_serie and not server_serie.startswith("19"):
        try:
            val = float(server_serie.split("~")[-1].split("a")[0].split("b")[0])
            if not (18.0 < val <= 19.0):
                raise UserError(f"Shopify Odoo Connector requires Odoo 19.0 series, detected: {server_serie}")
        except (ValueError, TypeError):
            pass
