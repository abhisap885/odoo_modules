# -*- coding: utf-8 -*-
from odoo import models, fields, api

class TrainTrain(models.Model):
    _name = 'train.train'
    _description = 'Train Master'
    _order = 'number asc'

    name = fields.Char(string='Train Name', required=True)
    number = fields.Char(string='Train Number', required=True, index=True)
    train_type = fields.Selection([
        ('vande_bharat', 'Vande Bharat Express'),
        ('rajdhani', 'Rajdhani Express'),
        ('shatabdi', 'Shatabdi Express'),
        ('duronto', 'Duronto Express'),
        ('superfast', 'Superfast Express'),
        ('express', 'Mail / Express'),
    ], string='Train Type', default='express', required=True)

    source_station_id = fields.Many2one('train.station', string='Origin Station', required=True)
    destination_station_id = fields.Many2one('train.station', string='Destination Station', required=True)

    departure_time = fields.Char(string='Departure Time (24h)', default='06:00', help='HH:MM in 24h format')
    arrival_time = fields.Char(string='Arrival Time (24h)', default='14:00', help='HH:MM in 24h format')
    duration_hours = fields.Float(string='Duration (Hours)', default=8.0)
    running_days = fields.Char(string='Running Days', default='Daily', help='e.g. Daily or Mon, Wed, Fri')

    fare_rule_ids = fields.One2many('train.fare.rule', 'train_id', string='Class & Fare Inventory')
    booking_ids = fields.One2many('train.booking', 'train_id', string='Bookings')
    booking_count = fields.Integer(string='Bookings Count', compute='_compute_booking_count')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('number_unique', 'unique(number)', 'Train number must be unique!'),
    ]

    @api.depends('booking_ids')
    def _compute_booking_count(self):
        for record in self:
            record.booking_count = len(record.booking_ids)

    @api.depends('number', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.number} - {record.name}" if record.number and record.name else (record.name or record.number or "")
