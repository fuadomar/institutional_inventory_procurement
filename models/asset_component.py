# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class InstitutionalAssetComponent(models.Model):
    _name = 'institutional.asset.component'
    _description = 'IT Hardware Asset Component'

    asset_id = fields.Many2one('institutional.asset.item', string='Computer / Asset Device', required=False, ondelete='set null')
    status = fields.Selection([
        ('installed', 'Installed / Composed'),
        ('unassigned_spare', 'Unassigned Spare'),
        ('maintenance', 'Under Maintenance / Defective'),
        ('scrapped', 'Scrapped'),
    ], string='Component Status', default='installed', required=True)

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
        ('other', 'Other Hardware Component'),
    ], string='Component Type', required=True, default='ram')

    name = fields.Char(string='Component Model & Brand', required=True)
    serial_number = fields.Char(string='Serial Number')
    capacity_or_spec = fields.Char(string='Capacity / Specification', help='e.g. 16GB DDR4, 512GB NVMe SSD, 24" FHD')
    condition = fields.Selection([
        ('intact', 'Intact'),
        ('used', 'Used'),
        ('damaged', 'Damaged'),
    ], string='Component Condition', default='intact', required=True)
    installed_date = fields.Date(string='Installed Date', default=fields.Date.context_today)
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        records = super(InstitutionalAssetComponent, self).create(vals_list)
        for rec in records:
            if rec.asset_id:
                note_text = f"Hardware Composition: Attached component '{rec.name}' ({rec.capacity_or_spec or 'N/A'})."
                # Log composition / attachment event in component history log
                self.env['institutional.asset.component.history'].sudo().create({
                    'asset_id': rec.asset_id.id,
                    'source_asset_id': False,
                    'dest_asset_id': rec.asset_id.id,
                    'component_id': rec.id,
                    'component_type': rec.component_type,
                    'action_type': 'installed',
                    'old_component_name': 'New Hardware Component',
                    'new_component_name': f"Installed: {rec.name} ({rec.capacity_or_spec or 'N/A'})",
                    'swap_date': rec.installed_date or fields.Date.today(),
                    'technician_id': self.env.user.id,
                    'reason': note_text,
                })
                # ALSO log in Asset Lifecycle & Custody Trail
                self.env['institutional.asset.custody.log'].sudo().create({
                    'asset_id': rec.asset_id.id,
                    'event_type': 'component_added',
                    'new_holder_id': rec.asset_id.assigned_user_id.id if rec.asset_id.assigned_user_id else False,
                    'new_department_id': rec.asset_id.department_id.id if rec.asset_id.department_id else False,
                    'condition': rec.asset_id.condition,
                    'notes': note_text,
                })
        return records

    def write(self, vals):
        for rec in self:
            old_asset = rec.asset_id
            res = super(InstitutionalAssetComponent, rec).write(vals)
            new_asset = rec.asset_id
            
            # Log event if component asset_id changes from False/None to a target asset device
            if 'asset_id' in vals and not old_asset and new_asset:
                note_text = f"Hardware Composition: Spare component '{rec.name}' ({rec.capacity_or_spec or 'N/A'}) attached to asset machine {new_asset.name}."
                self.env['institutional.asset.component.history'].sudo().create({
                    'asset_id': new_asset.id,
                    'source_asset_id': False,
                    'dest_asset_id': new_asset.id,
                    'component_id': rec.id,
                    'component_type': rec.component_type,
                    'action_type': 'installed',
                    'old_component_name': 'Unassigned Store Spare',
                    'new_component_name': f"Attached: {rec.name} ({rec.capacity_or_spec or 'N/A'})",
                    'swap_date': fields.Date.today(),
                    'technician_id': self.env.user.id,
                    'reason': note_text,
                })
                # ALSO log in Asset Lifecycle & Custody Trail
                self.env['institutional.asset.custody.log'].sudo().create({
                    'asset_id': new_asset.id,
                    'event_type': 'component_added',
                    'new_holder_id': new_asset.assigned_user_id.id if new_asset.assigned_user_id else False,
                    'new_department_id': new_asset.department_id.id if new_asset.department_id else False,
                    'condition': new_asset.condition,
                    'notes': note_text,
                })
        return res

    def action_detach_component(self):
        """Decomposition: Detach component from asset machine and set as unassigned spare"""
        for rec in self:
            if not rec.asset_id:
                raise UserError(_("Component '%s' is not attached to any asset.") % rec.name)
            source_asset = rec.asset_id
            note_text = f"Hardware Decomposition: Detached component '{rec.name}' ({rec.capacity_or_spec or 'N/A'}) from {source_asset.name} and set as spare in store."
            rec.write({
                'asset_id': False,
                'status': 'unassigned_spare',
            })
            # Log decomposition event in Component History
            self.env['institutional.asset.component.history'].sudo().create({
                'asset_id': source_asset.id,
                'source_asset_id': source_asset.id,
                'dest_asset_id': False,
                'component_id': rec.id,
                'component_type': rec.component_type,
                'action_type': 'removed',
                'old_component_name': f"{rec.name} ({rec.capacity_or_spec or 'N/A'})",
                'new_component_name': 'Detached / Unassigned Spare',
                'swap_date': fields.Date.today(),
                'technician_id': self.env.user.id,
                'reason': note_text,
            })
            # ALSO log in Asset Lifecycle & Custody Trail
            self.env['institutional.asset.custody.log'].sudo().create({
                'asset_id': source_asset.id,
                'event_type': 'component_removed',
                'previous_holder_id': source_asset.assigned_user_id.id if source_asset.assigned_user_id else False,
                'previous_department_id': source_asset.department_id.id if source_asset.department_id else False,
                'condition': source_asset.condition,
                'notes': note_text,
            })

    def action_transfer_component(self, target_asset_id, reason=False):
        """Transfer component directly from source asset to target asset"""
        for rec in self:
            source_asset = rec.asset_id
            target_asset = self.env['institutional.asset.item'].browse(target_asset_id)
            if not target_asset.exists():
                raise UserError(_("Target asset machine does not exist."))
            
            note_text = reason or f"Hardware Transfer: Transferred component '{rec.name}' from {source_asset.name if source_asset else 'Spare Stock'} to {target_asset.name}."
            rec.write({
                'asset_id': target_asset.id,
                'status': 'installed',
            })
            
            # Log inter-asset transfer event
            self.env['institutional.asset.component.history'].sudo().create({
                'asset_id': target_asset.id,
                'source_asset_id': source_asset.id if source_asset else False,
                'dest_asset_id': target_asset.id,
                'component_id': rec.id,
                'component_type': rec.component_type,
                'action_type': 'transferred',
                'old_component_name': f"From: {source_asset.name if source_asset else 'Unassigned Spare'}",
                'new_component_name': f"To: {target_asset.name} ({rec.name})",
                'swap_date': fields.Date.today(),
                'technician_id': self.env.user.id,
                'reason': note_text,
            })
            # ALSO log in Asset Lifecycle & Custody Trail
            self.env['institutional.asset.custody.log'].sudo().create({
                'asset_id': target_asset.id,
                'event_type': 'component_swapped',
                'new_holder_id': target_asset.assigned_user_id.id if target_asset.assigned_user_id else False,
                'new_department_id': target_asset.department_id.id if target_asset.department_id else False,
                'condition': target_asset.condition,
                'notes': note_text,
            })
