# -*- coding: utf-8 -*-
from . import models

def post_init_hook(env):
    user_data = [
        ('demo_user_teacher', 'head_fe@butex.edu.bd', 'head123'),
        ('demo_user_officer', 'tanvir@butex.edu.bd', 'officer123'),
        ('demo_user_3rd_officer', 'ali@butex.edu.bd', 'officer123'),
        ('demo_user_dept_head_fe', 'head_fe@butex.edu.bd', 'head123'),
        ('demo_user_dept_head_wpe', 'head_wpe@butex.edu.bd', 'head123'),
        ('demo_user_registrar', 'registrar@butex.edu.bd', 'registrar123'),
        ('demo_user_store_incharge', 'store@butex.edu.bd', 'store123'),
        ('demo_user_procurement_head', 'procurement@butex.edu.bd', 'proc123'),
        ('demo_user_store_admin', 'admin@butex.edu.bd', 'admin123'),
    ]
    group_hr_user = env.ref('hr.group_hr_user', raise_if_not_found=False)
    for xml_id, email, pwd in user_data:
        user = env.ref('institutional_inventory_procurement.' + xml_id, raise_if_not_found=False)
        if user:
            user.write({'login': email, 'email': email, 'password': pwd})
            if group_hr_user:
                user.write({'group_ids': [(4, group_hr_user.id)]})

    admin_user = env.ref('base.user_admin', raise_if_not_found=False)
    group_admin = env.ref('institutional_inventory_procurement.group_institutional_admin', raise_if_not_found=False)
    if admin_user and group_admin:
        admin_user.write({'group_ids': [(4, group_admin.id)]})

    # Centralize Currency to Bangladeshi Taka (BDT ৳)
    try:
        bdt = env.ref('base.BDT', raise_if_not_found=False)
        if not bdt:
            bdt = env['res.currency'].sudo().search([('name', '=', 'BDT')], limit=1)
        if bdt:
            bdt.sudo().write({'active': True, 'symbol': '৳', 'position': 'before'})
            companies = env['res.company'].sudo().search([])
            companies.write({'currency_id': bdt.id})
    except Exception:
        pass

    # Seed Positive On-Hand Inventory for Central Store (WH/Stock)
    try:
        stock_location = env.ref('stock.stock_location_stock', raise_if_not_found=False)
        if stock_location:
            products = env['product.product'].sudo().search([('type', '=', 'consu')])
            stock_qty_map = {
                'charta': 500.0,
                'paper': 500.0,
                'ballpoint': 200.0,
                'toner': 50.0,
                'dell': 20.0,
                'desktop': 15.0,
                'server': 10.0,
                'ram': 30.0,
                'ssd': 30.0,
                'stapler': 50.0,
            }
            for p in products:
                qty = 25.0
                for k, v in stock_qty_map.items():
                    if k.lower() in p.name.lower():
                        qty = v
                        break
                quant = env['stock.quant'].sudo().search([('product_id', '=', p.id), ('location_id', '=', stock_location.id)], limit=1)
                if quant:
                    quant.sudo().write({'inventory_quantity': qty})
                    quant.sudo().action_apply_inventory()
                else:
                    env['stock.quant'].sudo().create({
                        'product_id': p.id,
                        'location_id': stock_location.id,
                        'inventory_quantity': qty,
                    }).action_apply_inventory()
    except Exception:
        pass
