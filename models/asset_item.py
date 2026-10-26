# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class InstitutionalAssetItem(models.Model):
    _name = 'institutional.asset.item'
    _description = 'Institutional Asset Unit Tracking'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Asset Tag / Code', required=True, copy=False, default='New', tracking=True)
    product_id = fields.Many2one('product.product', string='Asset Product', required=True, tracking=True)
    category_id = fields.Many2one('product.category', related='product_id.categ_id', string='Category', store=True)
    serial_number = fields.Char(string='Serial Number / S/N', tracking=True)
    
    condition = fields.Selection([
        ('intact', 'Intact'),
        ('used', 'Used'),
        ('damaged', 'Damaged'),
    ], string='Item Condition', default='intact', required=True, tracking=True)

    status = fields.Selection([
        ('available', 'Available in Store'),
        ('issued', 'Issued / Unavailable'),
        ('maintenance', 'Under Maintenance'),
        ('scrapped', 'Scrapped'),
    ], string='Availability Status', default='available', required=True, tracking=True,
       help='While an asset is allocated or held by an employee, it is marked Issued / Unavailable.')

    department_id = fields.Many2one('hr.department', string='Allocated Department', tracking=True)
    assigned_user_id = fields.Many2one('res.users', string='Current Holder / Assigned User', tracking=True)
    location = fields.Char(string='Storage / Desk Location', default='Central Store Office', tracking=True)
    acquisition_date = fields.Date(string='Acquisition Date', default=fields.Date.context_today)
    
    def _default_currency_id(self):
        return self.env.ref('base.BDT', raise_if_not_found=False) or self.env.company.currency_id

    currency_id = fields.Many2one('res.currency', string='Currency', default=_default_currency_id)
    asset_value = fields.Monetary(string='Asset Purchase Cost', currency_field='currency_id', default=0.0)

    component_ids = fields.One2many('institutional.asset.component', 'asset_id', string='Hardware Components')
    swap_history_ids = fields.One2many('institutional.asset.component.history', 'asset_id', string='Component Replacement History')
    custody_log_ids = fields.One2many('institutional.asset.custody.log', 'asset_id', string='Lifecycle & Custody History')
    notes = fields.Text(string='Technical Specs & Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('institutional.asset.item') or 'AST/2026/0000'
        records = super(InstitutionalAssetItem, self).create(vals_list)
        for rec in records:
            # Create initial Acquisition custody log entry
            self.env['institutional.asset.custody.log'].sudo().create({
                'asset_id': rec.id,
                'event_type': 'acquisition',
                'new_holder_id': rec.assigned_user_id.id if rec.assigned_user_id else False,
                'new_department_id': rec.department_id.id if rec.department_id else False,
                'condition': rec.condition,
                'notes': f"Asset acquired on {rec.acquisition_date or fields.Date.today()}. Serial: {rec.serial_number or 'N/A'}",
            })
        return records

    def _update_department_quotas(self, dept_id=False, product_id=False):
        domain = []
        if dept_id:
            domain.append(('department_id', '=', dept_id))
        if product_id:
            domain.append(('product_id', '=', product_id))
        if domain:
            quotas = self.env['institutional.department.quota'].sudo().search(domain)
            for q in quotas:
                q._compute_quota_metrics()

    def write(self, vals):
        # Track manual custody / department updates for lifecycle audit log
        depts_to_update = set()
        for rec in self:
            old_user = rec.assigned_user_id
            old_dept = rec.department_id
            if old_dept:
                depts_to_update.add((old_dept.id, rec.product_id.id))
            
            res = super(InstitutionalAssetItem, rec).write(vals)
            new_user = rec.assigned_user_id
            new_dept = rec.department_id
            if new_dept:
                depts_to_update.add((new_dept.id, rec.product_id.id))
            
            if ('assigned_user_id' in vals and old_user != new_user) or ('department_id' in vals and old_dept != new_dept):
                if new_user != old_user:
                    event = 'transfer' if (old_user and new_user) else ('issue' if new_user else 'return')
                    note_msg = f"Custody updated from {old_user.name if old_user else 'Central Store'} to {new_user.name if new_user else 'Central Store'}."
                else:
                    event = 'transfer'
                    note_msg = f"Department allocation updated from {old_dept.name if old_dept else 'None'} to {new_dept.name if new_dept else 'None'}."
                
                self.env['institutional.asset.custody.log'].sudo().create({
                    'asset_id': rec.id,
                    'event_type': event,
                    'previous_holder_id': old_user.id if old_user else False,
                    'new_holder_id': new_user.id if new_user else False,
                    'previous_department_id': old_dept.id if old_dept else False,
                    'new_department_id': new_dept.id if new_dept else False,
                    'condition': rec.condition,
                    'notes': note_msg,
                })

        if any(f in vals for f in ('status', 'department_id', 'product_id')):
            for d_id, p_id in depts_to_update:
                self._update_department_quotas(d_id, p_id)
        return True

    def action_mark_issued(self, user_id=False, department_id=False, location=False):
        """Mark asset as issued / unavailable when picked up"""
        for rec in self:
            if rec.status == 'issued':
                raise UserError(_("Asset '%s' is already issued to %s and cannot be re-issued until returned.") % (rec.name, rec.assigned_user_id.name or 'someone'))
            old_u = rec.assigned_user_id
            old_d = rec.department_id
            rec.write({
                'status': 'issued',
                'assigned_user_id': user_id or rec.assigned_user_id.id,
                'department_id': department_id or rec.department_id.id,
                'location': location or 'Issued to User Desk',
            })
            rec.message_post(body=_("Asset issued to %s at %s") % (rec.assigned_user_id.name or 'User', rec.location))
            rec._update_department_quotas(rec.department_id.id, rec.product_id.id)
            
            self.env['institutional.asset.custody.log'].sudo().create({
                'asset_id': rec.id,
                'event_type': 'issue',
                'previous_holder_id': old_u.id if old_u else False,
                'new_holder_id': rec.assigned_user_id.id,
                'previous_department_id': old_d.id if old_d else False,
                'new_department_id': rec.department_id.id if rec.department_id else False,
                'condition': rec.condition,
                'notes': f"Asset checked out to {rec.assigned_user_id.name} in {rec.department_id.name if rec.department_id else 'Executive/Independent Office'}.",
            })

    def action_mark_returned(self, condition=False):
        """Mark asset returned to store office -> available with condition update and return stock move"""
        for rec in self:
            prev_user = rec.assigned_user_id
            prev_dept = rec.department_id
            vals = {
                'status': 'available',
                'assigned_user_id': False,
                'department_id': False,
                'location': 'Central Store Office',
            }
            if condition:
                vals['condition'] = condition
            rec.write(vals)
            if prev_dept:
                self._update_department_quotas(prev_dept.id, rec.product_id.id)
            rec.message_post(body=_("Asset returned to Central Store Office. Condition: %s") % (condition or rec.condition))
            
            self.env['institutional.asset.custody.log'].sudo().create({
                'asset_id': rec.id,
                'event_type': 'return',
                'previous_holder_id': prev_user.id if prev_user else False,
                'new_holder_id': False,
                'previous_department_id': prev_dept.id if prev_dept else False,
                'new_department_id': False,
                'condition': condition or rec.condition,
                'notes': f"Asset returned to Central Store by {prev_user.name if prev_user else 'Custodian'}. Checked in as available.",
            })
            
            # Create native stock return move into Central Store (WH/Stock)
            self._create_return_stock_picking(rec, prev_user)

    def _create_return_stock_picking(self, asset, prev_user=False):
        """Create native stock return move from Customer/Department back to Central Store"""
        try:
            picking_type = self.env['stock.picking.type'].sudo().search([('code', '=', 'incoming')], limit=1)
            if not picking_type:
                picking_type = self.env['stock.picking.type'].sudo().search([], limit=1)

            src_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
            dest_location = picking_type.default_location_dest_id or self.env.ref('stock.stock_location_stock', raise_if_not_found=False)

            if picking_type and src_location and dest_location and asset.product_id.is_storable:
                partner_id = prev_user.partner_id.id if (prev_user and prev_user.partner_id) else False
                picking = self.env['stock.picking'].sudo().create({
                    'picking_type_id': picking_type.id,
                    'location_id': src_location.id,
                    'location_dest_id': dest_location.id,
                    'origin': f"Return of {asset.name}",
                    'partner_id': partner_id,
                    'move_ids': [(0, 0, {
                        'description_picking': f"Return: {asset.name}",
                        'product_id': asset.product_id.id,
                        'product_uom_qty': 1.0,
                        'product_uom': asset.product_id.uom_id.id,
                        'location_id': src_location.id,
                        'location_dest_id': dest_location.id,
                    })],
                })
                picking.action_confirm()
                picking.action_assign()
                for m in picking.move_ids:
                    m.quantity = 1.0
                    if m.product_id.tracking in ('serial', 'lot') and asset.serial_number:
                        sn_str = asset.serial_number
                        lot = self.env['stock.lot'].sudo().search([('product_id', '=', m.product_id.id), ('name', '=', sn_str)], limit=1)
                        if not lot:
                            lot = self.env['stock.lot'].sudo().create({'product_id': m.product_id.id, 'name': sn_str})
                        for ml in m.move_line_ids:
                            ml.lot_id = lot.id
                picking.button_validate()
        except Exception:
            pass
