# -*- coding: utf-8 -*-
from odoo import models, fields, api

class TrainFareRule(models.Model):
    _name = 'train.fare.rule'
    _description = 'Train Fare and Quota Inventory'
    _order = 'train_id, travel_class asc'

    train_id = fields.Many2one('train.train', string='Train', required=True, ondelete='cascade')
    travel_class = fields.Selection([
        ('1A', 'AC First Class (1A)'),
        ('2A', 'AC 2 Tier (2A)'),
        ('3A', 'AC 3 Tier (3A)'),
        ('CC', 'AC Chair Car (CC)'),
        ('EC', 'Exec Chair Car (EC)'),
        ('SL', 'Sleeper (SL)'),
    ], string='Class', required=True)

    base_fare = fields.Float(string='Base Fare', required=True, default=500.0)
    total_seats = fields.Integer(string='Total Quota Seats', default=60)
    available_seats = fields.Integer(string='Available Seats', default=60)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ('train_class_unique', 'unique(train_id, travel_class)', 'Only one fare rule per class per train!'),
    ]

    @api.depends('train_id', 'travel_class', 'base_fare')
    def _compute_display_name(self):
        for record in self:
            c_label = dict(self._fields['travel_class'].selection).get(record.travel_class, record.travel_class)
            t_name = record.train_id.name if record.train_id else ""
            record.display_name = f"{t_name} - {c_label} (₹{record.base_fare})"
