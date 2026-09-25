# -*- coding: utf-8 -*-
import random
from odoo import models, fields, api
from odoo.exceptions import UserError

class TrainBooking(models.Model):
    _name = 'train.booking'
    _description = 'Train Ticket Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='PNR Number', required=True, copy=False, readonly=True,
        default='New', tracking=True, index=True
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer / Passenger Contact',
        default=lambda self: self.env.user.partner_id, tracking=True
    )
    train_id = fields.Many2one('train.train', string='Train', required=True, tracking=True)
    source_station_id = fields.Many2one(
        'train.station', string='Origin Station', required=True,
        related='train_id.source_station_id', store=True, readonly=False
    )
    destination_station_id = fields.Many2one(
        'train.station', string='Destination Station', required=True,
        related='train_id.destination_station_id', store=True, readonly=False
    )
    journey_date = fields.Date(string='Journey Date', required=True, tracking=True, default=fields.Date.today)
    travel_class = fields.Selection([
        ('1A', 'AC First Class (1A)'),
        ('2A', 'AC 2 Tier (2A)'),
        ('3A', 'AC 3 Tier (3A)'),
        ('CC', 'AC Chair Car (CC)'),
        ('EC', 'Exec Chair Car (EC)'),
        ('SL', 'Sleeper (SL)'),
    ], string='Class', required=True, default='3A', tracking=True)

    passenger_ids = fields.One2many('train.booking.passenger', 'booking_id', string='Passengers')
    passenger_count = fields.Integer(string='Passengers Count', compute='_compute_passenger_count', store=True)

    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    total_fare = fields.Monetary(
        string='Total Fare', compute='_compute_total_fare', store=True,
        currency_field='currency_id', tracking=True
    )

    state = fields.Selection([
        ('draft', 'Reserved / Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    booking_type = fields.Selection([
        ('manual', 'Manual Booking'),
        ('agentic_ai', 'Agentic AI Autonomous'),
    ], string='Booking Mode', default='manual', tracking=True)

    ai_task_id = fields.Many2one('ai.agent.task', string='AI Task Origin', readonly=True)
    irctc_account_id = fields.Many2one('irctc.credential', string='IRCTC User Account', tracking=True)
    is_real_irctc = fields.Boolean(string='Real IRCTC Live Booking', default=False, tracking=True)
    irctc_txn_id = fields.Char(string='IRCTC Transaction ID', readonly=True, copy=False)
    booking_notes = fields.Text(string='Notes / AI Commentary')
    booking_date = fields.Datetime(string='Booked On', default=fields.Datetime.now, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self._generate_pnr()
        return super().create(vals_list)

    @api.model
    def _generate_pnr(self):
        # Generates a realistic 10-digit Indian Railways style PNR: e.g. PNR-2849102847
        random_digits = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        return f"PNR-{random_digits}"

    @api.depends('passenger_ids')
    def _compute_passenger_count(self):
        for record in self:
            record.passenger_count = len(record.passenger_ids)

    @api.depends('passenger_ids.fare', 'train_id', 'travel_class')
    def _compute_total_fare(self):
        for record in self:
            sum_passenger_fare = sum(record.passenger_ids.mapped('fare'))
            if sum_passenger_fare > 0:
                record.total_fare = sum_passenger_fare
            else:
                rule = self.env['train.fare.rule'].search([
                    ('train_id', '=', record.train_id.id),
                    ('travel_class', '=', record.travel_class)
                ], limit=1)
                unit_fare = rule.base_fare if rule else 500.0
                record.total_fare = unit_fare * max(1, len(record.passenger_ids))

    def action_confirm(self):
        self.ensure_one()
        if not self.passenger_ids:
            raise UserError("Cannot confirm booking without at least one passenger!")

        rule = self.env['train.fare.rule'].search([
            ('train_id', '=', self.train_id.id),
            ('travel_class', '=', self.travel_class)
        ], limit=1)

        passenger_count = len(self.passenger_ids)
        if rule:
            if rule.available_seats < passenger_count:
                raise UserError(f"Insufficient seats available on train {self.train_id.number} in class {self.travel_class}. Remaining: {rule.available_seats}, requested: {passenger_count}.")
            rule.available_seats = max(0, rule.available_seats - passenger_count)

        # Allocate Coach and Berth
        coach_prefixes = {
            '1A': 'H1',
            '2A': 'A1',
            '3A': 'B2',
            'CC': 'C1',
            'EC': 'E1',
            'SL': 'S3',
        }
        coach = coach_prefixes.get(self.travel_class, 'B1')
        berth_types = ['Lower', 'Middle', 'Upper', 'Side Lower', 'Side Upper'] if self.travel_class in ['3A', 'SL'] else ['Lower', 'Upper'] if self.travel_class in ['1A', '2A'] else ['Window', 'Aisle', 'Middle']

        seat_details = []
        for idx, passenger in enumerate(self.passenger_ids, start=1):
            if not passenger.allocated_coach:
                passenger.allocated_coach = coach
            if not passenger.allocated_berth:
                berth_no = random.randint(1, 64)
                passenger.allocated_berth = str(berth_no)
                passenger.allocated_berth_type = berth_types[(berth_no - 1) % len(berth_types)]
            if not passenger.fare and rule:
                passenger.fare = rule.base_fare
            seat_details.append(f"{passenger.name} -> Coach {passenger.allocated_coach}, Berth {passenger.allocated_berth} ({passenger.allocated_berth_type})")

        self.state = 'confirmed'
        chatter_msg = f"<b>Train Booking Confirmed!</b><br/>"                       f"<b>PNR:</b> {self.name}<br/>"                       f"<b>Train:</b> {self.train_id.display_name}<br/>"                       f"<b>Date:</b> {self.journey_date}<br/>"                       f"<b>Seats Allocated:</b><br/>" + "<br/>".join(seat_details) +                       f"<br/><b>Total Amount:</b> ₹{self.total_fare:,.2f}"
        self.message_post(body=chatter_msg)
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'confirmed':
            rule = self.env['train.fare.rule'].search([
                ('train_id', '=', self.train_id.id),
                ('travel_class', '=', self.travel_class)
            ], limit=1)
            if rule:
                rule.available_seats = min(rule.total_seats, rule.available_seats + len(self.passenger_ids))

        self.state = 'cancelled'
        self.message_post(body=f"Booking {self.name} has been cancelled. Seats returned to quota.")
        return True

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_open_payment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'IRCTC Payment Checkout',
            'res_model': 'train.booking.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_booking_id': self.id},
        }

    def action_book_on_irctc(self):
        self.ensure_one()
        account = self.irctc_account_id or self.env['irctc.credential'].search([('state', '=', 'active')], limit=1)
        if not account:
            account = self.env['irctc.credential'].search([], limit=1)
        if not account:
            raise UserError("Please configure an IRCTC Account under IRCTC Accounts menu first!")

        self.write({
            'is_real_irctc': True,
            'irctc_account_id': account.id,
        })

        self.message_post(body=(
            f"<b>🌐 Redirecting to Official IRCTC Portal (irctc.co.in)...</b><br/>"
            f"<b>IRCTC Login ID:</b> {account.username}<br/>"
            f"<b>Train:</b> {self.train_id.display_name}<br/>"
            f"<b>Route:</b> {self.source_station_id.code} ➔ {self.destination_station_id.code}<br/>"
            f"<b>Journey Date:</b> {self.journey_date}<br/>"
            f"<b>Passenger:</b> {', '.join(self.passenger_ids.mapped('name')) or '1 Passenger'}<br/>"
            f"<b>Class:</b> {self.travel_class}"
        ))

        return {
            'type': 'ir.actions.act_url',
            'url': 'https://www.irctc.co.in/nget/train-search',
            'target': 'new',
        }

    def action_open_confirmtkt(self):
        self.ensure_one()
        src = self.source_station_id.code or 'NDLS'
        dest = self.destination_station_id.code or 'MMCT'
        d = self.journey_date.strftime('%d-%m-%Y') if self.journey_date else fields.Date.today().strftime('%d-%m-%Y')
        url = f"https://www.confirmtkt.com/rbooking-d/trains/from/{src}/to/{dest}/{d}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
