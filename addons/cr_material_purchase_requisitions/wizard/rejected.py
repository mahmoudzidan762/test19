# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import api, fields, models


class RejectWizard(models.TransientModel):
    _name = "reject.wizard"
    _description = "reject wizard"

    reason_for_rejection = fields.Char(string="Reason For Rejection")

    def action_rejection(self):
        active_id = self.env.context.get("active_id")
        if active_id:
            requisition = self.env["material.purchase.requisition"].browse(active_id)
            requisition.write(
                {"state": "rejected", "reason_for_rejection": self.reason_for_rejection}
            )
