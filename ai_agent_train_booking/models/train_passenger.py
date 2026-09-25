# -*- coding: utf-8 -*-
from odoo import models, fields

class TrainBookingPassenger(models.Model):
    _name = 'train.booking.passenger'
    _description = 'Booking Passenger Detail'
    _order = 'id asc'

    booking_id = fields.Many2one('train.booking', string='Booking', required=True, ondelete='cascade')
    name = fields.Char(string='Passenger Full Name', required=True)
    age = fields.Integer(string='Age', required=True, default=30)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender', default='male', required=True)
    berth_preference = fields.Selection([
        ('lower', 'Lower Berth'),
        ('middle', 'Middle Berth'),
        ('upper', 'Upper Berth'),
        ('side_lower', 'Side Lower'),
        ('side_upper', 'Side Upper'),
        ('window', 'Window Seat'),
        ('no_preference', 'No Preference'),
    ], string='Berth Preference', default='no_preference')

    allocated_coach = fields.Char(string='Coach', readonly=True)
    allocated_berth = fields.Char(string='Berth / Seat No', readonly=True)
    allocated_berth_type = fields.Char(string='Berth Type', readonly=True)
    fare = fields.Float(string='Individual Fare')
