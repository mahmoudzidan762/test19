# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseRequisition(models.Model):
    _name = "material.purchase.requisition"
    _description = "material purchase requisition"

    name = fields.Char(
        string="Requisition Reference",
        required=True,
        copy=False,
        readonly=True,
        index="trigram",
        default=lambda self: "New",
    )
    request_action = fields.Selection(
        [
            ("purchase order", "Purchase Order"),
            ("internal picking", "Internal Picking"),
        ],
        string="Requisition Type",
    )
    employee_id = fields.Many2one("hr.employee", string="Employee Name", required=True)
    department_id = fields.Many2one("hr.department", string="Department Name")
    requisition_responsible = fields.Many2one("res.users", string="Requisition Owner")
    requisition_date = fields.Date(
        string="Request Date", default=fields.Date.context_today
    )
    received_date = fields.Date(string="Date Received")
    requisition_deadline = fields.Date(string="Requisition Expiration Date")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("waiting_department_approval", "CEO Approval"),
            ("waiting_ir_approval", "Accounting Approval"),
            ("approved", "Approved"),
            ("purchase_order_created", "Purchase Order Created"),
            ("received", "Received"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="new",
    )
    requisition_lines = fields.One2many(
        "material.purchase.requisition.line",
        "requisition_id",
        string="Requisition Lines",
    )
    destination_location_id = fields.Many2one(
        "stock.location", string="Destination Location"
    )
    source_location_id = fields.Many2one("stock.location", string="Source Location")
    picking_type_id = fields.Many2one("stock.picking.type", string="Picking Type")
    confirmed_by_id = fields.Many2one("res.users", string="Confirmation Person")
    department_manager_id = fields.Many2one("res.users", string="Department Head")
    approved_id = fields.Many2one("res.users", string="Approval Authority")
    rejected_id = fields.Many2one("res.users", string="Rejection Authority")
    confirmed_date = fields.Date(string="Confirmation Date")
    department_approval_date = fields.Date(string="Department Approval Date")
    approved_date = fields.Date(string="Approved Date")
    rejected_date = fields.Date(string="Rejected Date")
    reason_for_requisition = fields.Text(string="Reason for Requisition")
    reason_for_rejection = fields.Text(string="Reason for Rejection")
    internal_transfer_count = fields.Integer(
        string="Internal Transfer count", compute="_compute_internal_transfer_count"
    )
    purchase_count = fields.Integer(
        string="Purchase Count", compute="_compute_purchase_count"
    )
    journal_id = fields.Many2one("account.journal", string="Journal")
    total_amount = fields.Float(string="Total Amount", compute="_compute_total_amount")

    @api.depends("requisition_lines.quantity", "requisition_lines.unit_price")
    def _compute_total_amount(self):
        for requisition in self:
            total = 0.0
            for line in requisition.requisition_lines:
                total += line.quantity * line.unit_price
            requisition.total_amount = total

    @api.model
    def create(self, vals):
        # Odoo may call create with a list of dicts
        if isinstance(vals, list):
            for val in vals:
                if val.get("name", "New") == "New":
                    val["name"] = (
                            self.env["ir.sequence"].next_by_code("material.purchase.requisition")
                            or "New"
                    )
            return super(PurchaseRequisition, self).create(vals)

        # Single dict create
        if vals.get("name", "New") == "New":
            vals["name"] = (
                    self.env["ir.sequence"].next_by_code("material.purchase.requisition")
                    or "New"
            )

        return super(PurchaseRequisition, self).create(vals)

    def action_confirm(self):
        self.write(
            {
                "state": "waiting_department_approval",
                "confirmed_by_id": self.env.user.id,
                "confirmed_date": fields.Date.context_today(self),
            }
        )

    def action_dept_approve(self):
        self.write(
            {
                "state": "waiting_ir_approval",
                "department_manager_id": self.env.user.id,
                "department_approval_date": fields.Date.context_today(self),
            }
        )

    def action_approve(self):
        self.write(
            {
                "state": "approved",
                "approved_id": self.env.user.id,
                "approved_date": fields.Date.context_today(self),
            }
        )

    def action_create_picking_and_po(self):
        """Create internal pickings and purchase orders from requisition lines."""

        # Update state
        self.write({"state": "purchase_order_created"})

        picking_ids = []

        # ------------------------------
        # Validate locations
        # ------------------------------
        source_loc = self.source_location_id or self.picking_type_id.default_location_src_id
        dest_loc = self.destination_location_id or self.picking_type_id.default_location_dest_id

        if not source_loc:
            raise UserError("Source Location is missing on the requisition or picking type.")

        if not dest_loc:
            raise UserError("Destination Location is missing on the requisition or picking type.")

        # ------------------------------
        # Create Internal Pickings
        # ------------------------------
        for line in self.requisition_lines:
            if line.request_action == "internal picking":
                for vendor in line.vendor_ids:
                    picking_vals = {
                        "picking_type_id": self.picking_type_id.id,
                        "origin": self.name,
                        "requisition_order": self.name,
                        "partner_id": vendor.id,
                        "location_id": source_loc.id,
                        "location_dest_id": dest_loc.id,

                        # Correct field for stock moves
                        "move_ids": [
                            (
                                0,
                                0,
                                {
                                    "display_name": line.product_id.name,
                                    "product_id": line.product_id.id,
                                    "product_uom_qty": line.quantity,
                                    "product_uom": line.product_id.uom_id.id,
                                    "location_id": source_loc.id,
                                    "location_dest_id": dest_loc.id,
                                },
                            )
                        ],
                    }

                    picking = self.env["stock.picking"].create(picking_vals)
                    line.write({"picking_id": picking.id})
                    picking_ids.append(picking.id)

        # ------------------------------
        # Group Lines by Vendor for PO
        # ------------------------------

        vendor_lines = {}

        for line in self.requisition_lines:
            if line.request_action == "purchase order":
                for vendor in line.vendor_ids:
                    vendor_lines.setdefault(vendor.id, [])
                    vendor_lines[vendor.id].append(
                        {
                            "product_id": line.product_id.id,
                            "product_qty": line.quantity,
                            "product_uom_id": line.product_id.uom_id.id,
                            "name": line.description or line.product_id.name,
                            "price_unit": line.unit_price,
                        }
                    )

        # ------------------------------
        # Create Purchase Orders
        # ------------------------------
        purchase_ids = []

        for vendor_id, lines in vendor_lines.items():
            po_vals = {
                "partner_id": vendor_id,
                "requisition_order": self.name,
                "order_line": [(0, 0, line) for line in lines],
            }

            po = self.env["purchase.order"].create(po_vals)
            purchase_ids.append(po.id)

            # Attach PO back to requisition lines
            for line in self.requisition_lines:
                if vendor_id in line.vendor_ids.ids:
                    line.write({"purchase_order_id": po.id})

        return {
            "pickings": picking_ids,
            "purchase_orders": purchase_ids,
        }

    def action_received(self):
        self.write({"state": "received"})

    def action_reset_to_draft(self):
        self.write({"state": "new"})

    def action_reject(self):
        self.write(
            {
                "rejected_id": self.env.user.id,
                "rejected_date": fields.Date.context_today(self),
            }
        )
        return {
            "name": "Reason Of Rejection",
            "view_mode": "form",
            "res_model": "reject.wizard",
            "type": "ir.actions.act_window",
            "target": "new",
        }

    def view_internal_picking(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Transfers",
            "res_model": "stock.picking",
            "view_type": "form",
            "view_mode": "tree,form",
            "domain": [("requisition_order", "=", self.name)],
            "target": "current",
        }

    def _compute_internal_transfer_count(self):
        self.internal_transfer_count = self.env["stock.picking"].search_count(
            [("requisition_order", "=", self.name)]
        )

    def view_purchase_order(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Purchase Order",
            "res_model": "purchase.order",
            "view_type": "form",
            "view_mode": "list,form",
            "domain": [("requisition_order", "=", self.name)],
            "target": "current",
        }

    def _compute_purchase_count(self):
        self.purchase_count = self.env["purchase.order"].search_count(
            [("requisition_order", "=", self.name)]
        )


class MaterialPurchaseRequisitionLine(models.Model):
    _name = "material.purchase.requisition.line"
    _description = "Material Purchase Requisition Lines"

    request_action = fields.Selection(
        [
            ("purchase order", "Purchase Order"),
            ("internal picking", "Internal Picking"),
        ],
        string="Requisition Type",
    )
    product_id = fields.Many2one("product.product", string="Product", required=True)
    description = fields.Char(string="Description", related="product_id.name")
    quantity = fields.Float(string="Quantity", required=True)
    unit_of_measure = fields.Many2one(
        "uom.uom", string="Unit of Measure", related="product_id.uom_id"
    )
    vendor_ids = fields.Many2many("res.partner", string="Vendors")
    requisition_id = fields.Many2one(
        "material.purchase.requisition", string="Requisition"
    )
    picking_id = fields.Many2one("stock.picking", string="Picking")
    purchase_order_id = fields.Many2one("purchase.order", string="Purchase Order")
    unit_price = fields.Float(string="Unit Price")
    cost_center_id = fields.Many2one("account.analytic.account", string="Cost Center")
