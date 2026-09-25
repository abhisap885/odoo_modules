# -*- coding: utf-8 -*-
from odoo import models, fields, api
from ..utils.agent_engine import AgentExecutionEngine

class AIAgentTask(models.Model):
    _name = 'ai.agent.task'
    _description = 'AI Agent Execution Task'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        string='Task Reference', required=True, copy=False, readonly=True,
        default=lambda self: 'TASK-' + fields.Datetime.now().strftime('%Y%m%d%H%M%S'),
        tracking=True
    )
    agent_id = fields.Many2one('ai.agent', string='AI Agent', required=True, tracking=True)
    prompt = fields.Text(string='User Goal / Prompt', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('waiting_approval', 'Waiting Approval'),
        ('done', 'Completed'),
        ('failed', 'Failed'),
    ], string='Status', default='draft', tracking=True)

    booking_id = fields.Many2one('train.booking', string='Generated Booking', tracking=True)
    step_ids = fields.One2many('ai.agent.step', 'task_id', string='Execution Steps / Trace')
    step_count = fields.Integer(string='Steps Executed', compute='_compute_step_count')
    final_response = fields.Text(string='Agent Final Output')
    execution_time = fields.Float(string='Execution Time (sec)', readonly=True)

    @api.depends('step_ids')
    def _compute_step_count(self):
        for record in self:
            record.step_count = len(record.step_ids)

    def action_run(self):
        self.ensure_one()
        engine = AgentExecutionEngine(self)
        engine.run()
        return True

    def action_approve_and_confirm(self):
        self.ensure_one()
        if self.booking_id and self.booking_id.state == 'draft':
            self.booking_id.action_confirm()
            self.state = 'done'
            self.message_post(body=f"Booking {self.booking_id.name} approved and confirmed by user.")
        return True

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
