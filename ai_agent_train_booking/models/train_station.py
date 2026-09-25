# -*- coding: utf-8 -*-
from odoo import models, fields, api

class TrainStation(models.Model):
    _name = 'train.station'
    _description = 'Railway Station'
    _order = 'code asc'

    name = fields.Char(string='Station Name', required=True, index=True)
    code = fields.Char(string='Station Code', required=True, index=True, size=10)
    city = fields.Char(string='City', index=True)
    state_name = fields.Char(string='State')
    zone = fields.Char(string='Railway Zone')
    active = fields.Boolean(default=True)

    originating_train_ids = fields.One2many('train.train', 'source_station_id', string='Originating Trains')
    terminating_train_ids = fields.One2many('train.train', 'destination_station_id', string='Terminating Trains')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The station code must be unique!'),
    ]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"[{record.code}] {record.name}" if record.code and record.name else (record.name or record.code or "")
