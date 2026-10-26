# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _

class InstitutionalRequisitionStageMatrix(models.Model):
    _name = 'institutional.requisition.stage.matrix'
    _description = 'Product Pipeline Stage Quantity Matrix Dashboard'
    _auto = False
    _order = 'total_requested_qty desc, product_id'

    product_id = fields.Many2one('product.product', string='Product Item', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    category_id = fields.Many2one('product.category', string='Category', readonly=True)
    
    total_requested_qty = fields.Float(string='Total Requisitioned Qty', readonly=True)
    draft_qty = fields.Float(string='Stage 1: Draft Qty', readonly=True)
    dept_pending_qty = fields.Float(string='Stage 2: Dept Pending Qty', readonly=True)
    registrar_pending_qty = fields.Float(string='Stage 3: Registrar Pending Qty', readonly=True)
    ready_qty = fields.Float(string='Stage 4: Ready Qty', readonly=True)
    issued_qty = fields.Float(string='Stage 5: Issued Qty', readonly=True)
    shortfall_qty = fields.Float(string='Stage 6: Shortfall Qty', readonly=True)
    on_hand_qty = fields.Float(string='Store Stock On Hand', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    l.product_id AS product_id,
                    p.product_tmpl_id AS product_tmpl_id,
                    r.department_id AS department_id,
                    pt.categ_id AS category_id,
                    SUM(COALESCE(l.approved_qty, l.requested_qty, 0)) AS total_requested_qty,
                    SUM(CASE WHEN r.state = 'draft' THEN COALESCE(l.requested_qty, 0) ELSE 0 END) AS draft_qty,
                    SUM(CASE WHEN r.state = 'submitted' THEN COALESCE(l.requested_qty, 0) ELSE 0 END) AS dept_pending_qty,
                    SUM(CASE WHEN r.state = 'dept_approved' THEN COALESCE(l.approved_qty, l.requested_qty, 0) ELSE 0 END) AS registrar_pending_qty,
                    SUM(CASE WHEN r.state = 'ready_for_issue' THEN COALESCE(l.approved_qty, 0) ELSE 0 END) AS ready_qty,
                    SUM(CASE WHEN r.state = 'done' THEN COALESCE(l.issued_qty, l.approved_qty, 0) ELSE 0 END) AS issued_qty,
                    SUM(COALESCE(l.stock_shortfall_qty, 0)) AS shortfall_qty,
                    MAX(COALESCE(sq.quantity, 0)) AS on_hand_qty
                FROM institutional_store_requisition_line l
                JOIN institutional_store_requisition r ON l.requisition_id = r.id
                JOIN product_product p ON l.product_id = p.id
                JOIN product_template pt ON p.product_tmpl_id = pt.id
                LEFT JOIN (
                    SELECT product_id, SUM(quantity) AS quantity
                    FROM stock_quant
                    WHERE location_id IN (SELECT id FROM stock_location WHERE usage = 'internal')
                    GROUP BY product_id
                ) sq ON sq.product_id = l.product_id
                GROUP BY l.product_id, p.product_tmpl_id, r.department_id, pt.categ_id
            )
        """ % self._table)
