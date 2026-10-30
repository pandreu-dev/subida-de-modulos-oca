# -*- coding: utf-8 -*-
"""Registro de cada cambio hecho por la «puerta de atrás» (carga inicial /
corrección de meses cerrados). Un registro por celda modificada: quién, cuándo,
qué había y qué se puso, y el motivo que escribió la persona."""
from odoo import fields, models

from .produccion import CONCEPTOS


class ProduccionPlanAjuste(models.Model):
    _name = "produccion.plan.ajuste"
    _description = "Ajuste de producción en mes cerrado (registro de auditoría)"
    _order = "fecha desc, id desc"

    project_id = fields.Many2one("project.project", string="Proyecto", required=True,
                                 ondelete="cascade", index=True)
    company_id = fields.Many2one(related="project_id.company_id", store=True)
    currency_id = fields.Many2one(related="project_id.currency_id", store=True)
    fecha_mes = fields.Date(string="Mes ajustado", required=True)
    concepto = fields.Selection(CONCEPTOS, string="Concepto", required=True)
    importe_anterior = fields.Monetary(string="Valor anterior", readonly=True)
    importe_nuevo = fields.Monetary(string="Valor nuevo", readonly=True)
    user_id = fields.Many2one("res.users", string="Realizado por", required=True,
                              default=lambda self: self.env.user, readonly=True)
    fecha = fields.Datetime(string="Fecha del ajuste", required=True,
                            default=fields.Datetime.now, readonly=True)
    motivo = fields.Text(string="Motivo", required=True, readonly=True)
    origen = fields.Selection(
        [("manual", "Asistente (manual)"), ("excel", "Asistente (Excel)")],
        string="Origen", required=True, default="manual", readonly=True)
