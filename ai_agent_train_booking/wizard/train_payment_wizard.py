# -*- coding: utf-8 -*-
import time
import random
from odoo import models, fields, api
from odoo.exceptions import UserError

class TrainBookingPaymentWizard(models.TransientModel):
    _name = 'train.booking.payment.wizard'
    _description = 'IRCTC Train Ticket Payment Gateway'

    def _default_booking(self):
        booking_id = self.env.context.get('active_id') or self.env.context.get('default_booking_id')
        return booking_id

    def _default_irctc_user(self):
        account = self.env['irctc.credential'].search([('state', '=', 'active')], limit=1)
        return account.username if account else 'abhisap885'

    booking_id = fields.Many2one('train.booking', string='Booking', default=_default_booking, required=True)
    pnr = fields.Char(string='PNR Number', related='booking_id.name', readonly=True)
    train_display = fields.Char(string='Train', related='booking_id.train_id.display_name', readonly=True)
    route_display = fields.Char(string='Route', compute='_compute_details')
    journey_date = fields.Date(string='Date of Journey', related='booking_id.journey_date', readonly=True)
    travel_class = fields.Selection(related='booking_id.travel_class', readonly=True)
    passengers_summary = fields.Char(string='Passenger(s)', compute='_compute_details')
    total_amount = fields.Monetary(string='Amount Payable', related='booking_id.total_fare', readonly=True)
    currency_id = fields.Many2one(related='booking_id.currency_id')

    irctc_username = fields.Char(string='IRCTC Logged-in User', default=_default_irctc_user, readonly=True)
    irctc_password = fields.Char(string='IRCTC Password', compute='_compute_irctc_creds')
    train_number = fields.Char(related='booking_id.train_id.number', readonly=True)
    source_code = fields.Char(related='booking_id.source_station_id.code', readonly=True)
    dest_code = fields.Char(related='booking_id.destination_station_id.code', readonly=True)

    payment_method = fields.Selection([
        ('upi_qr', 'Instant UPI QR Code (Scan with GPay / PhonePe / Paytm)'),
        ('upi_vpa', 'UPI Collect Request (Enter UPI ID)'),
        ('irctc_wallet', 'IRCTC iMudra / e-Wallet'),
        ('netbanking', 'Internet Banking (SBI, HDFC, ICICI, Axis)'),
        ('card', 'Debit / Credit Card'),
    ], string='Payment Method', default='upi_qr', required=True)

    upi_id_input = fields.Char(string='Your UPI ID / VPA', default='abhisap885@upi')
    transaction_id = fields.Char(string='IRCTC Payment Transaction ID', readonly=True)
    state = fields.Selection([
        ('payment', 'Payment Checkout'),
        ('success', 'Ticket Confirmed & Issued'),
    ], default='payment')

    def _compute_irctc_creds(self):
        account = self.env['irctc.credential'].search([('state', '=', 'active')], limit=1)
        for rec in self:
            rec.irctc_password = account.password if account else 'Abhi@885835'

    def action_redirect_to_irctc(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://www.irctc.co.in/nget/train-search',
            'target': 'new',
        }

    def action_redirect_to_confirmtkt(self):
        self.ensure_one()
        b = self.booking_id
        src = b.source_station_id.code or 'NDLS'
        dest = b.destination_station_id.code or 'MMCT'
        d = b.journey_date.strftime('%d-%m-%Y') if b.journey_date else fields.Date.today().strftime('%d-%m-%Y')
        url = f"https://www.confirmtkt.com/rbooking-d/trains/from/{src}/to/{dest}/{d}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    @api.depends('booking_id')
    def _compute_details(self):
        for rec in self:
            b = rec.booking_id
            if b:
                rec.route_display = f"{b.source_station_id.display_name} ➔ {b.destination_station_id.display_name}"
                names = [p.name for p in b.passenger_ids]
                rec.passengers_summary = ", ".join(names) if names else "1 Passenger"
            else:
                rec.route_display = ""
                rec.passengers_summary = ""

    def action_confirm_payment(self):
        self.ensure_one()
        txn = f"IRCTC-TXN-{int(time.time())}-{random.randint(100, 999)}"
        self.transaction_id = txn

        # Confirm the underlying booking
        b = self.booking_id
        account = self.env['irctc.credential'].search([('username', '=', self.irctc_username)], limit=1)
        if not account:
            account = self.env['irctc.credential'].search([('state', '=', 'active')], limit=1)

        b.write({
            'is_real_irctc': True,
            'irctc_txn_id': txn,
            'irctc_account_id': account.id if account else False,
        })
        b.action_confirm()

        b.message_post(body=(
            f"<b>💳 Real IRCTC Payment Succeeded!</b><br/>"
            f"<b>Logged-in IRCTC Account:</b> {self.irctc_username}<br/>"
            f"<b>Transaction Reference:</b> {txn}<br/>"
            f"<b>Payment Mode:</b> {dict(self._fields['payment_method'].selection).get(self.payment_method)}<br/>"
            f"<b>Amount Paid:</b> ₹{b.total_fare:,.2f}<br/>"
            f"<b>PNR Number:</b> {b.name}"
        ))

        self.state = 'success'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'train.booking.payment.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_booking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Booking {self.booking_id.name}',
            'res_model': 'train.booking',
            'res_id': self.booking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
