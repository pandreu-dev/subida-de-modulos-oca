# -*- coding: utf-8 -*-
"""Automatizaciones de crm.lead migradas de Odoo Studio a Python.

Toda la logica vive en overrides de create/write que delegan en helpers
privados. Cada logica lleva su propia bandera de contexto para evitar
recursion. El acceso a los campos x_studio_* se protege siempre con
`"campo" in self._fields`, porque provienen de Studio y en la fase
transitoria de migracion pueden no existir todavia.
"""

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # ------------------------------------------------------------------
    # Constantes de nombre (referencias por NOMBRE, nunca por id de BD).
    # OJO: confirmar que estos nombres coinciden con los reales en la BD.
    # ------------------------------------------------------------------
    STAGE_WON_NAME = "Ganado"
    STAGE_LOST_NAME = "Perdida"

    # Mapa de porcentaje (texto) -> probabilidad numerica.
    _ZAMBUDIO_PCT_MAP = {
        "0%": 0.0,
        "10%": 10.0,
        "30%": 30.0,
        "60%": 60.0,
        "90%": 90.0,
    }

    # ==================================================================
    # OVERRIDES DE create / write
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Crea los leads y aplica las automatizaciones que aplican en creacion."""
        records = super().create(vals_list)
        # 4) Pasar a perdido si trae motivo de perdida (puede mover de etapa).
        if not self.env.context.get("skip_zambudio_lost"):
            records._zambudio_apply_lost()
        # 3) Fecha de cierre = hoy si el lead se crea ya en Ganado/Perdida
        #    (o si "pasar a perdido" acaba de moverlo a Perdida).
        if not self.env.context.get("skip_zambudio_close"):
            records._zambudio_apply_close()
        # 1) Sincronizar probabilidad + fase segun etapa.
        if not self.env.context.get("skip_zambudio_prob"):
            records._zambudio_apply_prob()
        # 2) Ingreso esperado = SoS + COGS.
        if not self.env.context.get("skip_zambudio_expected"):
            records._zambudio_apply_expected()
        # 5) Fechas de inicio/fin de contrato.
        if not self.env.context.get("skip_zambudio_contract"):
            records._zambudio_apply_contract()
        return records

    def write(self, vals):
        """Escribe y aplica las 5 automatizaciones en orden sensato."""
        res = super().write(vals)
        # 3) Fecha de cierre = hoy si en este write se cambia a Ganado/Perdida.
        if "stage_id" in vals and not self.env.context.get("skip_zambudio_close"):
            self._zambudio_apply_close()
        # 4) Pasar a perdido si tiene motivo de perdida.
        if not self.env.context.get("skip_zambudio_lost"):
            self._zambudio_apply_lost()
        # 1) Sincronizar probabilidad + fase segun etapa.
        if not self.env.context.get("skip_zambudio_prob"):
            self._zambudio_apply_prob()
        # 2) Ingreso esperado = SoS + COGS.
        if not self.env.context.get("skip_zambudio_expected"):
            self._zambudio_apply_expected()
        # 5) Fechas de inicio/fin de contrato.
        if not self.env.context.get("skip_zambudio_contract"):
            self._zambudio_apply_contract()
        return res

    # ==================================================================
    # 1) SINCRONIZAR PROBABILIDAD + FASE (x_studio_etapa_1) SEGUN ETAPA
    # ==================================================================
    def _zambudio_apply_prob(self):
        """Ajusta probability y x_studio_etapa_1 en funcion del nombre de etapa.

        Reproduce exactamente la logica del Studio original. Usa la guarda
        skip_zambudio_prob para no reprocesar al reescribir.
        """
        pct_map = self._ZAMBUDIO_PCT_MAP
        has_etapa_1 = "x_studio_etapa_1" in self._fields
        has_p_ini = "x_studio_probabilidad_inicial" in self._fields
        has_p_ofe = "x_studio_probabilidad_avanzada" in self._fields
        # OJO: el nombre real trae la errata "negociacin" (sin la 'o').
        has_p_neg = "x_studio_probabilidad_negociacin" in self._fields

        for lead in self:
            stage = (lead.stage_id.name or "").strip()

            p_ini = lead.x_studio_probabilidad_inicial if has_p_ini else False
            p_ofe = lead.x_studio_probabilidad_avanzada if has_p_ofe else False
            p_neg = lead.x_studio_probabilidad_negociacin if has_p_neg else False

            vals = {}

            # ---- Fase x_studio_etapa_1 -----------------------------------
            if has_etapa_1 and stage != "Abandonada":
                if stage in ("Sin cualificar", "Cualificada"):
                    tipo = "Prospeccion"
                else:
                    tipo = "Oportunidad"
                if lead.x_studio_etapa_1 != tipo:
                    vals["x_studio_etapa_1"] = tipo

            # ---- Probabilidad por etapa ----------------------------------
            new_prob = None
            if stage in ("Sin cualificar", "Cualificada", "Abandonada", "En preparación"):
                if has_p_ofe and p_ofe != p_ini:
                    vals["x_studio_probabilidad_avanzada"] = p_ini
                if has_p_neg and p_neg is not False:
                    vals["x_studio_probabilidad_negociacin"] = False
                new_prob = pct_map.get(p_ini, 0.0)
            elif stage == "Entregada":
                if has_p_ofe and not p_ofe and p_ini:
                    vals["x_studio_probabilidad_avanzada"] = p_ini
                    p_ofe = p_ini
                if has_p_neg and p_neg is not False:
                    vals["x_studio_probabilidad_negociacin"] = False
                new_prob = pct_map.get(p_ofe or p_ini, 0.0)
            elif stage == "En negociación":
                if has_p_neg and not p_neg:
                    p_neg = p_ofe if p_ofe in ("60%", "90%") else "30%"
                    vals["x_studio_probabilidad_negociacin"] = p_neg
                new_prob = pct_map.get(p_neg, 30.0)
            elif stage in ("Perdida", "Retirada"):
                base = p_neg or p_ofe or p_ini
                new_prob = pct_map.get(base, 0.0)
            elif stage == "Ganado":
                new_prob = 100.0
            else:
                new_prob = pct_map.get(p_ini, 0.0)

            # set probability solo si cambia (y si hay valor calculable).
            if new_prob is not None and lead.probability != new_prob:
                vals["probability"] = new_prob

            if vals:
                lead.with_context(skip_zambudio_prob=True).write(vals)

    # ==================================================================
    # 2) INGRESO ESPERADO = SoS + COGS
    # ==================================================================
    def _zambudio_apply_expected(self):
        """expected_revenue = x_studio_ingresos_sos + x_studio_ingresos_cogs."""
        has_sos = "x_studio_ingresos_sos" in self._fields
        has_cogs = "x_studio_ingresos_cogs" in self._fields
        if not (has_sos or has_cogs):
            return

        for lead in self:
            try:
                sos = float(lead.x_studio_ingresos_sos or 0.0) if has_sos else 0.0
            except (TypeError, ValueError):
                sos = 0.0
            try:
                cogs = float(lead.x_studio_ingresos_cogs or 0.0) if has_cogs else 0.0
            except (TypeError, ValueError):
                cogs = 0.0

            # Si ambos son practicamente cero, no tocamos nada.
            if abs(sos) < 1e-9 and abs(cogs) < 1e-9:
                continue

            total = sos + cogs
            if lead.expected_revenue != total:
                lead.with_context(skip_zambudio_expected=True).write(
                    {"expected_revenue": total}
                )

    # ==================================================================
    # 3) FECHA CIERRE = HOY al pasar a Ganado o Perdida
    # ==================================================================
    def _zambudio_apply_close(self):
        """Pone date_deadline = hoy cuando la etapa nueva es Ganado o Perdida."""
        today = fields.Date.context_today(self)
        won_lost = (self.STAGE_WON_NAME, self.STAGE_LOST_NAME)
        for lead in self:
            stage_name = (lead.stage_id.name or "").strip()
            if stage_name in won_lost and lead.date_deadline != today:
                lead.with_context(skip_zambudio_close=True).write(
                    {"date_deadline": today}
                )

    # ==================================================================
    # 4) PASAR A PERDIDO (dominio lost_reason_id != False)
    # ==================================================================
    def _zambudio_apply_lost(self):
        """Si el lead tiene motivo de perdida, mueve su etapa a la de Perdida."""
        leads_with_reason = self.filtered(lambda l: l.lost_reason_id)
        if not leads_with_reason:
            return

        for lead in leads_with_reason:
            stage_name = (lead.stage_id.name or "").strip()
            if stage_name == self.STAGE_LOST_NAME:
                continue

            # Busca la etapa de Perdida por NOMBRE (multi-compania: filtra
            # por la compania del lead cuando la etapa la tiene informada).
            stage = self._zambudio_find_stage(self.STAGE_LOST_NAME, lead.company_id)
            if stage and lead.stage_id.id != stage.id:
                lead.with_context(skip_zambudio_lost=True).write(
                    {"stage_id": stage.id}
                )

    def _zambudio_find_stage(self, name, company=None):
        """Busca una crm.stage por nombre, respetando multi-compania.

        Las etapas de CRM pueden tener company_id vacio (compartidas) o
        informado. Preferimos una etapa de la compania del lead o compartida.
        """
        Stage = self.env["crm.stage"]
        domain = [("name", "=", name)]
        # crm.stage estandar NO tiene company_id (las etapas son globales, se
        # segmentan por team_id). Solo filtramos por compania si el campo existe,
        # para no romper el search en instalaciones estandar.
        if company and "company_id" in Stage._fields:
            domain += ["|", ("company_id", "=", company.id), ("company_id", "=", False)]
        return Stage.search(domain, limit=1)

    # ==================================================================
    # 5) CONTRATO: inicio / fin al guardar
    # ==================================================================
    def _zambudio_apply_contract(self):
        """Calcula fecha de inicio y fin de contrato a partir del cierre y duracion."""
        has_inicio = "x_studio_fecha_inicio_contrato" in self._fields
        # OJO: erratas de Studio en los nombres ('duracin', sin 'o').
        has_meses = "x_studio_meses_de_duracin" in self._fields
        has_fin = "x_studio_fecha_fin_de_contrato" in self._fields
        if not (has_inicio or has_fin):
            return

        for lead in self:
            vals = {}
            cierre = lead.date_deadline
            inicio = lead.x_studio_fecha_inicio_contrato if has_inicio else False

            # ---- Fecha de inicio: primer dia del mes siguiente al cierre ----
            if cierre:
                inicio_calc = (cierre + relativedelta(months=1)).replace(day=1)
                if has_inicio and (not inicio or inicio <= cierre):
                    if lead.x_studio_fecha_inicio_contrato != inicio_calc:
                        vals["x_studio_fecha_inicio_contrato"] = inicio_calc
                    inicio = inicio_calc

            # ---- Fecha de fin: inicio + duracion (meses) --------------------
            dur = 0
            if has_meses:
                try:
                    dur = int(lead.x_studio_meses_de_duracin or 0)
                except (TypeError, ValueError):
                    dur = 0

            if has_fin and inicio:
                # relativedelta respeta el fin de mes: si el dia no existe en
                # el mes destino, usa el ultimo dia disponible.
                fin = inicio + relativedelta(months=dur)
                if lead.x_studio_fecha_fin_de_contrato != fin:
                    vals["x_studio_fecha_fin_de_contrato"] = fin

            if vals:
                lead.with_context(skip_zambudio_contract=True).write(vals)
