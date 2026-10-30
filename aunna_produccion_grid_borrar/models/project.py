# -*- coding: utf-8 -*-
from odoo import _, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    def action_ver_produccion_grid(self):
        """Abre la cuadrícula (vista grid Enterprise) de este proyecto."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Producción · %s") % self.display_name,
            "res_model": "produccion.plan.linea",
            "view_mode": "grid,list,pivot",
            "domain": [("project_id", "=", self.id)],
            "context": {"default_project_id": self.id},
        }
