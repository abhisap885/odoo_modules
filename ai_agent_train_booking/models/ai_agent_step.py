# -*- coding: utf-8 -*-
from odoo import models, fields

class AIAgentStep(models.Model):
    _name = 'ai.agent.step'
    _description = 'AI Agent Execution Step'
    _order = 'sequence asc, id asc'

    task_id = fields.Many2one('ai.agent.task', string='Task', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Step #', default=1)
    step_type = fields.Selection([
        ('thought', 'Reasoning / Plan'),
        ('tool_call', 'Tool Call'),
        ('observation', 'Tool Result'),
        ('final_answer', 'Final Output'),
    ], string='Step Type', default='thought', required=True)

    thought = fields.Text(string='Thought / Reasoning')
    tool_name = fields.Char(string='Tool Called')
    tool_args = fields.Text(string='Arguments (JSON)')
    tool_result = fields.Text(string='Result / Output')
    is_error = fields.Boolean(string='Is Error', default=False)
