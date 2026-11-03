# -*- coding: utf-8 -*-
"""Líneas de planificación de producción: un registro por proyecto, mes y concepto."""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Las 10 tipologías de coste del documento de especificaciones (en su orden).
CONCEPTOS_COSTE = [
    ("horas_internas", "Horas internas"),
    ("horas_externas", "Horas externas (SCR)"),
    ("contratas_fp", "Contratas (Fix price)"),
    ("contratas_adm", "Contratas (Por administración)"),
    ("materiales", "Materiales"),
    ("viajes", "Gastos de Viaje"),
    ("riesgos", "Provisión de riesgos"),
    ("rent_lease", "Gastos Rent & Lease"),
    ("otros", "Otros costes"),
    ("penalizacion", "Penalización"),
]
CONCEPTOS = [("ingreso", "INGRESO")] + CONCEPTOS_COSTE
CLAVES_COSTE = [c[0] for c in CONCEPTOS_COSTE]

# Testigo que autoriza a escribir en meses cerrados. Es un OBJETO Python, no un
# valor: solo puede ponerlo en el contexto el código del servidor (motor, generar
# planificación, carga inicial autorizada). Por la API (JSON-RPC) es imposible
# fabricarlo, así que nadie puede saltarse la regla 3 «pasando el contexto».
PERMISO_MESES_CERRADOS = object()


class ProduccionPlanLinea(models.Model):
    _name = "produccion.plan.linea"
    _description = "Línea de planificación de producción (proyecto × mes × concepto)"
    _order = "project_id, fecha_mes, secuencia"

    project_id = fields.Many2one("project.project", string="Proyecto", required=True,
                                 ondelete="cascade", index=True)
    company_id = fields.Many2one(related="project_id.company_id", store=True)
    currency_id = fields.Many2one(related="project_id.currency_id", store=True)
    fecha_mes = fields.Date(string="Mes", required=True, index=True,
                            help="Primer día del mes planificado.")
    anio = fields.Integer(compute="_compute_periodo", store=True)
    mes = fields.Integer(compute="_compute_periodo", store=True)
    etiqueta_mes = fields.Char(compute="_compute_periodo", store=True, string="Periodo")
    concepto = fields.Selection(CONCEPTOS, string="Concepto", required=True)
    secuencia = fields.Integer(compute="_compute_secuencia", store=True)
    es_ingreso = fields.Boolean(compute="_compute_secuencia", store=True)

    importe_previsto = fields.Monetary(string="Previsto", aggregator="sum")
    importe_real = fields.Monetary(string="Real", readonly=True, aggregator="sum",
                                   help="Dato real obtenido de Odoo (fase 2).")
    desviacion = fields.Monetary(compute="_compute_desviacion", store=True,
                                 aggregator="sum",
                                 string="Desviación (real − previsto)")
    # NO almacenado a propósito: depende del día de hoy. Almacenado se quedaba
    # congelado con el valor del día en que se creó la línea (un mes abierto
    # seguía "abierto" para siempre) — corregido 18/08/2026.
    mes_cerrado = fields.Boolean(compute="_compute_mes_cerrado", store=False,
                                 help="El mes en curso NUNCA se considera cerrado.")

    @api.model
    def _conceptos_vigentes(self):
        """[(clave, etiqueta)] de TODOS los conceptos, incluidos los que añaden
        otros módulos por selection_add (p. ej. licencias_software)."""
        return list(self._fields["concepto"].selection)

    @api.model
    def _claves_coste_vigentes(self):
        return [c for c, _e in self._conceptos_vigentes() if c != "ingreso"]

    _uniq_linea = models.Constraint(
        "unique(project_id, fecha_mes, concepto)",
        "Ya existe una línea para ese proyecto, mes y concepto.",
    )

    @api.depends("fecha_mes")
    def _compute_periodo(self):
        for r in self:
            if r.fecha_mes:
                r.anio, r.mes = r.fecha_mes.year, r.fecha_mes.month
                r.etiqueta_mes = r.fecha_mes.strftime("%m/%Y")
            else:
                r.anio = r.mes = 0
                r.etiqueta_mes = ""

    @api.depends("concepto")
    def _compute_secuencia(self):
        orden = {c[0]: i for i, c in enumerate(CONCEPTOS)}
        for r in self:
            r.secuencia = orden.get(r.concepto, 99)
            r.es_ingreso = r.concepto == "ingreso"

    @api.depends("importe_previsto", "importe_real")
    def _compute_desviacion(self):
        for r in self:
            r.desviacion = r.importe_real - r.importe_previsto

    @api.depends("fecha_mes")
    def _compute_mes_cerrado(self):
        """Regla 1: el mes en curso SIEMPRE es previsión, nunca cerrado."""
        hoy = fields.Date.context_today(self)
        primero_actual = hoy.replace(day=1)
        for r in self:
            r.mes_cerrado = bool(r.fecha_mes and r.fecha_mes < primero_actual)

    @api.constrains("importe_previsto", "concepto")
    def _check_tcv_linea(self):
        """Regla 2: el ingreso total del proyecto nunca puede superar el TCV.

        Se valida también aquí porque al editar una línea suelta no se dispara la
        restricción declarada en el proyecto. Durante el recálculo automático
        (contexto sin_recalculo) se omite: las escrituras intermedias mezclan
        valores nuevos y antiguos; el reparto final nunca supera el TCV y el
        proyecto lo revalida al terminar.
        """
        if self.env.context.get("sin_recalculo"):
            return
        # solo si lo editado es un ingreso: editar un coste con el TCV de la
        # ficha ya por debajo del plan no debe quedar bloqueado
        if not any(l.concepto == "ingreso" for l in self):
            return
        for proyecto in self.mapped("project_id"):
            tcv = proyecto.tcv_efectivo
            if not tcv:
                continue
            total = sum(l.importe_previsto for l in proyecto.produccion_linea_ids
                        if l.concepto == "ingreso")
            if total > tcv + 0.01:
                raise ValidationError(_(
                    "El ingreso total planificado (%(ing).2f) supera el TCV del proyecto "
                    "«%(proj)s» (%(tcv).2f). El ingreso nunca puede superar el TCV."
                ) % {"ing": total, "tcv": tcv, "proj": proyecto.display_name})

    @api.constrains("importe_previsto")
    def _check_mes_pasado(self):
        """Regla 3: no se pueden modificar ingresos ni costes de meses ya pasados.

        La única excepción es el propio código del módulo (generar la planificación,
        el motor de reales, la carga inicial autorizada), que pone en el contexto
        el testigo PERMISO_MESES_CERRADOS. Un valor cualquiera (True) NO vale: así
        nadie puede saltarse la regla pasando el contexto por la API. (Las
        constraints corren en sudo, por eso no sirve mirar env.su.)"""
        if self.env.context.get("permitir_meses_pasados") is PERMISO_MESES_CERRADOS:
            return
        for r in self:
            if r.mes_cerrado:
                raise ValidationError(_(
                    "No se pueden modificar los datos de un mes ya cerrado (%s). "
                    "Solo son editables el mes en curso y los meses futuros."
                ) % (r.etiqueta_mes or ""))

    def write(self, vals):
        res = super().write(vals)
        if "importe_previsto" in vals and not self.env.context.get("sin_recalculo"):
            self.mapped("project_id")._recalcular_ingresos()
        return res
