# BUTEX Institutional Inventory & Procurement Management
### Odoo 19 Community — Custom Module

> **Module**: `institutional_inventory_procurement`  
> **Version**: 19.0.1.3.0  
> **Platform**: Odoo 19 Community Edition  
> **University**: Bangladesh University of Textiles (BUTEX)  
> **Currency**: Bangladeshi Taka (BDT ৳) — Single Currency  

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [On-Premise Installation](#on-premise-installation)
4. [Database Setup](#database-setup)
5. [Running the Server](#running-the-server)
6. [Module Installation](#module-installation)
7. [Demo Credentials](#demo-credentials)
8. [Complete Workflow Guide](#complete-workflow-guide)
9. [User Roles & Permissions](#user-roles--permissions)
10. [Menu Structure](#menu-structure)
11. [Module Architecture](#module-architecture)
12. [Troubleshooting](#troubleshooting)
13. [SRS Documentation](#srs-documentation)

---

## Overview

This custom Odoo 19 module implements the complete institutional inventory, asset lifecycle, and procurement management system for BUTEX. It replaces manual spreadsheet-based processes with a structured, multi-level approval and tracking system.

### Key Features

| Feature | Description |
|---|---|
| **Demand-Driven Quotas** | Annual/Dept requisitions auto-create & aggregate department quotas |
| **Time-by-Time Requisitions** | Staff submit supplies requests as needed throughout the year |
| **Holding vs Consumed** | Consumables tracked as *Consumed*, serialized assets tracked as *Holdings* |
| **Real-Time Quota Sync** | Quota balances update instantly at every approval, issuance, or cancellation event |
| **Product 360° Analytics** | Per-product: store stock, dept breakdown, personnel consumer list |
| **Personnel Profile Holdings** | Per-staff: cumulative consumed supplies + active held assets |
| **Pipeline Stage Matrix** | Executive dashboard: quantities at each workflow stage per product |
| **Non-Negative Stock Guard** | System blocks issuance if it would cause negative inventory |
| **Asset Component Engine** | Track RAM, SSD, charger, lens, drawer, etc. per serialized asset |
| **Audit Trail** | Immutable log of every quantity change, approval, and back-date |

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **OS** | Ubuntu 20.04 LTS | Ubuntu 22.04 LTS |
| **Python** | 3.10 | 3.11+ |
| **PostgreSQL** | 14 | 14 or 15 |
| **RAM** | 4 GB | 8 GB |
| **Disk** | 10 GB free | 20 GB SSD |
| **Odoo Version** | 19 Community Edition | 19 Community Edition |

---

## On-Premise Installation

### 1. Clone Odoo 19 Community

```bash
git clone https://github.com/odoo/odoo.git --branch 19.0 --depth 1 /opt/odoo19
cd /opt/odoo19
pip3 install -r requirements.txt
```

### 2. Clone This Module

```bash
git clone https://github.com/YOUR-ORG/butex-inventory-odoo.git /opt/butex-inventory-odoo
ln -s /opt/butex-inventory-odoo/institutional_inventory_procurement \
      /opt/odoo19/custom/institutional_inventory_procurement
```

### 3. Create Configuration File

Save as `/opt/odoo19/odoo.conf`:

```ini
[options]
db_host         = /var/run/postgresql
db_port         = 5432
db_user         = odoo
db_password     = your_secure_password
db_name         = butex_inventory
data_dir        = /var/lib/odoo/data
addons_path     = /opt/odoo19/addons,/opt/odoo19/custom
http_port       = 8069
http_interface  = 0.0.0.0
log_level       = info
logfile         = /var/log/odoo/odoo.log
```

---

## Database Setup

```bash
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres psql -c "CREATE USER odoo WITH CREATEDB PASSWORD 'your_secure_password';"
sudo -u postgres createdb -O odoo butex_inventory
```

---

## Running the Server

### First-Time Initialization

```bash
cd /opt/odoo19
python3 odoo-bin -c odoo.conf \
  -d butex_inventory \
  --init=institutional_inventory_procurement \
  --stop-after-init
```

> This creates all tables and loads demo data (departments, employees, products, quotas, assets, sample requisitions).

### Start Server

```bash
python3 odoo-bin -c odoo.conf
```

Access at: **http://localhost:8069**

### systemd Service (Production)

```ini
# /etc/systemd/system/odoo.service
[Unit]
Description=BUTEX Odoo 19 Inventory System
After=network.target postgresql.service

[Service]
Type=simple
User=odoo
ExecStart=/usr/bin/python3 /opt/odoo19/odoo-bin -c /opt/odoo19/odoo.conf
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now odoo
```

---

## Module Installation (Existing Odoo Instance)

1. Go to **Settings → Apps → Update Apps List**
2. Search `Institutional Inventory` → Click **Install**

Or via CLI:
```bash
python3 odoo-bin -c odoo.conf -u institutional_inventory_procurement --stop-after-init
```

---

## Demo Credentials

| Role | Email | Password |
|---|---|---|
| System Admin | `admin@butex.edu.bd` | `admin` |
| Registrar | `registrar@butex.edu.bd` | `admin` |
| Store Incharge | `store@butex.edu.bd` | `admin` |
| Dept Head (WPE) | `wpe.head@butex.edu.bd` | `admin` |
| Faculty | `repon@butex.edu.bd` | `admin` |

> **Change all passwords before production use.**

---

## Complete Workflow Guide

### Step 1 — Annual Requisition (Demand List)

**Who:** Department Head | **Where:** `Institutional Store → Store Requisitions → New`

1. Set **Demand Type** = `Annual Baseline Requisition`
2. Set **Department** and **Fiscal Year**
3. Add products with annual quantities needed
4. Submit → Dept Head Approve → Registrar Approve

> On **Registrar approval**, the system automatically creates or aggregates the Department Quota record for each product/department/year combination.

---

### Step 2 — Quota Auto-Allocation

**Where:** `Institutional Store → Department Quota Allocations`

- Auto-created on Registrar approval of Annual/Dept requisitions
- Multiple approved requisitions for the same product/dept **cumulate**: `allocated_qty += newly_approved_qty`
- Balances update in real-time on every issuance, cancellation, or return event

---

### Step 3 — Individual Personnel Requisition

**Who:** Any faculty/officer/staff | **Where:** `Institutional Store → Store Requisitions → New`

1. Set **Demand Type** = `Individual Personnel Requisition`
2. Add products needed (not all at once — submit as needs arise throughout the year)
3. Live warnings shown per line: **Quota Remaining** + **Store Stock Available**
4. Submit → Approval chain begins

---

### Step 4 — Approval Chain

```
Faculty Submits
    ↓
Dept Head Approves  (or Rejects)
    ↓
Registrar Approves  (or Rejects)
    ↓
Store Incharge reviews, may adjust Approved Qty (audit logged)
    ↓
Mark Ready for Issue  →  Requester notified by email
    ↓
Issue Stock  →  Done
```

---

### Step 5 — Store Fulfillment & Stock Issuance

**Who:** Store Incharge | **Where:** Open a `Registrar Approved` requisition

1. Review lines — stock warning banners highlight shortfalls
2. Adjust `Approved Qty` if needed (reason is mandatory, logged immutably)
3. If shortfall: click **Send to Procurement** on the line → Purchase Order auto-created
4. **Mark Ready for Issue** — requester collects from Central Store
5. **Issue Stock** — system simultaneously:
   - Deducts inventory (creates native `stock.picking` + validates it)
   - Sets `issued_qty = approved_qty` on all lines
   - Updates `consumed_qty` on Department Quota (for consumables)
   - Sets serialized assets to `Issued` status (updates `held_qty` on quota)
   - Blocks if any item would make inventory negative

---

### Step 6 — Asset Lifecycle Management

**Where:** `Institutional Store → Asset Registry`

#### Register
New asset → Enter product, serial number, condition → saved as `Available`

#### Issue to User
Open asset → **Mark as Issued** → select user, dept, location
- Status: `Available` → `Issued / Unavailable`
- Quota `held_qty` auto-increments

#### Return
Open asset → **Mark as Returned** → update condition
- Status: `Issued` → `Available in Store`
- Native stock return picking created
- Quota `held_qty` auto-decrements

#### Component Tracking
`Asset form → Hardware Components tab`
- Add/detach/transfer components (RAM, SSD, Charger, Lens, etc.)
- All movements logged in Component History

---

### Step 7 — Analytics & Reporting

| View | Location | Description |
|---|---|---|
| **Product 360°** | `Inventory → Products → [Any Product]` | Smart buttons: Held Assets, Consumed, Personnel |
| **Personnel Holdings** | `Institutional Store → Personnel Profile Holdings` | Per-staff: consumed supplies + held assets + inline Return button |
| **Pipeline Matrix** | `Institutional Store → Reporting → Pipeline Stage Matrix` | Qty at every workflow stage per product |
| **Quota Dashboard** | `Institutional Store → Department Quota Allocations` | Allocated vs Consumed vs Remaining with status badges |
| **Requisition PDF** | `Done Requisition → Print` | Voucher with approval signatures |
| **Asset Registry PDF** | `Reporting → Asset Registry Report` | Full asset inventory with holders |
| **Low Stock PDF** | `Reporting → Low Stock Alert` | Products needing reorder |

---

## User Roles & Permissions

| Role | Permission Group | Can Do |
|---|---|---|
| **Normal User** | `group_institutional_user` | Create/submit own requisitions, view own holdings |
| **Dept Head** | `group_institutional_dept_head` | Approve/reject dept requisitions, view dept quotas |
| **Store Incharge** | `group_institutional_store_incharge` | Issue stock, manage assets, adjust approved qty |
| **Registrar** | `group_institutional_registrar` | Final approval, university-wide view |
| **Admin** | `group_institutional_admin` | Full system access |

Assign at: `Settings → Users → [User] → Groups`

---

## Menu Structure

```
Institutional Store
├── Store Requisitions
│   ├── All Requisitions
│   ├── My Requisitions
│   ├── Annual Requisitions
│   └── + New
├── Department Quota Allocations
├── Asset Registry
│   ├── All Assets
│   └── Asset Components
├── Personnel Profile Holdings
├── Reporting
│   ├── Product Pipeline Stage Matrix
│   ├── Asset Registry Report
│   └── Low Stock Alert Report
└── Configuration (Admin)

Inventory (Native Odoo — Extended)
└── Products  →  Product 360° smart buttons added
```

---

## Module Architecture

```
institutional_inventory_procurement/
├── __manifest__.py
├── __init__.py
│
├── models/
│   ├── store_requisition.py        # Requisition engine, approval workflow, quota triggers
│   ├── department_quota.py         # Quota model + real-time lifecycle sync + dynamic read
│   ├── asset_item.py               # Asset lifecycle, custody, component link, quota sync
│   ├── asset_component.py          # Hardware component tracking per asset
│   ├── asset_component_history.py  # Component swap/transfer history log
│   ├── asset_custody_log.py        # Asset lifecycle event log
│   ├── product_template.py         # Product 360° analytics compute fields
│   ├── hr_employee.py              # Personnel profile holdings extension
│   ├── store_requisition_audit.py  # Immutable audit trail model
│   └── requisition_stage_matrix.py # SQL view for pipeline dashboard
│
├── views/
│   ├── requisition_views.xml
│   ├── department_quota_views.xml
│   ├── asset_views.xml
│   ├── hr_employee_views.xml
│   ├── product_views.xml
│   ├── pipeline_matrix_views.xml
│   ├── reporting_views.xml
│   └── menus.xml
│
├── security/
│   ├── security_groups.xml
│   ├── security_rules.xml
│   └── ir.model.access.csv
│
├── data/
│   ├── sequence_data.xml           # REQ/YYYY/NNNN, AST/YYYY/NNNN sequences
│   └── mail_templates.xml          # Email notifications at each workflow step
│
├── demo/
│   ├── demo_users.xml
│   ├── demo_departments.xml        # WPE, FE, CSE
│   ├── demo_employees.xml
│   ├── demo_products.xml           # 22 products (consumables + serialized assets)
│   ├── demo_quotas.xml
│   ├── demo_assets.xml
│   └── demo_requisitions.xml
│
└── reports/
    ├── report_actions.xml
    ├── report_requisition_slip.xml
    ├── report_asset_registry.xml
    └── report_low_stock.xml
```

---

## Troubleshooting

### Quota shows stale values
Quotas recompute on every form open. If list view is stale, open the quota record.
Force upgrade:
```bash
python3 odoo-bin -c odoo.conf -u institutional_inventory_procurement --stop-after-init
```

### Issuance blocked (non-negative inventory)
Reduce `Approved Qty` OR create a Purchase Order for the shortfall → receive goods → then issue.

### Asset already-issued error
Return the asset first (`Mark as Returned`), then re-issue.

### PostgreSQL connection error
```bash
pg_isready -h /var/run/postgresql -p 5432
sudo systemctl restart postgresql
```

### Viewing logs
```bash
# Manual run
tail -f /var/log/odoo/odoo.log

# systemd service
sudo journalctl -u odoo -f
```

---

## SRS Documentation

Full Software Requirements Specification (v1.3.0) is in `docs/`:

| Format | File |
|---|---|
| Markdown | `docs/SRS_BUTEX_Institutional_Inventory_v1.3.0.md` |
| HTML | `docs/SRS_BUTEX_Institutional_Inventory_v1.3.0.html` |
| PDF | `docs/SRS_BUTEX_Institutional_Inventory_v1.3.0.pdf` |

---

## License

LGPL-3 — [GNU Lesser General Public License v3](https://www.gnu.org/licenses/lgpl-3.0.en.html)

---

*BUTEX Institutional Inventory & Procurement — Odoo 19 Custom Module*  
*Developed by Nascenia / Antigravity — October 2026*
