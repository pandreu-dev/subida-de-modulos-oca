# -*- coding: utf-8 -*-
"""Maestros de Studio pasados a codigo.

ESTRATEGIA (sin perder datos): se define cada modelo con EL MISMO nombre tecnico
(`x_...`) y LOS MISMOS nombres de campo (`x_name`, `x_active`, `x_studio_sequence`,
y `x_studio_divisin` en practica) que ya usa Studio. Asi Odoo REUTILIZA la tabla y
los registros existentes (mismos ids) -> las many2one de empleados/leads siguen
validas y no se migra ni un dato.

Nota: Odoo reconoce `x_active` como campo de archivado (equivalente a `active`).
No se replica el "chatter" que Studio anadio (actividades/mensajes): esos campos no
son datos de negocio y quedan como campos manuales, sin usarse en estas vistas.
"""

from odoo import fields, models

DIVISION_SELECTION = [
    ("NODO RENOVABLES", "NODO RENOVABLES"),
    ("NODO COMUNICACIONES", "NODO COMUNICACIONES"),
    ("SELECT ASTERISCO", "SELECT ASTERISCO"),
    ("BPO", "BPO"),
    ("DIGITAL", "DIGITAL"),
]


class XTipoEmpleado(models.Model):
    _name = "x_tipo_empleado"
    _description = "Tipo empleado"
    _order = "x_studio_sequence, x_name"
    _rec_name = "x_name"

    x_name = fields.Char(string="Descripcion", required=True, translate=True)
    x_active = fields.Boolean(string="Activo", default=True)
    x_studio_sequence = fields.Integer(string="Secuencia", default=10)


class XSubtipoEmpleado(models.Model):
    _name = "x_subtipo_empleado"
    _description = "Subtipo empleado"
    _order = "x_studio_sequence, x_name"
    _rec_name = "x_name"

    x_name = fields.Char(string="Descripcion", required=True, translate=True)
    x_active = fields.Boolean(string="Activo", default=True)
    x_studio_sequence = fields.Integer(string="Secuencia", default=10)


class XTipoDePersonal(models.Model):
    _name = "x_tipo_de_personal"
    _description = "Tipo de personal"
    _order = "x_studio_sequence, x_name"
    _rec_name = "x_name"

    x_name = fields.Char(string="Descripcion", required=True, translate=True)
    x_active = fields.Boolean(string="Activo", default=True)
    x_studio_sequence = fields.Integer(string="Secuencia", default=10)


class XSector(models.Model):
    _name = "x_sector"
    _description = "Sector"
    _order = "x_studio_sequence, x_name"
    _rec_name = "x_name"

    x_name = fields.Char(string="Descripcion", required=True, translate=True)
    x_active = fields.Boolean(string="Activo", default=True)
    x_studio_sequence = fields.Integer(string="Secuencia", default=10)


class XCrmPractica(models.Model):
    _name = "x_crm_practica"
    _description = "CRM Practica (Estructura)"
    _order = "x_studio_sequence, x_name"
    _rec_name = "x_name"

    x_name = fields.Char(string="Descripcion", required=True, translate=True)
    x_active = fields.Boolean(string="Activo", default=True)
    x_studio_sequence = fields.Integer(string="Secuencia", default=10)
    # Selection: las claves DEBEN coincidir EXACTAS con los valores ya guardados.
    x_studio_divisin = fields.Selection(
        selection=DIVISION_SELECTION, string="Division"
    )
