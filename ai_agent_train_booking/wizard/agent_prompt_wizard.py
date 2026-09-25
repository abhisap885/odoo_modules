# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AgentBookingWizard(models.TransientModel):
    _name = 'agent.booking.wizard'
    _description = 'Interactive Agentic AI Booking Wizard'

    def _default_agent(self):
        default_agent_id = self.env['ir.config_parameter'].sudo().get_param('ai_agent_train_booking.default_agent_id')
        if default_agent_id:
            agent = self.env['ai.agent'].browse(int(default_agent_id))
            if agent.exists():
                return agent.id
        first_agent = self.env['ai.agent'].search([], limit=1)
        return first_agent.id if first_agent else False

    def _default_irctc(self):
        acc = self.env['irctc.credential'].search([('state', '=', 'active')], limit=1)
        return acc.id if acc else False

    agent_id = fields.Many2one('ai.agent', string='AI Agent', required=True, default=_default_agent)
    irctc_account_id = fields.Many2one('irctc.credential', string='Active IRCTC Account', default=_default_irctc)
    preset_prompt = fields.Selection([
        ('delhi_mumbai', 'Book Delhi (NDLS) to Mumbai (MMCT) in 2AC for Amit Sharma (Age 34, M) tomorrow'),
        ('delhi_kolkata', 'Book Delhi (NDLS) to Howrah (HWH) in 3AC for Sunita Verma (Age 29, F) on 2026-09-12'),
        ('search_delhi_mumbai', 'Search all trains running between New Delhi and Mumbai'),
        ('check_seats', 'Check seat availability for Train 12952 in 2A'),
        ('check_pnr', 'Check status for PNR-8947291038'),
    ], string='Sample Quick Prompts')

    prompt = fields.Text(
        string='Goal / Natural Language Instruction',
        required=True,
        default="Book a ticket from New Delhi to Mumbai tomorrow for Amit Sharma, age 34, male in 2AC"
    )

    state = fields.Selection([
        ('input', 'Enter Goal'),
        ('result', 'Execution Completed'),
    ], default='input')

    task_id = fields.Many2one('ai.agent.task', string='Agent Task', readonly=True)
    booking_id = fields.Many2one('train.booking', string='Generated Booking', readonly=True)
    execution_output = fields.Text(string='Agent Response', readonly=True)

    @api.onchange('preset_prompt')
    def _onchange_preset_prompt(self):
        presets = {
            'delhi_mumbai': "Book a 2AC ticket on Mumbai Rajdhani from Delhi (NDLS) to Mumbai (MMCT) for Amit Sharma, age 34, male tomorrow",
            'delhi_kolkata': "Book 1 ticket from New Delhi to Howrah in 3AC on 2026-09-12 for Sunita Verma, age 29, female",
            'search_delhi_mumbai': "Search all available trains from New Delhi to Mumbai",
            'check_seats': "Check seat availability for train 12952 in 2A",
            'check_pnr': "Check status of PNR-8947291038",
        }
        if self.preset_prompt in presets:
            self.prompt = presets[self.preset_prompt]

    def action_run_agent(self):
        self.ensure_one()
        task = self.env['ai.agent.task'].create({
            'agent_id': self.agent_id.id,
            'prompt': self.prompt,
        })
        task.action_run()

        self.write({
            'task_id': task.id,
            'booking_id': task.booking_id.id if task.booking_id else False,
            'execution_output': task.final_response,
            'state': 'result',
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agent.booking.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_booking(self):
        self.ensure_one()
        if not self.booking_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': f'Booking {self.booking_id.name}',
            'res_model': 'train.booking',
            'res_id': self.booking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_task(self):
        self.ensure_one()
        if not self.task_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': f'Task {self.task_id.name}',
            'res_model': 'ai.agent.task',
            'res_id': self.task_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_new_prompt(self):
        self.write({
            'state': 'input',
            'task_id': False,
            'booking_id': False,
            'execution_output': False,
            'prompt': '',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agent.booking.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_irctc_accounts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'IRCTC Accounts',
            'res_model': 'irctc.credential',
            'view_mode': 'list,form',
            'target': 'current',
        }
