# -*- coding: utf-8 -*-
"""Extensión del proyecto: TCV, tipo de producción y generación/cálculo de la cuadrícula."""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from .produccion import CLAVES_COSTE, CONCEPTOS, PERMISO_MESES_CERRADOS  # noqa: F401

TIPOS_PRODUCCION = [
    ("cerrado", "Proyecto cerrado"),
    ("tm", "Tiempo & Materiales"),
    ("recurrente", "Recurrente"),
]

# El «Tipo de proyecto» vive en la ficha del proyecto (módulo
# zambudio_project_type). Aquí solo se traduce a nuestras claves internas para
# no tener que tocar el resto del cálculo. Indicación de Laura (14/08/2026):
# el tipo y las fechas se toman del proyecto, en las pestañas son informativos.
MAPEO_TIPO_PROYECTO = {
    "closed": "cerrado",
    "time_materials": "tm",
    "recurring": "recurrente",
}
MAPEO_TIPO_INVERSO = {v: k for k, v in MAPEO_TIPO_PROYECTO.items()}


class ProjectProject(models.Model):
    _inherit = "project.project"

    # --- datos de cabecera que pide el documento (nombre, tipo y TCV) -----------
    # El TCV oficial vive en la FICHA del proyecto: campo `tcv_amount` (módulo
    # zambudio_project_tcv de la casa). Confirmado por Laura el 18/08/2026. Se lee
    # en tiempo de ejecución (dependencia blanda) para poder instalar también
    # donde ese módulo no esté: entonces —y solo entonces— se usa el TCV manual.
    tcv = fields.Monetary(string="TCV manual", currency_field="currency_id",
                          help="Solo se usa si la ficha del proyecto no tiene TCV "
                               "(campo «TCV» del proyecto vacío o inexistente).")
    tcv_efectivo = fields.Monetary(
        string="TCV", currency_field="currency_id",
        compute="_compute_tcv_efectivo",
        help="Total Contract Value con el que se calcula la producción. Se toma "
             "del TCV de la ficha del proyecto; si la ficha no lo tiene, del TCV "
             "manual de esta pestaña.")
    tcv_fuente = fields.Selection(
        [("ficha", "Ficha del proyecto"), ("manual", "Manual (la ficha no tiene TCV)")],
        string="Fuente del TCV", compute="_compute_tcv_efectivo")
    produccion_tcv_aplicado = fields.Monetary(
        string="TCV aplicado en el último reparto", currency_field="currency_id",
        readonly=True, copy=False,
        help="TCV con el que se repartió el ingreso la última vez. Si el TCV de la "
             "ficha cambia, el reparto se rehace automáticamente.")
    produccion_tcv_alerta = fields.Char(
        string="Aviso de TCV", readonly=True, copy=False,
        help="Se rellena cuando el TCV de la ficha ha bajado por debajo del ingreso "
             "ya planificado y el reparto no se ha podido rehacer solo.")

    @staticmethod
    def _campo_tcv_ficha(model):
        """Nombre del campo TCV de la ficha si existe en esta base (o None)."""
        return "tcv_amount" if "tcv_amount" in model._fields else None

    def _depends_tcv(self):
        campo = ProjectProject._campo_tcv_ficha(self)
        return ["tcv", campo] if campo else ["tcv"]

    @api.depends(_depends_tcv)
    def _compute_tcv_efectivo(self):
        campo = self._campo_tcv_ficha(self)
        for p in self:
            nativo = p[campo] if campo else 0.0
            if nativo:
                p.tcv_efectivo = nativo
                p.tcv_fuente = "ficha"
            else:
                p.tcv_efectivo = p.tcv or 0.0
                p.tcv_fuente = "manual"
    tipo_produccion = fields.Selection(
        TIPOS_PRODUCCION, string="Tipo de proyecto",
        compute="_compute_datos_de_cabecera", store=True, readonly=True,
        help="Se toma del «Tipo de proyecto» de la ficha del proyecto. "
             "Aquí es informativo: determina cómo se calcula el ingreso.")
    produccion_fecha_inicio = fields.Date(
        string="Inicio planificación",
        compute="_compute_datos_de_cabecera", store=True, readonly=True,
        help="Se toma de la «Fecha planificada» del proyecto.")
    produccion_fecha_fin = fields.Date(
        string="Fin planificación",
        compute="_compute_datos_de_cabecera", store=True, readonly=True,
        help="Se toma de la «Fecha planificada» del proyecto.")

    @api.depends("zambudio_project_type", "date_start", "date")
    def _compute_datos_de_cabecera(self):
        """El tipo y el periodo se leen SIEMPRE de la ficha del proyecto."""
        for p in self:
            p.tipo_produccion = MAPEO_TIPO_PROYECTO.get(p.zambudio_project_type)
            p.produccion_fecha_inicio = p.date_start
            p.produccion_fecha_fin = p.date
    produccion_linea_ids = fields.One2many("produccion.plan.linea", "project_id",
                                           string="Planificación de producción")

    # --- KPIs -------------------------------------------------------------------
    produccion_ingreso_total = fields.Monetary(compute="_compute_produccion_kpi",
                                               string="Ingreso planificado")
    produccion_coste_total = fields.Monetary(compute="_compute_produccion_kpi",
                                             string="Coste planificado")
    produccion_margen = fields.Monetary(compute="_compute_produccion_kpi",
                                        string="Margen previsto")
    produccion_margen_pct = fields.Float(compute="_compute_produccion_kpi",
                                         string="% Margen")
    produccion_tcv_restante = fields.Monetary(compute="_compute_produccion_kpi",
                                              string="TCV sin distribuir")

    @api.depends("produccion_linea_ids.importe_previsto", "produccion_linea_ids.concepto",
                 "tcv_efectivo")
    def _compute_produccion_kpi(self):
        for p in self:
            ing = sum(l.importe_previsto for l in p.produccion_linea_ids
                      if l.concepto == "ingreso")
            cos = sum(l.importe_previsto for l in p.produccion_linea_ids
                      if l.concepto != "ingreso")
            p.produccion_ingreso_total = ing
            p.produccion_coste_total = cos
            # Los costes se guardan en NEGATIVO (coherencia con los actuals de
            # Odoo), así que el margen SUMA: PM = Ingresos + Costes.
            p.produccion_margen = ing + cos
            p.produccion_margen_pct = (ing + cos) / ing if ing else 0.0
            p.produccion_tcv_restante = (p.tcv_efectivo or 0.0) - ing

    # --- Regla 2: el ingreso total nunca puede superar el TCV -------------------
    @api.constrains("produccion_linea_ids", "tcv")
    def _check_tcv(self):
        for p in self:
            if not p.tcv_efectivo:
                continue
            ing = sum(l.importe_previsto for l in p.produccion_linea_ids
                      if l.concepto == "ingreso")
            if ing > p.tcv_efectivo + 0.01:
                raise ValidationError(_(
                    "El ingreso total planificado (%(ing).2f) supera el TCV del proyecto "
                    "(%(tcv).2f). El ingreso nunca puede superar el TCV."
                ) % {"ing": ing, "tcv": p.tcv_efectivo})

    # --- El TCV de la ficha manda: si cambia, el reparto se rehace --------------
    def write(self, vals):
        res = super().write(vals)
        campo = self._campo_tcv_ficha(self)
        if "tcv" in vals or (campo and campo in vals):
            # Cambio del TCV manual → reparto estricto (avisa si no cabe).
            # Cambio del TCV de la ficha → reparto tolerante: nunca bloquea la
            # ficha del proyecto; si el ingreso ya planificado no cabe, deja aviso.
            self._sincronizar_tcv(estricto="tcv" in vals and not (campo and campo in vals))
        return res

    def _sincronizar_tcv(self, estricto=False):
        """Rehace el reparto del ingreso de los proyectos cuyo TCV efectivo ha
        cambiado desde el último reparto. Devuelve los proyectos rehechos.

        Sirve tanto para el TCV manual como para el de la ficha, sea este un
        campo normal o calculado (p. ej. desde pedidos de venta): se compara el
        TCV vigente con el aplicado la última vez, así que da igual por qué
        camino haya cambiado. Lo llaman el write, el botón de recalcular, el
        cron diario y la pestaña de seguimiento al abrirse.
        """
        rehechos = self.browse()
        for p in self:
            if not p.produccion_linea_ids:
                continue
            if float_compare(p.tcv_efectivo, p.produccion_tcv_aplicado or 0.0,
                             precision_digits=2) == 0 and not p.produccion_tcv_alerta:
                continue
            if estricto:
                p._recalcular_ingresos()
                rehechos |= p
                continue
            try:
                with self.env.cr.savepoint():
                    p._recalcular_ingresos()
                rehechos |= p
            except ValidationError as e:
                p.sudo().write({"produccion_tcv_alerta": str(e.args[0] if e.args else e)})
        return rehechos

    # --- generación de la cuadrícula -------------------------------------------
    def _meses_planificacion(self):
        """Lista de primeros-de-mes entre inicio y fin (tantos meses como apliquen)."""
        self.ensure_one()
        ini = self.produccion_fecha_inicio or self.date_start
        fin = self.produccion_fecha_fin or self.date
        if not ini or not fin:
            raise UserError(_("Indica las fechas de inicio y fin de la planificación "
                              "en el proyecto «%s».") % self.display_name)
        if fin < ini:
            raise UserError(_("La fecha de fin es anterior a la de inicio."))
        meses, cur = [], ini.replace(day=1)
        tope = fin.replace(day=1)
        while cur <= tope:
            meses.append(cur)
            cur += relativedelta(months=1)
        return meses

    def action_generar_planificacion(self):
        """Crea las líneas que falten (proyecto × mes × concepto). No borra lo existente."""
        Linea = self.env["produccion.plan.linea"]
        for p in self:
            existentes = {(l.fecha_mes, l.concepto) for l in p.produccion_linea_ids}
            nuevas = []
            for mes in p._meses_planificacion():
                for clave, _etq in Linea._conceptos_vigentes():
                    if (mes, clave) not in existentes:
                        nuevas.append({"project_id": p.id, "fecha_mes": mes,
                                       "concepto": clave, "importe_previsto": 0.0})
            if nuevas:
                Linea.with_context(permitir_meses_pasados=PERMISO_MESES_CERRADOS).create(nuevas)
            p._recalcular_ingresos()
        return True

    # --- Sección 5 del documento: los tres cálculos de ingreso ------------------
    def _recalcular_ingresos(self):
        """Calcula el ingreso de los meses NO cerrados según el tipo de proyecto.

        * cerrado    -> por avance de coste
        * recurrente -> TCV / nº de meses
        * T&M        -> manual (no se toca)
        """
        for p in self:
            if p.tipo_produccion == "cerrado":
                p._ingresos_por_avance_coste()
            elif p.tipo_produccion == "recurrente":
                p._ingresos_recurrente()
            # T&M: lo consigna el jefe de proyecto, no se calcula.
            # Revalidación final: el reparto terminado nunca debe superar el TCV.
            tcv = p.tcv_efectivo
            if tcv:
                ing = sum(l.importe_previsto for l in p.produccion_linea_ids
                          if l.concepto == "ingreso")
                if ing > tcv + 0.01:
                    raise ValidationError(_(
                        "El ingreso total planificado (%(ing).2f) supera el TCV del "
                        "proyecto «%(proj)s» (%(tcv).2f). Revisa la planificación "
                        "de ingresos (o el TCV de la ficha)."
                    ) % {"ing": ing, "tcv": tcv, "proj": p.display_name})
            # Memoria del TCV usado: si la ficha cambia, se detecta y se rehace.
            p.sudo().write({"produccion_tcv_aplicado": tcv, "produccion_tcv_alerta": False})

    def _lineas_por_mes(self):
        """{fecha_mes: {concepto: linea}}"""
        self.ensure_one()
        out = {}
        for l in self.produccion_linea_ids:
            out.setdefault(l.fecha_mes, {})[l.concepto] = l
        return out

    def _ingresos_por_avance_coste(self):
        """Proyecto cerrado: el ingreso sigue la proporción del coste.

            % avance(m)        = coste(m) / Σ costes(m .. fin)
            ingreso pendiente  = TCV − Σ ingresos de meses ya cerrados
            ingreso(m)         = % avance(m) × ingreso pendiente(m)

        Se recorre mes a mes: cada mes consume parte del pendiente.
        """
        self.ensure_one()
        por_mes = self._lineas_por_mes()
        # solo los meses que tienen línea de ingreso pueden recibir reparto
        meses = sorted(m for m in por_mes if por_mes[m].get("ingreso"))
        if not meses:
            return
        # Los costes van en negativo: para repartir por avance se usa su magnitud
        coste_mes = {
            m: abs(sum(l.importe_previsto for c, l in por_mes[m].items() if c != "ingreso"))
            for m in meses
        }
        # ingresos ya consolidados en meses cerrados (no se tocan)
        cerrados = [m for m in meses if por_mes[m].get("ingreso") and por_mes[m]["ingreso"].mes_cerrado]
        ingreso_cerrado = sum(por_mes[m]["ingreso"].importe_previsto for m in cerrados)
        pendiente = (self.tcv_efectivo or 0.0) - ingreso_cerrado
        abiertos = [m for m in meses if m not in cerrados]
        for i, m in enumerate(abiertos):
            restantes = abiertos[i:]
            total_coste_restante = sum(coste_mes.get(x, 0.0) for x in restantes)
            if total_coste_restante <= 0 or pendiente <= 0:
                valor = 0.0
            else:
                pct = coste_mes.get(m, 0.0) / total_coste_restante
                valor = pendiente * pct
            linea = por_mes[m].get("ingreso")
            if linea:
                linea.with_context(sin_recalculo=True,
                                   permitir_meses_pasados=PERMISO_MESES_CERRADOS).importe_previsto = valor
            pendiente -= valor

    def _ingresos_recurrente(self):
        """Recurrente: TCV dividido entre el número de meses (cuota).

        Los meses ya cerrados no se tocan. Si lo cargado en meses cerrados (p. ej.
        por la carga inicial) más la cuota de los abiertos superase el TCV, la
        cuota se reduce a lo que queda: (TCV − Σ cerrados) / nº abiertos. Así el
        ingreso nunca supera el TCV. El resto de redondeo va al último mes.
        """
        self.ensure_one()
        por_mes = self._lineas_por_mes()
        meses = sorted(m for m in por_mes if por_mes[m].get("ingreso"))
        if not meses or not self.tcv_efectivo:
            return
        tcv = self.tcv_efectivo
        cerrados = [m for m in meses if por_mes[m]["ingreso"].mes_cerrado]
        abiertos = [m for m in meses if m not in cerrados]
        if not abiertos:
            return
        ya = sum(por_mes[m]["ingreso"].importe_previsto for m in cerrados)
        cuota = min(tcv / len(meses), max(tcv - ya, 0.0) / len(abiertos))
        cuota = round(cuota, 2)
        total_abiertos = min(cuota * len(abiertos), max(tcv - ya, 0.0))
        for i, m in enumerate(abiertos):
            valor = cuota
            if i == len(abiertos) - 1:  # resto de redondeo al último mes
                valor = round(total_abiertos - cuota * (len(abiertos) - 1), 2)
            por_mes[m]["ingreso"].with_context(sin_recalculo=True).importe_previsto = valor

    def action_recalcular_ingresos(self):
        self._recalcular_ingresos()
        return True

    @api.model
    def cron_sincronizar_tcv(self):
        """Cron diario: si el TCV de la ficha ha cambiado (p. ej. un pedido de
        venta nuevo), rehace el reparto del ingreso de ese proyecto."""
        proyectos = self.search([("active", "=", True),
                                 ("produccion_linea_ids", "!=", False)])
        proyectos._sincronizar_tcv()
        return True

    def action_ver_produccion(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Producción · %s") % self.display_name,
            "res_model": "produccion.plan.linea",
            "view_mode": "list,pivot",
            "domain": [("project_id", "=", self.id)],
            "context": {"default_project_id": self.id,
                        "pivot_row_groupby": ["concepto"],
                        "pivot_column_groupby": ["fecha_mes:month"],
                        "pivot_measures": ["importe_previsto"]},
        }
