# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    train_ai_agent_id = fields.Many2one(
        'ai.agent', string='Default Train Booking Agent',
        config_parameter='ai_agent_train_booking.default_agent_id'
    )
    auto_confirm_bookings = fields.Boolean(
        string='Auto-Confirm Bookings Automatically',
        config_parameter='ai_agent_train_booking.auto_confirm_bookings',
        default=True
    )
