# -*- coding: utf-8 -*-
from odoo import models, fields, api

class InstitutionalAssetComponentHistory(models.Model):
    _name = 'institutional.asset.component.history'
    _description = 'IT Hardware Component Movement & Transfer Audit History Log'
    _order = 'swap_date desc, id desc'

    asset_id = fields.Many2one('institutional.asset.item', string='Machine / Asset Device', required=False, ondelete='cascade')
    source_asset_id = fields.Many2one('institutional.asset.item', string='Source Machine / Asset', ondelete='set null')
    dest_asset_id = fields.Many2one('institutional.asset.item', string='Destination Machine / Asset', ondelete='set null')
    component_id = fields.Many2one('institutional.asset.component', string='Component Unit', ondelete='cascade')

    action_type = fields.Selection([
        ('installed', 'Component Installed / Composed'),
        ('removed', 'Component Removed / Decomposed'),
        ('transferred', 'Inter-Asset Transfer'),
        ('replaced', 'Component Swapped / Replaced'),
    ], string='Composition / Movement Action', default='replaced', required=True)

    swap_date = fields.Date(string='Movement Date', default=fields.Date.context_today, required=True)
    component_type = fields.Selection([
        ('ram', 'RAM Memory'),
        ('storage', 'Storage (SSD / HDD / Memory Card)'),
        ('processor', 'CPU Processor'),
        ('gpu', 'Graphics Card / GPU'),
        ('monitor', 'Display Monitor'),
        ('display', 'Laptop Display Screen'),
        ('charger', 'Power Charger / Adapter'),
        ('battery', 'Battery Pack'),
        ('cctv_camera', 'CCTV Camera Unit'),
        ('cctv_nvr', 'CCTV NVR / DVR Unit'),
        ('camera_lens', 'DSLR Camera Lens'),
        ('drawer', 'Almirah / Cabinet Drawer'),
        ('lock', 'Locking Mechanism'),
        ('keyboard', 'Keyboard'),
        ('mouse', 'Mouse'),
        ('ups', 'UPS / Power Supply'),
        ('other', 'Other Component'),
    ], string='Component Type', required=True)

    old_component_name = fields.Char(string='Source / Swapped Out Component', required=True)
    new_component_name = fields.Char(string='Destination / New Component', required=True)
    technician_id = fields.Many2one('res.users', string='Technician / Store Officer', default=lambda self: self.env.user)
    reason = fields.Text(string='Reason for Movement / Swap', required=True)
