# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class IrctcCredential(models.Model):
    _name = 'irctc.credential'
    _description = 'IRCTC Account & API Credentials'
    _order = 'id desc'

    name = fields.Char(string='Account Name', required=True, default='Primary IRCTC Account')
    username = fields.Char(string='IRCTC User ID', required=True, help='Your official IRCTC login username')
    password = fields.Char(string='IRCTC Password', required=True)
    mobile_number = fields.Char(string='Registered Mobile No', help='Used for IRCTC 2FA / OTP verification')
    upi_id = fields.Char(string='Preferred UPI ID', help='e.g. yourname@okhdfcbank (for instant ticket payment)')

    integration_mode = fields.Selection([
        ('browser', 'Browser Automation Bot (Playwright / Web Bot)'),
        ('api', 'Live Indian Railways / IRCTC API (RapidAPI / PSP Gateway)'),
        ('simulation', 'Simulation Engine (Sandbox / Safe Test)'),
    ], string='Booking Mode', default='browser', required=True)

    api_key = fields.Char(string='API Key', help='Required if using Live Indian Railways API')
    api_host = fields.Char(string='API Host URL', default='irctc1.p.rapidapi.com')

    captcha_solving_mode = fields.Selection([
        ('ai_vision', 'AI Vision Auto-Solve (Gemini / Claude OCR)'),
        ('manual', 'Human-in-the-Loop (Popup Captcha in Odoo)'),
    ], string='Captcha Handling', default='ai_vision', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Verified & Active'),
        ('error', 'Authentication Failed'),
    ], string='Status', default='draft')

    last_verification = fields.Datetime(string='Last Tested On', readonly=True)
    notes = fields.Text(string='Compliance & Safety Notes', default="""IMPORTANT COMPLIANCE NOTE:
1. Automated ticket booking must comply with IRCTC Terms of Service and Indian Railways regulations.
2. For commercial travel agencies, IRCTC Principal Service Provider (PSP) license is mandatory.
3. For personal automation, browser automation operates under human supervision for Captcha/Payment confirmation.""")

    def action_test_connection(self):
        self.ensure_one()
        self.last_verification = fields.Datetime.now()
        if self.integration_mode == 'api':
            if not self.api_key:
                raise UserError("Please enter your API Key to test live API connection!")
            # Test API call
            from ..utils.irctc_service import IrctcApiService
            service = IrctcApiService(self.api_key, self.api_host)
            res = service.test_connection()
            if res.get('status') == 'success':
                self.state = 'active'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'IRCTC API Connected!',
                        'message': 'Successfully connected to Live Indian Railways API endpoint.',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                self.state = 'error'
                raise UserError(f"API Connection Failed: {res.get('message')}")
        else:
            # Browser automation credentials validation
            if not self.username or not self.password:
                raise UserError("Username and password are required for IRCTC Browser Automation!")
            self.state = 'active'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'IRCTC Credentials Saved!',
                    'message': f"Account '{self.username}' is configured for automated browser booking.",
                    'type': 'success',
                    'sticky': False,
                }
            }
