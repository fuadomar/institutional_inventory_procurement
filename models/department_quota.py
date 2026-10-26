# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class InstitutionalDepartmentQuota(models.Model):
    _name = 'institutional.department.quota'
    _description = 'Departmental Annual Quota Allocation'
    _order = 'fiscal_year desc, department_id, product_id'

    name = fields.Char(string='Quota Reference', compute='_compute_name', store=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True, index=True)
    product_id = fields.Many2one('product.product', string='Product Item', required=True, index=True)
    category_id = fields.Many2one('product.category', related='product_id.categ_id', string='Product Category', store=True)
    fiscal_year = fields.Char(string='Fiscal Year', default='2026', required=True, index=True)

    allocated_qty = fields.Float(string='Annual Allocated Quota', default=100.0, required=True,
                                 help='Beginning-of-year threshold allocation for this department and product.')
    consumed_qty = fields.Float(string='Consumed Quota (Supplies)', compute='_compute_quota_metrics', store=True,
                                help='Total quantity of consumable items fulfilled and consumed by this department.')
    held_qty = fields.Float(string='Held Assets (In Custody)', compute='_compute_quota_metrics', store=True,
                            help='Total count of active serialized assets currently held in custody by department personnel.')
    total_used_qty = fields.Float(string='Total Utilized Quota', compute='_compute_quota_metrics', store=True)
    remaining_qty = fields.Float(string='Remaining Quota Balance', compute='_compute_quota_metrics', store=True)
    usage_pct = fields.Float(string='Quota Usage %', compute='_compute_quota_metrics', store=True)

    status = fields.Selection([
        ('ok', 'Within Quota'),
        ('warning', 'Near Threshold (≥80%)'),
        ('exceeded', 'Quota Exceeded'),
    ], string='Quota Status', compute='_compute_quota_metrics', store=True)

    def _default_currency_id(self):
        return self.env.ref('base.BDT', raise_if_not_found=False) or self.env.company.currency_id

    currency_id = fields.Many2one('res.currency', string='Currency', default=_default_currency_id)
    unit_cost = fields.Float(related='product_id.standard_price', string='Unit Cost', store=True)
    allocated_value = fields.Monetary(string='Allocated Budget Value', currency_field='currency_id', compute='_compute_quota_metrics', store=True)
    consumed_value = fields.Monetary(string='Consumed Value', currency_field='currency_id', compute='_compute_quota_metrics', store=True)

    notes = fields.Text(string='Quota Notes & Approval Ref')

    @api.depends('department_id', 'product_id', 'fiscal_year')
    def _compute_name(self):
        for rec in self:
            dept = rec.department_id.name if rec.department_id else 'General'
            prod = rec.product_id.display_name if rec.product_id else 'Item'
            rec.name = f"{dept} - {prod} ({rec.fiscal_year or '2026'})"

    @api.depends('allocated_qty', 'department_id', 'product_id', 'fiscal_year')
    def _compute_quota_metrics(self):
        for rec in self:
            consumed = 0.0
            held = 0.0
            if rec.department_id and rec.product_id:
                if rec.product_id.institutional_item_type == 'consumable':
                    # Only individual personnel requisitions consume quota (NOT annual baseline or supplementary demand lists)
                    lines = self.env['institutional.store.requisition.line'].search([
                        ('department_id', '=', rec.department_id.id),
                        ('product_id', '=', rec.product_id.id),
                        ('requisition_id.demand_type', '=', 'individual_personnel'),
                        ('requisition_id.is_annual_requisition', '=', False),
                        ('state', 'in', ('ready_for_issue', 'done'))
                    ])
                    consumed = sum(line.issued_qty if line.issued_qty > 0 else line.approved_qty for line in lines)
                else:
                    # Asset items: tracked as active serialized assets currently held in custody by department personnel
                    held_assets = self.env['institutional.asset.item'].search([
                        ('department_id', '=', rec.department_id.id),
                        ('product_id', '=', rec.product_id.id),
                        ('status', '=', 'issued')
                    ])
                    held = float(len(held_assets))

            rec.consumed_qty = consumed
            rec.held_qty = held
            total_used = consumed + held
            rec.total_used_qty = total_used

            rem = max(0.0, rec.allocated_qty - total_used)
            rec.remaining_qty = rem
            
            alloc = rec.allocated_qty if rec.allocated_qty > 0 else 1.0
            pct = min(100.0, max(0.0, (total_used / alloc) * 100.0))
            rec.usage_pct = pct

            if total_used > rec.allocated_qty:
                rec.status = 'exceeded'
            elif pct >= 80.0:
                rec.status = 'warning'
            else:
                rec.status = 'ok'

            cost = rec.unit_cost or 10.0
            rec.allocated_value = rec.allocated_qty * cost
            rec.consumed_value = total_used * cost

    def read(self, fields=None, load='_classic_read'):
        self._compute_quota_metrics()
        return super(InstitutionalDepartmentQuota, self).read(fields=fields, load=load)
