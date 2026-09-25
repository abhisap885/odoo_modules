# -*- coding: utf-8 -*-
# Part of Shopify Odoo Connector. Copyright (c) Odooteck.
# See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard
from . import controllers

from odoo.exceptions import ValidationError

TARGET_ODOO_SERIES = "20.0"

def pre_init_check(env):
    """Block installation on wrong Odoo series."""
    from odoo.service import common
    version_info = common.exp_version()
    server_serie = version_info.get("server_serie")
    if server_serie != TARGET_ODOO_SERIES:
        raise ValidationError(
            "Module supports Odoo series {} — found {}.".format(
                TARGET_ODOO_SERIES, server_serie
            )
        )
