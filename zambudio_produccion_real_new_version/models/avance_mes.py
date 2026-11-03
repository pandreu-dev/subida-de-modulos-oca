# -*- coding: utf-8 -*-
"""Avance mensual confirmable: el sistema sugiere (previsión propia y curva
lineal por días) y el gestor confirma o ajusta. El importe confirmado es el
«ingreso reconocido» real del mes: alimenta PM y WIP."""
from odoo import api, fields, models


class ProduccionAvanceMes(models.Model):
    _name = "produccion.avance.mes"
    _description = "Avance mensual confirmado (ingreso reconocido)"
    _order = "project_id, fecha_mes"

    project_id = fields.Many2one(
        "project.project", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="project_id.company_id", store=True)
    currency_id = fields.Many2one(related="project_id.currency_id")
    fecha_mes = fields.Date(string="Mes", required=True, help="Primer día del mes.")
    etiqueta_mes = fields.Char(compute="_compute_etiqueta", store=True)

    importe_sugerido_prevision = fields.Monetary(
        string="Sugerido (previsión)",
        readonly=True,
        help="La línea INGRESO prevista de ese mes en la pestaña Producción.",
    )
    importe_sugerido_lineal = fields.Monetary(
        string="Sugerido (curva lineal)",
        readonly=True,
        help="TCV × días transcurridos ÷ días del periodo (reparto por calendario).",
    )
    importe_confirmado = fields.Monetary(
        string="Avance confirmado",
        help="Ingreso reconocido del mes. Por defecto, la previsión propia.",
    )
    estado = fields.Selection(
        [("borrador", "Borrador"), ("confirmado", "Confirmado")],
        default="borrador",
        required=True,
    )
    confirmado_por_id = fields.Many2one("res.users", readonly=True)
    confirmado_fecha = fields.Datetime(readonly=True)
    nota = fields.Char(string="Nota del ajuste")

    _avance_unico = models.Constraint(
        "unique(project_id, fecha_mes)",
        "Ya existe un avance para ese proyecto y mes.",
    )

    @api.depends("fecha_mes")
    def _compute_etiqueta(self):
        for rec in self:
            rec.etiqueta_mes = (
                rec.fecha_mes.strftime("%m/%Y") if rec.fecha_mes else False
            )

    def action_confirmar(self):
        for rec in self:
            rec.write(
                {
                    "estado": "confirmado",
                    "confirmado_por_id": self.env.user.id,
                    "confirmado_fecha": fields.Datetime.now(),
                }
            )
        return True

    def action_volver_borrador(self):
        self.write(
            {"estado": "borrador", "confirmado_por_id": False, "confirmado_fecha": False}
        )
        return True

    @api.model
    def congelar_meses_cerrados(self, project):
        """Al terminar un mes, su ingreso queda CONGELADO con la última
        previsión que tenía mientras estaba abierto (criterio de Laura,
        13/08/2026). Solo actúa sobre meses ya cerrados y aún en borrador."""
        hoy = fields.Date.context_today(self)
        mes_actual = hoy.replace(day=1)
        previsiones = {
            l.fecha_mes: l.importe_previsto
            for l in project.produccion_linea_ids
            if l.concepto == "ingreso"
        }
        for avance in project.produccion_avance_ids:
            if avance.fecha_mes >= mes_actual or avance.estado == "confirmado":
                continue
            avance.write({
                "importe_confirmado": previsiones.get(avance.fecha_mes, 0.0),
                "estado": "confirmado",
                "confirmado_fecha": fields.Datetime.now(),
                "nota": avance.nota or "Congelado automáticamente al cerrar el mes",
            })

    @api.model
    def sincronizar_proyecto(self, project):
        """Crea/actualiza los borradores de avance para cada mes planificado.
        Nunca pisa un mes ya confirmado."""
        meses = project._meses_planificacion()
        if not meses:
            return
        existentes = {a.fecha_mes: a for a in project.produccion_avance_ids}
        lineas_ing = {
            l.fecha_mes: l.importe_previsto
            for l in project.produccion_linea_ids
            if l.concepto == "ingreso"
        }
        tcv = project.tcv_efectivo
        d_ini, d_fin = meses[0], self._fin_de_mes(meses[-1])
        dias_total = max((d_fin - d_ini).days + 1, 1)
        acumulado_prev = 0.0
        for mes in meses:
            fin_mes = min(self._fin_de_mes(mes), d_fin)
            dias_hasta = (fin_mes - d_ini).days + 1
            lineal_acum = tcv * dias_hasta / dias_total
            lineal_mes = lineal_acum - acumulado_prev
            acumulado_prev = lineal_acum
            valores = {
                "importe_sugerido_prevision": lineas_ing.get(mes, 0.0),
                "importe_sugerido_lineal": lineal_mes,
            }
            avance = existentes.get(mes)
            if avance:
                if avance.estado == "borrador":
                    valores["importe_confirmado"] = valores[
                        "importe_sugerido_prevision"
                    ]
                    avance.write(valores)
                else:
                    avance.write(
                        {
                            k: v
                            for k, v in valores.items()
                            if k.startswith("importe_sugerido")
                        }
                    )
            else:
                valores.update(
                    {
                        "project_id": project.id,
                        "fecha_mes": mes,
                        "importe_confirmado": valores["importe_sugerido_prevision"],
                    }
                )
                self.create(valores)

    @staticmethod
    def _fin_de_mes(fecha):
        import calendar

        return fecha.replace(day=calendar.monthrange(fecha.year, fecha.month)[1])
