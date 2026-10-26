# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    institutional_item_type = fields.Selection([
        ('consumable', 'Consumable Item'),
        ('asset', 'Asset Item'),
    ], string='Institutional Item Type', default='consumable', required=True,
       help='Consumable items deplete upon issue. Asset items are unit-tracked and subject to availability rules.')

    item_condition = fields.Selection([
        ('intact', 'Intact'),
        ('used', 'Used'),
        ('damaged', 'Damaged'),
    ], string='Default Condition', default='intact', required=True,
       help='Physical condition of the item.')

    requisition_pending_qty = fields.Float(
        string='Pending Requisition Demand',
        compute='_compute_requisition_stock_metrics',
        help='Sum of approved quantities in active requisitions waiting for fulfillment.'
    )
    forecast_shortfall_qty = fields.Float(
        string='Forecast Stock Balance',
        compute='_compute_requisition_stock_metrics',
        help='On Hand Stock minus Pending Requisition Demand.'
    )
    qty_to_order = fields.Float(
        string='Qty Needed to Order',
        compute='_compute_requisition_stock_metrics',
        help='Quantity needed to purchase/order to satisfy all requisitions.'
    )
    is_shortfall = fields.Boolean(
        string='Has Shortfall / Need Order',
        compute='_compute_requisition_stock_metrics',
        search='_search_is_shortfall'
    )
    reorder_cost_subtotal = fields.Monetary(
        string='Est. Reorder Cost (BDT)',
        currency_field='currency_id',
        compute='_compute_requisition_stock_metrics',
        help='Estimated cost in Bangladeshi Taka to procure needed shortfall stock.'
    )

    # Product 360° Analytics Smart Fields
    held_asset_count = fields.Integer(
        string='Active Held Assets',
        compute='_compute_institutional_360_metrics',
        help='Count of serialized assets of this product currently held in custody by personnel.'
    )
    consumed_qty_total = fields.Float(
        string='Cumulative Consumed Supplies',
        compute='_compute_institutional_360_metrics',
        help='Total consumable units fulfilled and issued to university personnel to date.'
    )
    personnel_consumer_count = fields.Integer(
        string='Personnel Consumers',
        compute='_compute_institutional_360_metrics',
        help='Distinct number of teachers and officers holding or consuming this product.'
    )

    @api.depends('qty_available', 'virtual_available', 'standard_price', 'list_price')
    def _compute_requisition_stock_metrics(self):
        for tmpl in self:
            products = tmpl.product_variant_ids
            req_lines = self.env['institutional.store.requisition.line'].search([
                ('product_id', 'in', products.ids),
                ('state', 'in', ('submitted', 'dept_approved', 'registrar_approved', 'in_procurement', 'ready_for_issue'))
            ])
            pending_demand = sum(req_lines.mapped('approved_qty'))
            on_hand = tmpl.qty_available
            forecast = on_hand - pending_demand

            shortfall = max(0.0, pending_demand - on_hand)
            if forecast < 0 and abs(forecast) > shortfall:
                shortfall = abs(forecast)

            unit_cost = tmpl.standard_price or tmpl.list_price or 10.0

            tmpl.requisition_pending_qty = pending_demand
            tmpl.forecast_shortfall_qty = forecast
            tmpl.qty_to_order = shortfall
            tmpl.is_shortfall = (shortfall > 0 or forecast < 0)
            tmpl.reorder_cost_subtotal = shortfall * unit_cost

    def _search_is_shortfall(self, operator, value):
        all_templates = self.search([('institutional_item_type', '!=', False)])
        shortfall_ids = []
        for tmpl in all_templates:
            if tmpl.qty_to_order > 0 or tmpl.forecast_shortfall_qty < 0:
                shortfall_ids.append(tmpl.id)
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', shortfall_ids)]
        else:
            return [('id', 'not in', shortfall_ids)]

    def _compute_institutional_360_metrics(self):
        for tmpl in self:
            products = tmpl.product_variant_ids
            if not products:
                tmpl.held_asset_count = 0
                tmpl.consumed_qty_total = 0.0
                tmpl.personnel_consumer_count = 0
                continue

            # Active held assets currently issued
            assets = self.env['institutional.asset.item'].search([
                ('product_id', 'in', products.ids),
                ('status', '=', 'issued')
            ])
            tmpl.held_asset_count = len(assets)

            # Cumulative consumed supplies issued
            consumed_lines = self.env['institutional.store.requisition.line'].search([
                ('product_id', 'in', products.ids),
                ('state', '=', 'done')
            ])
            tmpl.consumed_qty_total = sum(consumed_lines.mapped('issued_qty')) or sum(consumed_lines.mapped('approved_qty'))

            # Distinct teachers and staff holding equipment or consumed supplies
            asset_users = assets.mapped('assigned_user_id')
            line_users = consumed_lines.mapped('requested_by_id')
            all_users = asset_users | line_users
            tmpl.personnel_consumer_count = len(all_users)

    def action_view_held_assets(self):
        self.ensure_one()
        return {
            'name': _('Active Held Assets - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'institutional.asset.item',
            'view_mode': 'list,form',
            'domain': [('product_id', 'in', self.product_variant_ids.ids), ('status', '=', 'issued')],
            'context': {
                'default_product_id': self.product_variant_ids[0].id if self.product_variant_ids else False,
                'default_status': 'issued',
            },
        }

    def action_view_consumed_supplies(self):
        self.ensure_one()
        return {
            'name': _('Cumulative Consumed Supplies - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'institutional.store.requisition.line',
            'view_mode': 'list,kanban,pivot',
            'domain': [('product_id', 'in', self.product_variant_ids.ids), ('state', '=', 'done')],
            'context': {
                'search_default_group_person': 1,
            },
        }

    def action_view_personnel_consumers(self):
        self.ensure_one()
        if self.institutional_item_type == 'asset':
            return {
                'name': _('Personnel Asset Holders - %s') % self.name,
                'type': 'ir.actions.act_window',
                'res_model': 'institutional.asset.item',
                'view_mode': 'list,kanban,pivot,form',
                'domain': [('product_id', 'in', self.product_variant_ids.ids), ('status', '=', 'issued')],
                'context': {
                    'search_default_group_dept': 1,
                },
            }
        else:
            return {
                'name': _('Personnel Consumers Breakdown - %s') % self.name,
                'type': 'ir.actions.act_window',
                'res_model': 'institutional.store.requisition.line',
                'view_mode': 'kanban,pivot,list',
                'domain': [('product_id', 'in', self.product_variant_ids.ids), ('state', '=', 'done')],
                'context': {
                    'search_default_group_person': 1,
                    'search_default_group_dept': 1,
                },
            }
