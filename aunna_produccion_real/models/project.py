# -*- coding: utf-8 -*-
"""Extensión del proyecto: recálculo de actuals, detección de datos obsoletos,
TCV efectivo y endpoint JSON de la pestaña Seguimiento económico."""
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .produccion_real import TIPOS_COMPRA

ETIQUETAS_COSTE_BR = dict(
    TIPOS_COMPRA
    + [
        ("horas_internas", "Horas internas"),
        ("horas_externas", "Horas externas (SCR)"),
        ("riesgos", "Provisión de riesgos"),
        ("rent_lease", "Gastos Rent & Lease"),
        ("penalizacion", "Penalización"),
    ]
)

# Orden de presentación de los costes en la vista BR y el Excel
ORDEN_COSTES_BR = [
    "horas_internas",
    "horas_externas",
    "contratas_fp",
    "contratas_adm",
    "materiales",
    "viajes",
    "licencias_software",
    "riesgos",
    "rent_lease",
    "otros",
    "penalizacion",
]


class ProjectProject(models.Model):
    _inherit = "project.project"

    produccion_avance_ids = fields.One2many(
        "produccion.avance.mes", "project_id", string="Avances mensuales"
    )
    produccion_real_last_update = fields.Datetime(
        string="Último recálculo de reales", readonly=True
    )
    produccion_real_stale = fields.Boolean(
        string="Reales desactualizados", compute="_compute_produccion_real_stale"
    )
    # El TCV efectivo (ficha del proyecto `tcv_amount`, con fallback al manual)
    # y su fuente los define ya el módulo base (aunna_produccion): aquí solo
    # se consumen.

    # ------------------------------------------------------------------
    # Frescura: ¿hay movimientos posteriores al último recálculo?
    # ------------------------------------------------------------------
    def _compute_produccion_real_stale(self):
        Analitica = self.env["account.analytic.line"].sudo()
        Move = self.env["account.move.line"].sudo()
        for project in self:
            marca = project.produccion_real_last_update
            if not marca:
                project.produccion_real_stale = bool(project.produccion_linea_ids)
                continue
            stale = bool(
                Analitica.search_count(
                    [
                        ("project_id", "=", project.id),
                        ("write_date", ">", marca),
                    ],
                    limit=1,
                )
            )
            motor = self.env["produccion.real.motor"]
            cuenta = motor._cuenta_analitica(project)
            if not stale and cuenta:
                stale = bool(
                    Move.search_count(
                        [
                            ("analytic_distribution", "in", [cuenta.id]),
                            ("write_date", ">", marca),
                        ],
                        limit=1,
                    )
                )
            # albaranes (recepciones, devoluciones, entregas) y gastos nuevos
            if not stale and "stock.move" in self.env:
                movs = motor._movimientos_compra(project, cuenta)
                stale = bool(movs.filtered(lambda m: m.write_date and m.write_date > marca))
                if not stale and "project_id" in self.env["stock.picking"]._fields:
                    stale = bool(self.env["stock.picking"].sudo().search_count(
                        [("project_id", "=", project.id), ("write_date", ">", marca)], limit=1))
            if not stale and cuenta and "hr.expense" in self.env:
                stale = bool(self.env["hr.expense"].sudo().search_count(
                    [("analytic_distribution", "in", [cuenta.id]), ("write_date", ">", marca)],
                    limit=1))
            project.produccion_real_stale = stale

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_recalcular_produccion_real(self):
        """Botón «Recalcular»: actuals + sincronización de avances."""
        motor = self.env["produccion.real.motor"]
        Avance = self.env["produccion.avance.mes"]
        for project in self:
            project._sincronizar_tcv()  # si el TCV de la ficha cambió, rehacer reparto
            motor.recalcular_proyectos(project)
            Avance.sincronizar_proyecto(project)
            Avance.congelar_meses_cerrados(project)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": "Producción",
                "message": "Datos reales recalculados.",
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    @api.model
    def cron_recalcular_produccion_real(self, meses_atras=2):
        """Cron: recalcula proyectos activos con planificación. Ventana corta a
        diario; el día 1 de cada mes, el año completo."""
        hoy = fields.Date.context_today(self)
        proyectos = self.search(
            [("active", "=", True), ("produccion_linea_ids", "!=", False)]
        )
        motor = self.env["produccion.real.motor"]
        if hoy.day == 1:
            desde = None  # día 1: repaso del periodo completo de cada proyecto
        else:
            from dateutil.relativedelta import relativedelta

            desde = hoy.replace(day=1) - relativedelta(months=meses_atras)
        Avance = self.env["produccion.avance.mes"]
        for project in proyectos:
            project._sincronizar_tcv()
            motor.recalcular_proyectos(project, fecha_desde=desde)
            Avance.sincronizar_proyecto(project)
            Avance.congelar_meses_cerrados(project)
        return True

    def action_abrir_avances(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Avance mensual — %s" % self.name,
            "res_model": "produccion.avance.mes",
            "view_mode": "list",
            "domain": [("project_id", "=", self.id)],
            "context": {"default_project_id": self.id},
            "target": "current",
        }

    # ------------------------------------------------------------------
    # Endpoint de datos de la pestaña Seguimiento económico (widget OWL)
    # ------------------------------------------------------------------
    def get_produccion_br_data(self, anio=None):
        """Estructura completa para pintar la tabla BR de un proyecto:
        meses, estado (pasado/actual/futuro), avance, costes por tipología,
        PM, %PM, %PM acumulado, facturación y WIP. Una cifra por celda:
        Costes: real guardado en pasado, consulta de fuentes hasta hoy en el
        mes actual, previsión en futuro. El ingreso actual sigue siendo previsto.
        """
        self.ensure_one()
        project = self.with_company(self.company_id)
        # El TCV de la ficha manda: si ha cambiado desde el último reparto, se
        # rehace antes de pintar (tolerante: si no cabe, deja aviso visible).
        project._sincronizar_tcv()
        motor = project.env["produccion.real.motor"]
        hoy = fields.Date.context_today(self)
        mes_actual = hoy.strftime("%Y-%m")

        try:
            meses = project._meses_planificacion() or []
        except UserError:
            meses = []  # sin fechas en la ficha: la pestaña enseña el aviso, no un error
        if anio:
            meses = [m for m in meses if m.year == anio]
        claves = [m.strftime("%Y-%m") for m in meses]

        # El mes abierto debe reflejar nuevas imputaciones aunque todavía no
        # haya pasado el cron ni se haya pulsado «Recalcular datos reales».
        # Esta lectura de costes no confirma avances ni modifica el histórico,
        # las previsiones o la marca del último recálculo completo.
        reales_actuales = (
            motor._costes_por_periodo(project, hoy.replace(day=1), hoy)
            if mes_actual in claves else {}
        )

        lineas = {
            (l.fecha_mes.strftime("%Y-%m"), l.concepto): l
            for l in project.produccion_linea_ids
        }
        avances = {
            a.fecha_mes.strftime("%Y-%m"): a for a in project.produccion_avance_ids
        }
        facturacion = motor.facturacion_por_mes(project)

        def estado_mes(clave):
            """Un mes solo está CERRADO cuando ya ha terminado. El mes en curso
            se trata como abierto: su ingreso es todavía la previsión
            (criterio de Laura, 13/08/2026)."""
            if clave < mes_actual:
                return "pasado"
            if clave == mes_actual:
                return "actual"
            return "futuro"

        def mes_cerrado(clave):
            return clave < mes_actual

        def celda(clave, concepto):
            l = lineas.get((clave, concepto))
            previsto = l.importe_previsto if l else 0.0
            real = l.importe_real if l else 0.0
            if clave == mes_actual:
                real = reales_actuales.get((clave, concepto), 0.0)
            usar_real = estado_mes(clave) != "futuro"
            return {
                "valor": real if usar_real else previsto,
                "previsto": previsto,
                "real": real,
                "desviacion": (real - previsto) if usar_real else 0.0,
            }

        filas_coste = []
        for concepto in ORDEN_COSTES_BR:
            filas_coste.append(
                {
                    "concepto": concepto,
                    "etiqueta": ETIQUETAS_COSTE_BR.get(concepto, concepto),
                    "celdas": {c: celda(c, concepto) for c in claves},
                }
            )

        fila_avance = {}
        for c in claves:
            a = avances.get(c)
            l = lineas.get((c, "ingreso"))
            previsto = l.importe_previsto if l else 0.0
            # Solo los meses YA CERRADOS muestran el ingreso congelado; el mes en
            # curso y los futuros muestran la previsión vigente.
            if not mes_cerrado(c) or not a:
                valor = previsto
                confirmado = False
            else:
                valor = a.importe_confirmado
                confirmado = a.estado == "confirmado"
            fila_avance[c] = {
                "valor": valor,
                "previsto": previsto,
                "sugerido_lineal": a.importe_sugerido_lineal if a else 0.0,
                "confirmado": confirmado,
                "desviacion": (valor - previsto) if mes_cerrado(c) else 0.0,
            }

        # PM / %PM / %PM acumulado / WIP
        pm, pct_pm, pct_pm_acum, fila_fact, fila_wip = {}, {}, {}, {}, {}
        avance_acum = coste_acum = fact_acum = 0.0
        for c in claves:
            av = fila_avance[c]["valor"]
            cos = sum(f["celdas"][c]["valor"] for f in filas_coste)
            fac = facturacion.get(c, 0.0)
            avance_acum += av
            coste_acum += cos
            fact_acum += fac
            pm[c] = av + cos  # costes en negativo
            pct_pm[c] = (pm[c] / av * 100.0) if av else 0.0
            pct_pm_acum[c] = (
                ((avance_acum + coste_acum) / avance_acum * 100.0)
                if avance_acum
                else 0.0
            )
            fila_fact[c] = fac
            fila_wip[c] = avance_acum - fact_acum

        cuenta = motor._cuenta_analitica(project)
        # Opción A (Laura, 18/08/2026): avisar de entregas desde almacén con
        # proyecto de productos ya comprados contra el proyecto (posible doble
        # coste). No altera cifras.
        duplicados = []
        if meses:
            for d in motor.posibles_duplicados_almacen(project, meses[0], meses[-1] + relativedelta(day=31)):
                duplicados.append({
                    "fecha": fields.Date.to_string(d["fecha"]),
                    "albaran": d["albaran"], "picking_id": d["picking_id"],
                    "move_id": d["move_id"],
                    "producto": d["producto"], "cantidad": d["cantidad"],
                    "importe": d["importe"], "pedidos": d["pedidos"],
                    "comprado": d["comprado"],
                })
        return {
            "proyecto": project.name,
            "posibles_duplicados": duplicados,
            "analytic_id": cuenta.id if cuenta else False,
            "solo_horas_validadas": motor.horas_requieren_validacion(),
            "tcv": project.tcv_efectivo,
            "tcv_fuente": project.tcv_fuente,
            "tcv_alerta": project.produccion_tcv_alerta or False,
            "tipo_proyecto": dict(project._fields["tipo_produccion"].selection).get(
                project.tipo_produccion, "") if project.tipo_produccion else "",
            "fecha_inicio": fields.Date.to_string(project.produccion_fecha_inicio)
            if project.produccion_fecha_inicio else False,
            "fecha_fin": fields.Date.to_string(project.produccion_fecha_fin)
            if project.produccion_fecha_fin else False,
            # el proyecto puede no tener compañía (compartido): currency_id del
            # proyecto ya resuelve la moneda que toca
            "moneda": project.currency_id.symbol or "",
            "meses": claves,
            "estado_mes": {c: estado_mes(c) for c in claves},
            "costes_actuales_hasta": fields.Date.to_string(hoy)
            if mes_actual in claves else False,
            "dominio_fechas_actual_datetime": [
                (campo, operador, fields.Datetime.to_string(valor))
                for campo, operador, valor in motor._dominio_fechas_datetime(
                    "date", hoy.replace(day=1), hoy)
            ] if mes_actual in claves else [],
            "avance": fila_avance,
            "costes": filas_coste,
            "pm": pm,
            "pct_pm": pct_pm,
            "pct_pm_acum": pct_pm_acum,
            "facturacion": fila_fact,
            "wip": fila_wip,
            "last_update": fields.Datetime.to_string(
                project.produccion_real_last_update
            )
            if project.produccion_real_last_update
            else False,
            "stale": project.produccion_real_stale,
        }
