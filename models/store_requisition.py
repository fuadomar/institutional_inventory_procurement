# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class InstitutionalStoreRequisition(models.Model):
    _name = 'institutional.store.requisition'
    _description = 'Institutional Supply Store Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'transaction_date desc, id desc'

    def _default_department_id(self):
        user = self.env.user
        if user.employee_id and user.employee_id.department_id:
            return user.employee_id.department_id.id
        emp = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        if emp and emp.department_id:
            return emp.department_id.id
        return False

    name = fields.Char(string='Requisition Ref', required=True, copy=False, default='New', tracking=True)
    requested_by_id = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, required=True, tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', default=_default_department_id, required=False, tracking=True)

    transaction_date = fields.Date(string='Requisition / Transaction Date', default=fields.Date.context_today, required=True, tracking=True,
                                    help='Back-dated transaction date permitted. Original system creation time is logged separately.')
    actual_create_date = fields.Datetime(string='System Creation Time', default=fields.Datetime.now, readonly=True)
    is_backdated = fields.Boolean(string='Is Back-dated Entry', compute='_compute_is_backdated', store=True)

    # Annual Requisition & Combined Master Features
    demand_type = fields.Selection([
        ('annual_baseline', 'Annual Baseline Requisition'),
        ('dept_supplementary', 'Department Supplementary Demand'),
        ('individual_personnel', 'Time-by-Time Personnel Requisition'),
    ], string='Demand Type', default='individual_personnel', required=True, tracking=True,
       help='Annual Baseline and Dept Supplementary requisitions automatically establish and aggregate department quotas upon Registrar approval.')
    is_annual_requisition = fields.Boolean(string='Annual Beginning-of-Year Requisition', default=False, tracking=True,
                                          help='Flag for department annual baseline demand submitted at starting of fiscal year.')
    is_combined_master = fields.Boolean(string='Master Combined Requisition', default=False, tracking=True,
                                       help='Flag for aggregated multi-department annual master requisition for central tender.')
    combined_source_requisition_ids = fields.Many2many('institutional.store.requisition', 'rel_combined_req_sources',
                                                        'master_id', 'source_id', string='Combined Source Department Requisitions', copy=False)
    combined_count = fields.Integer(string='Combined Requisitions Count', compute='_compute_combined_count')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted to Dept Head'),
        ('dept_approved', 'Dept Head Approved'),
        ('registrar_approved', 'Registrar Approved'),
        ('in_procurement', 'In Procurement'),
        ('ready_for_issue', 'Ready for Store Pickup'),
        ('done', 'Issued / Fulfilled'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True, tracking=True)

    line_ids = fields.One2many('institutional.store.requisition.line', 'requisition_id', string='Requisition Items')
    audit_ids = fields.One2many('institutional.requisition.audit', 'requisition_id', string='Audit Trail History')

    def _default_currency_id(self):
        return self.env.ref('base.BDT', raise_if_not_found=False) or self.env.company.currency_id

    currency_id = fields.Many2one('res.currency', string='Currency', default=_default_currency_id)
    total_estimated_cost = fields.Monetary(string='Total Estimated Cost', currency_field='currency_id', compute='_compute_total_cost', store=True)

    dept_head_approver_id = fields.Many2one('res.users', string='Dept Head Approver', tracking=True)
    registrar_approver_id = fields.Many2one('res.users', string='Registrar Approver', tracking=True)
    store_incharge_id = fields.Many2one('res.users', string='Store Incharge Handler', tracking=True)
    
    picking_id = fields.Many2one('stock.picking', string='Native Odoo Stock Transfer', readonly=True, copy=False)
    picking_count = fields.Integer(string='Transfers Count', compute='_compute_picking_count')

    # Non-Negative Stock Warning Summary
    has_stock_shortfall = fields.Boolean(string='Has Stock Shortfall', compute='_compute_stock_warnings', search='_search_has_stock_shortfall')
    stock_warning_summary = fields.Text(string='Central Store Stock Status Note', compute='_compute_stock_warnings')

    notes = fields.Text(string='Requisition Purpose / Justification')

    @api.depends('combined_source_requisition_ids')
    def _compute_combined_count(self):
        for rec in self:
            rec.combined_count = len(rec.combined_source_requisition_ids)

    @api.depends('picking_id')
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = 1 if rec.picking_id else 0

    @api.depends('transaction_date', 'create_date')
    def _compute_is_backdated(self):
        for rec in self:
            if rec.transaction_date and rec.create_date:
                rec.is_backdated = rec.transaction_date < rec.create_date.date()
            else:
                rec.is_backdated = False

    @api.depends('line_ids.subtotal_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_estimated_cost = sum(line.subtotal_cost for line in rec.line_ids)

    @api.depends('line_ids.has_stock_warning', 'line_ids.stock_warning_note')
    def _compute_stock_warnings(self):
        for rec in self:
            shortfall_lines = rec.line_ids.filtered(lambda l: l.has_stock_warning)
            if shortfall_lines:
                rec.has_stock_shortfall = True
                notes_list = [f"• {l.product_id.display_name}: Requested {l.approved_qty} units | Store Available: {l.stock_available_qty} units (Shortfall: {l.stock_shortfall_qty} units)" for l in shortfall_lines]
                rec.stock_warning_summary = "⚠️ Central Store Stock Shortfall Notice:\n" + "\n".join(notes_list) + "\n\n💡 Tip: Use 'Create Purchase Order' to procure shortfall quantities directly from Central Procurement."
            else:
                rec.has_stock_shortfall = False
                rec.stock_warning_summary = "✅ Central Store Stock Available for all line items."

    def _search_has_stock_shortfall(self, operator, value):
        shortfall_lines = self.env['institutional.store.requisition.line'].search([('has_stock_warning', '=', True)])
        req_ids = shortfall_lines.mapped('requisition_id').ids
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', req_ids)]
        else:
            return [('id', 'not in', req_ids)]

    @api.onchange('department_id', 'requested_by_id')
    def _onchange_department_and_user(self):
        if self.requested_by_id and self.requested_by_id.employee_id and self.requested_by_id.employee_id.department_id:
            if not self.department_id:
                self.department_id = self.requested_by_id.employee_id.department_id.id

        if self.department_id:
            if self.department_id.manager_id and self.department_id.manager_id.user_id:
                self.dept_head_approver_id = self.department_id.manager_id.user_id.id
            else:
                dept_head_group = self.env.ref('institutional_inventory_procurement.group_institutional_dept_head', raise_if_not_found=False)
                if dept_head_group and dept_head_group.user_ids:
                    dept_user = dept_head_group.user_ids.filtered(lambda u: u.employee_id.department_id == self.department_id) or dept_head_group.user_ids
                    self.dept_head_approver_id = dept_user[0].id

            registrar_group = self.env.ref('institutional_inventory_procurement.group_institutional_registrar', raise_if_not_found=False)
            if registrar_group and registrar_group.user_ids:
                self.registrar_approver_id = registrar_group.user_ids[0].id

            store_group = self.env.ref('institutional_inventory_procurement.group_institutional_store_incharge', raise_if_not_found=False)
            if store_group and store_group.user_ids:
                self.store_incharge_id = store_group.user_ids[0].id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                prefix = 'REQ/COMBINED/2026/' if vals.get('is_combined_master') else 'REQ/2026/'
                vals['name'] = self.env['ir.sequence'].next_by_code('institutional.store.requisition') or f'{prefix}0000'
            
            dept_id = vals.get('department_id')
            if dept_id:
                dept = self.env['hr.department'].browse(dept_id)
                if not vals.get('dept_head_approver_id'):
                    if dept.manager_id and dept.manager_id.user_id:
                        vals['dept_head_approver_id'] = dept.manager_id.user_id.id
                    else:
                        dept_head_group = self.env.ref('institutional_inventory_procurement.group_institutional_dept_head', raise_if_not_found=False)
                        if dept_head_group and dept_head_group.user_ids:
                            dept_user = dept_head_group.user_ids.filtered(lambda u: u.employee_id.department_id.id == dept_id) or dept_head_group.user_ids
                            vals['dept_head_approver_id'] = dept_user[0].id

                if not vals.get('registrar_approver_id'):
                    registrar_group = self.env.ref('institutional_inventory_procurement.group_institutional_registrar', raise_if_not_found=False)
                    if registrar_group and registrar_group.user_ids:
                        vals['registrar_approver_id'] = registrar_group.user_ids[0].id

                if not vals.get('store_incharge_id'):
                    store_group = self.env.ref('institutional_inventory_procurement.group_institutional_store_incharge', raise_if_not_found=False)
                    if store_group and store_group.user_ids:
                        vals['store_incharge_id'] = store_group.user_ids[0].id

        records = super(InstitutionalStoreRequisition, self).create(vals_list)
        for rec in records:
            if rec.is_backdated:
                self.env['institutional.requisition.audit'].sudo().create({
                    'requisition_id': rec.id,
                    'modified_by_id': self.env.user.id,
                    'audit_type': 'backdate',
                    'reason': f'Requisition created with back-dated transaction date {rec.transaction_date} (System entry: {rec.actual_create_date})',
                })
        return records

    def write(self, vals):
        if 'line_ids' in vals:
            for rec in self:
                old_lines = {line.id: (line.product_id.display_name, line.requested_qty, line.approved_qty) for line in rec.line_ids}
                res = super(InstitutionalStoreRequisition, rec).write(vals)
                new_lines = {line.id: (line.product_id.display_name, line.requested_qty, line.approved_qty) for line in rec.line_ids}

                log_msgs = []
                for lid, data in new_lines.items():
                    if lid not in old_lines:
                        log_msgs.append(_("• Added item %s (Requested Qty: %s)") % (data[0], data[1]))
                for lid, data in old_lines.items():
                    if lid not in new_lines:
                        log_msgs.append(_("• Removed item %s") % data[0])
                for lid, data in new_lines.items():
                    if lid in old_lines:
                        old_p, old_req, old_app = old_lines[lid]
                        new_p, new_req, new_app = data
                        changes = []
                        if old_req != new_req:
                            changes.append(_("Requested Qty (%s → %s)") % (old_req, new_req))
                        if old_app != new_app:
                            changes.append(_("Approved Qty (%s → %s)") % (old_app, new_app))
                        if changes:
                            log_msgs.append(_("• Updated %s: %s") % (new_p, ", ".join(changes)))
                if log_msgs:
                    rec.message_post(body=_("Requisition Line Items Log Trail:\n") + "\n".join(log_msgs))
            return True
        return super(InstitutionalStoreRequisition, self).write(vals)

    def action_combine_annual_requisitions(self):
        """ Combine selected department annual requisitions into a Master Combined Annual Requisition """
        selected_reqs = self.filtered(lambda r: not r.is_combined_master)
        if not selected_reqs:
            raise UserError(_("Please select one or more department requisitions to combine."))
        
        # Aggregate demand lines per product
        product_demand_map = {}
        dept_breakdown_map = {}
        for req in selected_reqs:
            dept_name = req.department_id.name if req.department_id else 'General'
            for line in req.line_ids:
                pid = line.product_id.id
                qty = line.requested_qty
                if pid not in product_demand_map:
                    product_demand_map[pid] = {
                        'product_id': pid,
                        'qty': 0.0,
                        'unit_price': line.unit_price,
                        'condition': line.item_condition,
                    }
                    dept_breakdown_map[pid] = []
                product_demand_map[pid]['qty'] += qty
                dept_breakdown_map[pid].append(f"{dept_name}: {qty} units (Ref: {req.name})")

        master_lines = []
        for pid, data in product_demand_map.items():
            breakdown_text = "; ".join(dept_breakdown_map[pid])
            master_lines.append((0, 0, {
                'product_id': pid,
                'requested_qty': data['qty'],
                'approved_qty': data['qty'],
                'unit_price': data['unit_price'],
                'item_condition': data['condition'],
                'edit_reason': f"Combined Demand Breakdown: {breakdown_text}",
            }))

        combined_name = f"REQ/COMBINED/2026/{self.env['ir.sequence'].next_by_code('institutional.store.requisition') or '001'}"
        master_req = self.create({
            'name': combined_name,
            'is_annual_requisition': True,
            'is_combined_master': True,
            'requested_by_id': self.env.user.id,
            'combined_source_requisition_ids': [(6, 0, selected_reqs.ids)],
            'state': 'draft',
            'notes': f"Master Combined Annual Requisition for Fiscal Year 2026. Consolidated demand from {len(selected_reqs)} departments: " + ", ".join(selected_reqs.mapped(lambda r: r.department_id.name or r.name)),
            'line_ids': master_lines,
        })

        # Log combined status on source requisitions
        for source_req in selected_reqs:
            source_req.message_post(body=_("Included in Master Combined Annual Requisition %s.") % master_req.name)

        return {
            'name': _('Master Combined Annual Requisition'),
            'type': 'ir.actions.act_window',
            'res_model': 'institutional.store.requisition',
            'res_id': master_req.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Please add at least one item line before submitting requisition."))
            rec.state = 'submitted'
            rec.message_post(body=_("Requisition submitted by %s for Department Head approval.") % self.env.user.name)
            template = self.env.ref('institutional_inventory_procurement.mail_template_requisition_submitted', raise_if_not_found=False)
            if template:
                template.send_mail(rec.id, force_send=False)

    def action_dept_approve(self):
        for rec in self:
            rec.state = 'dept_approved'
            rec.dept_head_approver_id = self.env.user.id
            rec.message_post(body=_("Requisition approved by Department Head (%s). Awaiting Registrar approval.") % self.env.user.name)
            self.env['institutional.requisition.audit'].sudo().create({
                'requisition_id': rec.id,
                'modified_by_id': self.env.user.id,
                'audit_type': 'approval',
                'reason': f'Department Head approval by {self.env.user.name}',
            })
            template = self.env.ref('institutional_inventory_procurement.mail_template_requisition_dept_approved', raise_if_not_found=False)
            if template:
                template.send_mail(rec.id, force_send=False)

    def action_registrar_approve(self):
        for rec in self:
            rec.state = 'registrar_approved'
            rec.registrar_approver_id = self.env.user.id
            rec.message_post(body=_("Requisition approved by Registrar (%s). Sent to Store Incharge for fulfillment.") % self.env.user.name)
            self.env['institutional.requisition.audit'].sudo().create({
                'requisition_id': rec.id,
                'modified_by_id': self.env.user.id,
                'audit_type': 'approval',
                'reason': f'Registrar mandatory approval by {self.env.user.name}',
            })

            # Automated Demand-Derived Department Quota Auto-Creation & Aggregation
            if rec.demand_type in ('annual_baseline', 'dept_supplementary') or rec.is_annual_requisition:
                if rec.department_id:
                    fiscal_yr = str(rec.transaction_date.year) if rec.transaction_date else str(fields.Date.today().year)
                    for line in rec.line_ids:
                        qty = line.approved_qty or line.requested_qty or 0.0
                        if qty > 0 and line.product_id:
                            quota = self.env['institutional.department.quota'].sudo().search([
                                ('department_id', '=', rec.department_id.id),
                                ('product_id', '=', line.product_id.id),
                                ('fiscal_year', '=', fiscal_yr)
                            ], limit=1)
                            if not quota:
                                quota = self.env['institutional.department.quota'].sudo().create({
                                    'department_id': rec.department_id.id,
                                    'product_id': line.product_id.id,
                                    'fiscal_year': fiscal_yr,
                                    'allocated_qty': qty,
                                    'notes': f"Auto-established from Demand List {rec.name}",
                                })
                            else:
                                quota.sudo().write({
                                    'allocated_qty': quota.allocated_qty + qty,
                                })
                            rec.message_post(body=_("⚡ Demand Quota Auto-Updated for %s: Added %s units to %s allocation (Fiscal Year %s). Cumulative Total Allocation: %s units.") % (
                                line.product_id.display_name, qty, rec.department_id.name, fiscal_yr, quota.allocated_qty
                            ))

    def _update_department_quotas(self):
        for rec in self:
            if rec.department_id:
                prods = rec.line_ids.mapped('product_id')
                if prods:
                    quotas = self.env['institutional.department.quota'].sudo().search([
                        ('department_id', '=', rec.department_id.id),
                        ('product_id', 'in', prods.ids)
                    ])
                    for q in quotas:
                        q._compute_quota_metrics()

    def action_mark_ready_issue(self):
        for rec in self:
            rec.state = 'ready_for_issue'
            rec.store_incharge_id = self.env.user.id
            rec._update_department_quotas()
            rec.message_post(body=_("Requisition prepared by Store Incharge (%s). Ready for pickup at Central Store Office.") % self.env.user.name)
            template = self.env.ref('institutional_inventory_procurement.mail_template_requisition_ready', raise_if_not_found=False)
            if template:
                template.send_mail(rec.id, force_send=False)

    def action_issue_stock(self):
        """ Fulfill requisition: mark assets issued/unavailable, update stock lines, and create native Odoo Stock Picking """
        for rec in self:
            # Non-Negative Inventory Enforcement Guard
            insufficient_items = []
            for line in rec.line_ids:
                avail = line.product_id.qty_available if line.product_id else 0.0
                req = line.approved_qty or line.requested_qty or 0.0
                if req > avail:
                    shortfall = req - avail
                    insufficient_items.append(
                        f"• {line.product_id.display_name}: Available {avail} units, "
                        f"Attempting to Issue {req} units (Shortfall: {shortfall} units)"
                    )
            if insufficient_items:
                raise UserError(_(
                    "⛔ Non-Negative Inventory Block:\n"
                    "Cannot issue stock because doing so would cause Central Store inventory to become negative!\n\n"
                    "Shortfall Summary:\n%s\n\n"
                    "💡 Solution: Click 'Send to Procurement' on the line item to create a Purchase Order, "
                    "or reduce the approved quantity before issuing."
                ) % ("\n".join(insufficient_items)))

            rec.state = 'done'
            rec.store_incharge_id = self.env.user.id
            for line in rec.line_ids:
                line.issued_qty = line.approved_qty
                # If asset items assigned, flip asset availability status to 'issued'
                for asset in line.asset_item_ids:
                    asset.action_mark_issued(
                        user_id=rec.requested_by_id.id,
                        department_id=rec.department_id.id,
                        location=f"Issued to {rec.department_id.name if rec.department_id else 'Department'}"
                    )
            
            # Integrate with Native Odoo Stock Transfer (stock.picking)
            self._create_native_stock_picking()
            rec._update_department_quotas()
            rec.message_post(body=_("Items successfully issued and picked up at Central Store Office by %s. Native stock transfer created.") % rec.requested_by_id.name)

    def _create_native_stock_picking(self):
        """ Create standard Odoo stock.picking record to update native inventory moves """
        picking_type = self.env['stock.picking.type'].sudo().search([('code', '=', 'outgoing')], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].sudo().search([('code', '=', 'internal')], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].sudo().search([], limit=1)

        src_location = picking_type.default_location_src_id or self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        dest_location = picking_type.default_location_dest_id or self.env.ref('stock.stock_location_customers', raise_if_not_found=False)

        if picking_type and src_location and dest_location:
            move_lines = []
            for line in self.line_ids:
                if line.approved_qty > 0:
                    move_lines.append((0, 0, {
                        'description_picking': line.product_id.display_name,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.approved_qty,
                        'product_uom': line.product_id.uom_id.id,
                        'location_id': src_location.id,
                        'location_dest_id': dest_location.id,
                    }))
            if move_lines:
                picking = self.env['stock.picking'].sudo().create({
                    'picking_type_id': picking_type.id,
                    'location_id': src_location.id,
                    'location_dest_id': dest_location.id,
                    'origin': self.name,
                    'partner_id': self.requested_by_id.partner_id.id if self.requested_by_id.partner_id else False,
                    'move_ids': move_lines,
                })
                self.picking_id = picking.id
                
                try:
                    picking.action_confirm()
                    picking.action_assign()
                    for m in picking.move_ids:
                        m.quantity = m.product_uom_qty
                        if m.product_id.tracking in ('serial', 'lot'):
                            req_line = self.line_ids.filtered(lambda l: l.product_id == m.product_id)
                            assigned_assets = req_line.asset_item_ids if req_line else self.env['institutional.asset.item']
                            for idx, ml in enumerate(m.move_line_ids):
                                lot = False
                                if idx < len(assigned_assets) and assigned_assets[idx].serial_number:
                                    sn_str = assigned_assets[idx].serial_number
                                    lot = self.env['stock.lot'].sudo().search([('product_id', '=', m.product_id.id), ('name', '=', sn_str)], limit=1)
                                    if not lot:
                                        lot = self.env['stock.lot'].sudo().create({'product_id': m.product_id.id, 'name': sn_str})
                                if not lot:
                                    sn_str = f"SN-{m.product_id.default_code or 'AST'}-{idx+1:03d}"
                                    lot = self.env['stock.lot'].sudo().search([('product_id', '=', m.product_id.id), ('name', '=', sn_str)], limit=1)
                                    if not lot:
                                        lot = self.env['stock.lot'].sudo().create({'product_id': m.product_id.id, 'name': sn_str})
                                ml.lot_id = lot.id
                    picking.button_validate()
                except Exception:
                    pass

    def action_view_picking(self):
        """ Open native Odoo stock transfer """
        self.ensure_one()
        return {
            'name': _('Native Odoo Stock Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'
            rec._update_department_quotas()
            rec.message_post(body=_("Requisition cancelled by %s.") % self.env.user.name)

    def action_reject(self):
        for rec in self:
            rec.state = 'rejected'
            rec._update_department_quotas()
            rec.message_post(body=_("Requisition rejected by %s.") % self.env.user.name)
            self.env['institutional.requisition.audit'].sudo().create({
                'requisition_id': rec.id,
                'modified_by_id': self.env.user.id,
                'audit_type': 'approval',
                'reason': f'Requisition rejected by {self.env.user.name}',
            })

    def action_create_purchase_order(self):
        """Create a draft Purchase Order from approved requisition lines using core purchase module"""
        for rec in self:
            order_lines = []
            for line in rec.line_ids:
                qty_to_buy = line.stock_shortfall_qty if line.stock_shortfall_qty > 0 else line.approved_qty
                if qty_to_buy > 0:
                    order_lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'product_qty': qty_to_buy,
                        'price_unit': line.unit_price,
                    }))
            
            if not order_lines:
                raise UserError(_("No items to create a Purchase Order."))
            
            po = self.env['purchase.order'].create({
                'partner_id': self.env.ref('base.main_partner', raise_if_not_found=False).id or self.env['res.partner'].search([], limit=1).id,
                'origin': rec.name,
                'order_line': order_lines,
            })
            rec.state = 'in_procurement'
            rec.message_post(body=_("Draft Purchase Order %s created from this requisition.") % po.name)
            return {
                'name': _('Purchase Order'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': po.id,
                'view_mode': 'form',
                'target': 'current',
            }


class InstitutionalStoreRequisitionLine(models.Model):
    _name = 'institutional.store.requisition.line'
    _description = 'Store Requisition Line Item'

    requisition_id = fields.Many2one('institutional.store.requisition', string='Requisition Reference', required=True, ondelete='cascade')
    requested_by_id = fields.Many2one('res.users', related='requisition_id.requested_by_id', string='Person / Requester', store=True)
    department_id = fields.Many2one('hr.department', related='requisition_id.department_id', string='Department', store=True)
    state = fields.Selection(related='requisition_id.state', string='Requisition Status', store=True)
    product_id = fields.Many2one('product.product', string='Item Product', required=True)
    institutional_item_type = fields.Selection(related='product_id.institutional_item_type', string='Type', store=True)
    
    requested_qty = fields.Float(string='Requested Qty', default=1.0, required=True)
    approved_qty = fields.Float(string='Approved / Issued Qty', default=1.0, required=True,
                                help='Store Incharge can edit approved quantity. Modifications are automatically written to the Registrar audit trail.')
    issued_qty = fields.Float(string='Fulfilled Qty', default=0.0)

    # Stock Availability & Shortfall Visual Warning Notes
    stock_available_qty = fields.Float(string='Central Store Stock', compute='_compute_stock_and_quota_warnings', store=True)
    stock_shortfall_qty = fields.Float(string='Shortfall Qty', compute='_compute_stock_and_quota_warnings', store=True)
    has_stock_warning = fields.Boolean(string='Stock Shortfall Warning', compute='_compute_stock_and_quota_warnings', store=True)
    stock_warning_note = fields.Char(string='Stock Warning Note', compute='_compute_stock_and_quota_warnings', store=True)

    # Department Quota Warnings
    dept_quota_remaining = fields.Float(string='Dept Remaining Quota', compute='_compute_stock_and_quota_warnings', store=True)
    dept_quota_warning = fields.Char(string='Quota Warning Note', compute='_compute_stock_and_quota_warnings', store=True)

    item_condition = fields.Selection([
        ('intact', 'Intact'),
        ('used', 'Used'),
        ('damaged', 'Damaged'),
    ], string='Condition', default='intact', required=True)

    currency_id = fields.Many2one('res.currency', related='requisition_id.currency_id', store=True)
    unit_price = fields.Monetary(string='Unit Cost', currency_field='currency_id', default=0.0)
    subtotal_cost = fields.Monetary(string='Subtotal Cost', currency_field='currency_id', compute='_compute_subtotal', store=True)

    asset_item_ids = fields.Many2many('institutional.asset.item', 'rel_req_line_asset', 'line_id', 'asset_id', string='Allocated Asset Units')
    qty_modified = fields.Boolean(string='Quantity Modified', compute='_compute_qty_modified', store=True)
    edit_reason = fields.Text(string='Quantity Adjustment Reason / Breakdown')

    @api.depends('product_id', 'requested_qty', 'approved_qty', 'department_id', 'product_id.qty_available')
    def _compute_stock_and_quota_warnings(self):
        for line in self:
            avail = line.product_id.qty_available if line.product_id else 0.0
            req = line.approved_qty or line.requested_qty or 0.0
            shortfall = max(0.0, req - avail)
            
            line.stock_available_qty = avail
            line.stock_shortfall_qty = shortfall
            line.has_stock_warning = (shortfall > 0)

            if shortfall > 0:
                line.stock_warning_note = f"⚠️ Insufficient Central Store Stock: Available {avail} units, Requested {req} units. Shortfall: {shortfall} units."
            else:
                line.stock_warning_note = f"✅ Stock Available (Store: {avail} units)"

            # Quota metrics
            quota_rem = 0.0
            quota_note = "✅ Within Department Annual Quota"
            if line.department_id and line.product_id:
                quota = self.env['institutional.department.quota'].search([
                    ('department_id', '=', line.department_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('fiscal_year', '=', '2026')
                ], limit=1)
                if quota:
                    quota_rem = quota.remaining_qty
                    if req > quota_rem:
                        quota_note = f"⚠️ Exceeds Annual Quota! Requested {req} exceeds remaining quota balance of {quota_rem} units (Allocated: {quota.allocated_qty})."
                    else:
                        quota_note = f"✅ Quota OK (Remaining: {quota_rem} / Allocated: {quota.allocated_qty})"

            line.dept_quota_remaining = quota_rem
            line.dept_quota_warning = quota_note

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.standard_price or self.product_id.list_price or 10.0
            self.item_condition = self.product_id.item_condition or 'intact'

    @api.onchange('requested_qty')
    def _onchange_requested_qty(self):
        if not self.requisition_id or self.requisition_id.state in (False, 'draft'):
            self.approved_qty = self.requested_qty

    @api.depends('requested_qty', 'approved_qty', 'requisition_id.state')
    def _compute_qty_modified(self):
        for line in self:
            if not line.requisition_id or line.requisition_id.state in (False, 'draft'):
                line.qty_modified = False
            else:
                line.qty_modified = (line.requested_qty != line.approved_qty)

    @api.depends('approved_qty', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal_cost = line.approved_qty * line.unit_price

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'requested_qty' in vals and 'approved_qty' not in vals:
                vals['approved_qty'] = vals['requested_qty']
        return super(InstitutionalStoreRequisitionLine, self).create(vals_list)

    def write(self, vals):
        if 'requested_qty' in vals and 'approved_qty' not in vals:
            for line in self:
                if not line.requisition_id or line.requisition_id.state in (False, 'draft'):
                    vals['approved_qty'] = vals['requested_qty']
        for line in self:
            if 'approved_qty' in vals and vals['approved_qty'] != line.approved_qty:
                if line.requisition_id and line.requisition_id.state not in (False, 'draft'):
                    old_q = line.approved_qty
                    new_q = vals['approved_qty']
                    reason_txt = vals.get('edit_reason') or line.edit_reason or 'Store Incharge stock allocation adjustment.'
                    self.env['institutional.requisition.audit'].sudo().create({
                        'requisition_id': line.requisition_id.id,
                        'line_id': line.id,
                        'product_id': line.product_id.id,
                        'modified_by_id': self.env.user.id,
                        'audit_type': 'qty_change',
                        'original_qty': old_q,
                        'new_qty': new_q,
                        'reason': reason_txt,
                        'details': f"Quantity modified for {line.product_id.display_name}: from {old_q} to {new_q}. Adjuster: {self.env.user.name}",
                    })
        res = super(InstitutionalStoreRequisitionLine, self).write(vals)
        if any(f in vals for f in ('approved_qty', 'issued_qty', 'department_id', 'product_id')):
            for line in self:
                if line.department_id and line.product_id:
                    quotas = self.env['institutional.department.quota'].sudo().search([
                        ('department_id', '=', line.department_id.id),
                        ('product_id', '=', line.product_id.id)
                    ])
                    for q in quotas:
                        q._compute_quota_metrics()
        return res

    def unlink(self):
        depts_and_prods = [(l.department_id.id, l.product_id.id) for l in self if l.department_id and l.product_id]
        res = super(InstitutionalStoreRequisitionLine, self).unlink()
        for dept_id, prod_id in depts_and_prods:
            quotas = self.env['institutional.department.quota'].sudo().search([
                ('department_id', '=', dept_id),
                ('product_id', '=', prod_id)
            ])
            for q in quotas:
                q._compute_quota_metrics()
        return res

    def action_send_to_procurement(self):
        """ 1-Click Action on Requisition Line to send shortfall item to Purchase / Procurement """
        self.ensure_one()
        qty = self.stock_shortfall_qty if self.stock_shortfall_qty > 0 else self.approved_qty
        po = self.env['purchase.order'].create({
            'partner_id': self.env.ref('base.main_partner', raise_if_not_found=False).id or self.env['res.partner'].search([], limit=1).id,
            'origin': f"Line Demand from {self.requisition_id.name}",
            'order_line': [(0, 0, {
                'product_id': self.product_id.id,
                'product_qty': qty,
                'price_unit': self.unit_price,
            })],
        })
        self.requisition_id.message_post(body=_("1-Click Procurement Created: Purchase Order %s generated for %s (%s units).") % (po.name, self.product_id.display_name, qty))
        return {
            'name': _('Procurement Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }
