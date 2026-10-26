# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    active_held_asset_count = fields.Integer(
        string='Active Held Assets',
        compute='_compute_institutional_holdings',
        help='Count of serialized assets currently held in custody by this employee.'
    )
    total_consumed_qty = fields.Float(
        string='Consumed Supplies Total',
        compute='_compute_institutional_holdings',
        help='Cumulative quantity of consumable supplies issued to this employee.'
    )
    total_requisition_count = fields.Integer(
        string='Total Requisitions',
        compute='_compute_institutional_holdings',
        help='Total requisitions submitted by this employee.'
    )
    held_asset_ids = fields.Many2many(
        'institutional.asset.item',
        compute='_compute_institutional_records',
        string='Active Equipment Custody'
    )
    consumed_line_ids = fields.Many2many(
        'institutional.store.requisition.line',
        compute='_compute_institutional_records',
        string='Cumulative Consumed Supplies Log'
    )

    def _compute_institutional_holdings(self):
        for emp in self:
            user = emp.user_id
            if user:
                emp.active_held_asset_count = self.env['institutional.asset.item'].search_count([
                    ('assigned_user_id', '=', user.id),
                    ('status', '=', 'issued')
                ])
                consumed_lines = self.env['institutional.store.requisition.line'].search([
                    ('requested_by_id', '=', user.id),
                    ('state', '=', 'done')
                ])
                emp.total_consumed_qty = sum(consumed_lines.mapped('issued_qty')) or sum(consumed_lines.mapped('approved_qty'))
                emp.total_requisition_count = self.env['institutional.store.requisition'].search_count([
                    ('requested_by_id', '=', user.id)
                ])
            else:
                emp.active_held_asset_count = 0
                emp.total_consumed_qty = 0.0
                emp.total_requisition_count = 0

    def _compute_institutional_records(self):
        for emp in self:
            user = emp.user_id
            if user:
                emp.held_asset_ids = self.env['institutional.asset.item'].search([
                    ('assigned_user_id', '=', user.id),
                    ('status', '=', 'issued')
                ])
                emp.consumed_line_ids = self.env['institutional.store.requisition.line'].search([
                    ('requested_by_id', '=', user.id),
                    ('state', '=', 'done')
                ])
            else:
                emp.held_asset_ids = self.env['institutional.asset.item']
                emp.consumed_line_ids = self.env['institutional.store.requisition.line']

    def action_view_held_assets(self):
        self.ensure_one()
        user = self.user_id
        return {
            'name': _('Active Held Equipment - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'institutional.asset.item',
            'view_mode': 'list,form',
            'domain': [('assigned_user_id', '=', user.id if user else False), ('status', '=', 'issued')],
            'context': {
                'default_assigned_user_id': user.id if user else False,
                'default_department_id': self.department_id.id if self.department_id else False,
                'default_status': 'issued',
            },
        }

    def action_view_consumed_supplies(self):
        self.ensure_one()
        user = self.user_id
        return {
            'name': _('Consumed Supplies - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'institutional.store.requisition.line',
            'view_mode': 'list,pivot',
            'domain': [('requested_by_id', '=', user.id if user else False), ('state', '=', 'done')],
            'context': {
                'search_default_group_dept': 1,
            },
        }

    def action_view_requisitions(self):
        self.ensure_one()
        user = self.user_id
        return {
            'name': _('Store Requisitions - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'institutional.store.requisition',
            'view_mode': 'list,form',
            'domain': [('requested_by_id', '=', user.id if user else False)],
            'context': {
                'default_requested_by_id': user.id if user else False,
                'default_department_id': self.department_id.id if self.department_id else False,
            },
        }
