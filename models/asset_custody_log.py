# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class InstitutionalAssetCustodyLog(models.Model):
    _name = 'institutional.asset.custody.log'
    _description = 'Asset Lifecycle & Custody History Log'
    _order = 'event_date desc, id desc'

    asset_id = fields.Many2one('institutional.asset.item', string='Asset Tag / Code', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', related='asset_id.product_id', string='Asset Product', store=True)
    serial_number = fields.Char(related='asset_id.serial_number', string='Serial Number', store=True)

    event_type = fields.Selection([
        ('acquisition', 'Acquisition / Store Receipt'),
        ('issue', 'Custody Check-Out / Issued'),
        ('return', 'Returned to Central Store'),
        ('transfer', 'Custody Transfer'),
        ('component_added', 'Component Composed / Attached'),
        ('component_removed', 'Component Decomposed / Detached'),
        ('component_swapped', 'Component Swapped / Replaced'),
        ('maintenance', 'Sent for Maintenance'),
        ('scrapped', 'Scrapped / Retired'),
    ], string='Lifecycle Event Type', required=True, default='issue')

    previous_holder_id = fields.Many2one('res.users', string='Previous Custodian')
    new_holder_id = fields.Many2one('res.users', string='New / Current Custodian')

    previous_department_id = fields.Many2one('hr.department', string='Previous Department')
    new_department_id = fields.Many2one('hr.department', string='New / Current Department')

    event_date = fields.Datetime(string='Event Date & Time', default=fields.Datetime.now, required=True)
    logged_by_id = fields.Many2one('res.users', string='Recorded By', default=lambda self: self.env.user, required=True)

    condition = fields.Selection([
        ('intact', 'Intact'),
        ('used', 'Used'),
        ('damaged', 'Damaged'),
    ], string='Condition at Event', default='intact')

    notes = fields.Text(string='Lifecycle Event Notes / Reason')
