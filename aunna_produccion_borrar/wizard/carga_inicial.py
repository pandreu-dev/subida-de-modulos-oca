# -*- coding: utf-8 -*-
"""«Puerta de atrás» controlada para meses cerrados (petición de Laura, 18/08/2026).

La regla 3 (no se modifican meses cerrados) protege el día a día. Pero hace
falta una salida controlada para (a) la carga inicial del histórico —los
ingresos a pasado que no vamos a tener de otra forma— y (b) corregir errores.

Este asistente:
  * solo lo puede usar quien tenga el grupo «Producción: carga inicial y
    corrección de meses cerrados» (2-3 personas);
  * exige un motivo;
  * permite cambiar importes de meses cerrados (y abiertos) del proyecto, a
    mano o desde la misma plantilla Excel de la pestaña;
  * deja registro por celda (produccion.plan.ajuste) y una nota en el chatter
    del proyecto;
  * tras aplicar, rehace el reparto del ingreso (los meses cerrados cuentan
    como ingreso ya consumido del TCV) y, si está instalado el seguimiento
    económico, actualiza el avance congelado de esos meses para que la pestaña
    muestre el dato cargado.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..models.produccion import CONCEPTOS, PERMISO_MESES_CERRADOS


class ProduccionCargaInicial(models.TransientModel):
    _name = "produccion.carga.inicial"
    _description = "Carga inicial / corrección de meses cerrados"

    project_id = fields.Many2one("project.project", string="Proyecto", required=True)
    currency_id = fields.Many2one(related="project_id.currency_id")
    motivo = fields.Text(
        string="Motivo", required=True,
        help="Queda registrado junto a cada celda modificada (quién, cuándo, "
             "valor anterior y nuevo).")
    modo = fields.Selection(
        [("manual", "Editar a mano"), ("excel", "Subir plantilla Excel")],
        string="Cómo cargar", default="manual", required=True)
    conceptos = fields.Selection(
        [("ingreso", "Solo INGRESO"), ("todos", "Ingreso y todos los costes")],
        string="Qué conceptos", default="ingreso", required=True,
        help="Por defecto solo el ingreso, que es lo que normalmente falta a "
             "pasado. Elige «todos» para corregir también costes previstos.")
    ambito = fields.Selection(
        [("cerrados", "Solo meses cerrados"), ("todos", "Todos los meses")],
        string="Qué meses", default="cerrados", required=True)
    linea_ids = fields.One2many("produccion.carga.inicial.linea", "wizard_id",
                                string="Celdas")
    fichero = fields.Binary(string="Plantilla Excel rellenada")
    nombre_fichero = fields.Char()
    n_cerrados = fields.Integer(compute="_compute_resumen")
    aviso_tcv = fields.Char(compute="_compute_resumen")

    # ------------------------------------------------------------------ carga de líneas
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        pid = vals.get("project_id") or self.env.context.get("default_project_id")
        if pid and "linea_ids" in fields_list:
            vals["linea_ids"] = self._preparar_lineas(
                self.env["project.project"].browse(pid),
                vals.get("conceptos", "ingreso"), vals.get("ambito", "cerrados"))
        return vals

    @api.model
    def _preparar_lineas(self, project, conceptos, ambito):
        comandos = [(5, 0, 0)]
        automatico = project.tipo_produccion in ("cerrado", "recurrente")
        for l in project.produccion_linea_ids.sorted(lambda x: (x.fecha_mes, x.secuencia)):
            if conceptos == "ingreso" and l.concepto != "ingreso":
                continue
            if ambito == "cerrados" and not l.mes_cerrado:
                continue
            # en proyecto cerrado/recurrente el ingreso de los meses abiertos lo
            # calcula el reparto: cargarlo a mano no serviría (se pisaría)
            if automatico and l.concepto == "ingreso" and not l.mes_cerrado:
                continue
            comandos.append((0, 0, {
                "linea_id": l.id,
                "fecha_mes": l.fecha_mes,
                "concepto": l.concepto,
                "mes_cerrado": l.mes_cerrado,
                "importe_actual": l.importe_previsto,
                "importe_nuevo": l.importe_previsto,
            }))
        return comandos

    @api.onchange("project_id", "conceptos", "ambito")
    def _onchange_filtros(self):
        if self.project_id:
            self.linea_ids = self._preparar_lineas(self.project_id, self.conceptos, self.ambito)

    @api.depends("project_id", "linea_ids.importe_nuevo")
    def _compute_resumen(self):
        for w in self:
            w.n_cerrados = len(set(
                w.project_id.produccion_linea_ids.filtered("mes_cerrado").mapped("fecha_mes")))
            tcv = w.project_id.tcv_efectivo
            aviso = False
            if tcv and w.project_id.produccion_linea_ids:
                nuevos = {l.linea_id.id: l.importe_nuevo for l in w.linea_ids if l.linea_id}
                automatico = w.project_id.tipo_produccion in ("cerrado", "recurrente")
                # T&M: cuenta todo el ingreso planificado. Cerrado/recurrente:
                # los meses abiertos se rehacen al aplicar, así que solo puede
                # sobrar lo cargado en meses cerrados.
                ing = sum(nuevos.get(l.id, l.importe_previsto)
                          for l in w.project_id.produccion_linea_ids
                          if l.concepto == "ingreso" and (not automatico or l.mes_cerrado))
                if ing > tcv + 0.01:
                    aviso = _("Con estos valores el ingreso total (%(ing).2f) superaría el "
                              "TCV (%(tcv).2f): no se podrá aplicar.") % {"ing": ing, "tcv": tcv}
            w.aviso_tcv = aviso

    # ------------------------------------------------------------------ aplicar
    def _comprobar_permiso(self):
        if not self.env.user.has_group("aunna_produccion_borrar.group_produccion_carga_inicial"):
            raise UserError(_("Solo las personas del grupo «Producción: carga inicial y "
                              "corrección de meses cerrados» pueden usar este asistente."))

    def action_aplicar(self):
        self.ensure_one()
        self._comprobar_permiso()
        if not (self.motivo or "").strip():
            raise UserError(_("Indica el motivo: queda registrado en cada cambio."))
        cambios = self._cambios_manual() if self.modo == "manual" else self._cambios_excel()
        if not cambios:
            raise UserError(_("No hay ningún importe distinto del actual: nada que aplicar."))
        return self._aplicar(cambios, origen=self.modo)

    def _cambios_manual(self):
        """[(linea, nuevo)] de las celdas editadas a mano."""
        return [(w.linea_id, w.importe_nuevo) for w in self.linea_ids
                if w.linea_id and abs(w.importe_nuevo - w.linea_id.importe_previsto) > 0.004]

    def _cambios_excel(self):
        if not self.fichero:
            raise UserError(_("Selecciona la plantilla Excel rellenada."))
        valores = self.env["produccion.importar"]._parsear_excel(self.fichero)
        indice = {(l.fecha_mes, l.concepto): l for l in self.project_id.produccion_linea_ids}
        automatico = self.project_id.tipo_produccion in ("cerrado", "recurrente")
        cambios = []
        for (mes, clave), val in valores.items():
            if self.conceptos == "ingreso" and clave != "ingreso":
                continue
            linea = indice.get((mes, clave))
            if not linea:
                continue
            if self.ambito == "cerrados" and not linea.mes_cerrado:
                continue
            if automatico and clave == "ingreso" and not linea.mes_cerrado:
                continue  # lo calcula el reparto
            if abs(val - linea.importe_previsto) > 0.004:
                cambios.append((linea, val))
        return cambios

    def _aplicar(self, cambios, origen):
        Ajuste = self.env["produccion.plan.ajuste"]
        project = self.project_id
        detalle = []  # (linea, anterior, nuevo)
        for linea, nuevo in cambios:
            anterior = linea.importe_previsto
            detalle.append((linea, anterior, nuevo))
            # el permiso ya se ha comprobado (grupo); el testigo levanta la regla 3
            linea.with_context(permitir_meses_pasados=PERMISO_MESES_CERRADOS,
                               sin_recalculo=True).write({"importe_previsto": nuevo})
            Ajuste.create({
                "project_id": project.id,
                "fecha_mes": linea.fecha_mes,
                "concepto": linea.concepto,
                "importe_anterior": anterior,
                "importe_nuevo": nuevo,
                "motivo": self.motivo,
                "origen": origen,
            })
        # Reparto del ingreso con los meses cerrados ya cargados. Si no cabe en
        # el TCV, se aborta TODO (la transacción se deshace) con mensaje claro.
        try:
            project._recalcular_ingresos()
        except ValidationError as e:
            raise UserError(_("No se puede aplicar la carga: %s") % (e.args[0] if e.args else e))
        self._actualizar_avances(project, cambios)
        self._anotar_en_chatter(project, detalle, origen)
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": _("Carga aplicada"),
                       "message": _("%s celda(s) modificadas y registradas.") % len(cambios),
                       "type": "success",
                       "next": {"type": "ir.actions.client", "tag": "soft_reload"}},
        }

    def _actualizar_avances(self, project, cambios):
        """Si está el seguimiento económico: el avance congelado de un mes
        cerrado pasa a ser el ingreso cargado (si no, la pestaña seguiría
        enseñando el valor congelado antiguo)."""
        if "produccion.avance.mes" not in self.env:
            return
        # el permiso ya está comprobado (grupo de carga inicial): el avance se
        # escribe con sudo porque su ACL exige otro grupo (confirmar avance)
        Avance = self.env["produccion.avance.mes"].sudo()
        for linea, nuevo in cambios:
            if linea.concepto != "ingreso" or not linea.mes_cerrado:
                continue
            avance = Avance.search([("project_id", "=", project.id),
                                    ("fecha_mes", "=", linea.fecha_mes)], limit=1)
            vals = {"importe_confirmado": nuevo, "estado": "confirmado",
                    "confirmado_por_id": self.env.user.id,
                    "confirmado_fecha": fields.Datetime.now(),
                    "nota": _("Carga inicial / corrección: %s") % (self.motivo or "")[:120]}
            if avance:
                avance.write(vals)
            else:
                vals.update({"project_id": project.id, "fecha_mes": linea.fecha_mes,
                             "importe_sugerido_prevision": nuevo})
                Avance.create(vals)

    def _anotar_en_chatter(self, project, detalle, origen):
        if not hasattr(project, "message_post"):
            return
        from markupsafe import Markup, escape
        etiquetas = dict(self.env["produccion.plan.linea"]._fields["concepto"].selection)
        filas = "".join(
            "<tr><td>%s</td><td>%s</td><td style='text-align:right'>%.2f</td>"
            "<td style='text-align:right'><b>%.2f</b></td></tr>" % (
                linea.fecha_mes.strftime("%m/%Y"),
                escape(etiquetas.get(linea.concepto, linea.concepto)), anterior, nuevo)
            for linea, anterior, nuevo in detalle)
        cuerpo = Markup(
            "<p><b>Carga inicial / corrección de meses cerrados</b> (%s)<br/>"
            "Motivo: %s</p><table class='table table-sm'><tr><th>Mes</th><th>Concepto</th>"
            "<th>Anterior</th><th>Nuevo</th></tr>%s</table>"
        ) % (Markup("Excel" if origen == "excel" else "manual"), self.motivo or "", Markup(filas))
        project.message_post(body=cuerpo, subtype_xmlid="mail.mt_note")


class ProduccionCargaInicialLinea(models.TransientModel):
    _name = "produccion.carga.inicial.linea"
    _description = "Celda a cargar (asistente de carga inicial)"
    _order = "fecha_mes, id"

    wizard_id = fields.Many2one("produccion.carga.inicial", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    linea_id = fields.Many2one("produccion.plan.linea", string="Línea", readonly=True)
    fecha_mes = fields.Date(string="Mes", readonly=True)
    etiqueta_mes = fields.Char(compute="_compute_etiqueta")
    concepto = fields.Selection(CONCEPTOS, string="Concepto", readonly=True)
    mes_cerrado = fields.Boolean(string="Cerrado", readonly=True)
    importe_actual = fields.Monetary(string="Valor actual", readonly=True)
    importe_nuevo = fields.Monetary(string="Valor nuevo")

    @api.depends("fecha_mes")
    def _compute_etiqueta(self):
        for r in self:
            r.etiqueta_mes = r.fecha_mes.strftime("%m/%Y") if r.fecha_mes else ""
