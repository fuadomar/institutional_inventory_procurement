# -*- coding: utf-8 -*-
from odoo import models, fields, api

class InstitutionalRequisitionAudit(models.Model):
    _name = 'institutional.requisition.audit'
    _description = 'Store Requisition Audit Log'
    _order = 'modified_date desc, id desc'

    requisition_id = fields.Many2one('institutional.store.requisition', string='Requisition Reference', required=True, ondelete='cascade')
    line_id = fields.Many2one('institutional.store.requisition.line', string='Requisition Line')
    product_id = fields.Many2one('product.product', string='Product Item')
    modified_by_id = fields.Many2one('res.users', string='Modified By', default=lambda self: self.env.user, required=True)
    modified_date = fields.Datetime(string='Modification Timestamp', default=fields.Datetime.now, required=True)

    audit_type = fields.Selection([
        ('qty_change', 'Quantity Modification by Store Incharge'),
        ('backdate', 'Back-dated Transaction Entry'),
        ('approval', 'Approval Workflow Step'),
    ], string='Audit Action Type', default='qty_change', required=True)

    original_qty = fields.Float(string='Original Requested Qty')
    new_qty = fields.Float(string='Modified Approved Qty')
    reason = fields.Text(string='Reason for Modification / Audit Notes')
    details = fields.Text(string='Audit Trace Details')
