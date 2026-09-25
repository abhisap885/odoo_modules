# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AIAgent(models.Model):
    _name = 'ai.agent'
    _description = 'Autonomous AI Agent'
    _order = 'name asc'

    name = fields.Char(string='Agent Name', required=True, default='RailBot - Train Booking Agent')
    provider = fields.Selection([
        ('simulated', 'Autonomous Local Engine (No API Key Required)'),
        ('openai', 'OpenAI (GPT-4o / GPT-4o-mini)'),
        ('gemini', 'Google Gemini (Gemini 1.5 Flash/Pro)'),
        ('anthropic', 'Anthropic Claude (Claude 3.5 Sonnet)'),
        ('ollama', 'Local Ollama (Llama 3 / Mistral)'),
    ], string='AI Provider', default='simulated', required=True)

    api_key = fields.Char(string='API Key')
    model = fields.Char(string='Model Name', default='gpt-4o-mini')
    base_url = fields.Char(string='Custom Base URL')
    system_prompt = fields.Text(string='System Instructions / Persona', default="""You are RailBot, an autonomous agentic AI in Odoo responsible for train ticket booking and travel operations.
You have direct access to database tools:
- search_trains: Find trains between stations.
- check_seat_availability: Check available berths and class fare.
- book_train_ticket: Create and reserve ticket in Odoo.
- confirm_ticket: Finalize ticket, assign coach and berth numbers.
- get_pnr_status: Track status of any PNR.
- cancel_ticket: Cancel reservation and restore seats.

Always reason step-by-step to fulfill the user request autonomously.""")

    autonomous_level = fields.Selection([
        ('full_auto', 'Fully Autonomous (Search, Book & Confirm)'),
        ('human_in_the_loop', 'Supervised (Reserve & Wait for Approval)'),
    ], string='Autonomy Level', default='full_auto', required=True)

    max_iterations = fields.Integer(string='Max Iterations', default=6)
    tool_ids = fields.Many2many('ai.agent.tool', string='Enabled Tools')
    task_ids = fields.One2many('ai.agent.task', 'agent_id', string='Execution Tasks')
    task_count = fields.Integer(string='Tasks Count', compute='_compute_task_count')
    booking_count = fields.Integer(string='Bookings Count', compute='_compute_booking_count')
    active = fields.Boolean(default=True)

    @api.depends('task_ids')
    def _compute_task_count(self):
        for record in self:
            record.task_count = len(record.task_ids)

    def _compute_booking_count(self):
        booking_obj = self.env['train.booking']
        for record in self:
            record.booking_count = booking_obj.search_count([('ai_task_id', 'in', record.task_ids.ids)])

    def action_open_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Run Agent: {self.name}',
            'res_model': 'agent.booking.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_agent_id': self.id},
        }

    def action_view_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Tasks: {self.name}',
            'res_model': 'ai.agent.task',
            'view_mode': 'list,form',
            'domain': [('agent_id', '=', self.id)],
            'context': {'default_agent_id': self.id},
        }

    def action_view_bookings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Bookings by {self.name}',
            'res_model': 'train.booking',
            'view_mode': 'list,form',
            'domain': [('ai_task_id', 'in', self.task_ids.ids)],
        }
