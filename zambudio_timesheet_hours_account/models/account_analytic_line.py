# -*- coding: utf-8 -*-
"""Asignacion de cuenta analitica de horas (internas/externas) por tipo de empleado.

Sustituye dos automatizaciones de Odoo Studio (on_create_or_write) sobre
account.analytic.line. La logica se implementa como override de create/write,
sin base.automation ni ir.actions.server.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# --- Constantes de nombre (NUNCA ids de BD). Confirmar todas con negocio. ---
# Nombres de las cuentas analiticas destino.
ACCOUNT_INTERNAL_NAME = "Horas internas"
ACCOUNT_EXTERNAL_NAME = "Horas externas"
# Nombre (x_name) del registro del maestro x_tipo_empleado.
EMP_TYPE_INTERNAL_NAME = "Interno"   # tipo interno (id 1 en Studio)
EMP_TYPE_EXTERNAL_NAME = "Externo"   # tipo externo (id 2 en Studio)
# Nombre (x_name) del registro del maestro x_subtipo_empleado.
EMP_SUBTYPE_GZ_NAME = "Subco GZ"     # subtipo (id 3 en Studio)

# Campos que provienen de Studio; su presencia debe comprobarse siempre.
_FIELD_EMP_TYPE = "x_studio_tipo_empleado_1"
_FIELD_EMP_SUBTYPE = "x_subtipo_empleado"
_FIELD_AUTO_ACCOUNT = "auto_account_id"

# Bandera de contexto propia para evitar reprocesar (recursion).
_CTX_FLAG = "skip_zambudio_hours"


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Crea los apuntes y aplica la clasificacion de horas."""
        records = super().create(vals_list)
        if not self.env.context.get(_CTX_FLAG):
            records._zambudio_apply_hours_account()
        return records

    def write(self, vals):
        """Escribe los apuntes y aplica la clasificacion de horas."""
        res = super().write(vals)
        if not self.env.context.get(_CTX_FLAG):
            self._zambudio_apply_hours_account()
        return res

    # ------------------------------------------------------------------
    # Helper privado
    # ------------------------------------------------------------------
    def _zambudio_apply_hours_account(self):
        """Asigna auto_account_id a la cuenta de horas internas/externas.

        Nunca lanza excepciones: este modulo alimenta el informe operativo
        financiero y no debe romper el create/write de apuntes. Ante cualquier
        campo Studio ausente o error, se salta silenciosamente.
        """
        # Guarda: si el campo destino no existe aun (fase transitoria Studio),
        # no hay nada que hacer.
        if _FIELD_AUTO_ACCOUNT not in self._fields:
            return
        # Guarda: sin el campo de tipo de empleado no podemos clasificar.
        if _FIELD_EMP_TYPE not in self._fields:
            return

        AnalyticAccount = self.env["account.analytic.account"]

        for line in self:
            try:
                # Solo se procesan apuntes ligados a un proyecto.
                if not line.project_id:
                    continue

                # Cuenta destino segun el tipo (y subtipo) de empleado.
                account_name = line._zambudio_target_account_name()
                if not account_name:
                    continue

                # Compania: la del apunte o, en su defecto, la del empleado.
                company = line.company_id or line.employee_id.company_id
                if not company:
                    continue

                account = AnalyticAccount.search(
                    [
                        ("name", "=", account_name),
                        ("company_id", "=", company.id),
                    ],
                    limit=1,
                )
                if not account:
                    continue

                # Eficiencia: escribir solo si el valor cambia de verdad.
                current = line[_FIELD_AUTO_ACCOUNT]
                if current and current.id == account.id:
                    continue

                # Reescritura con la bandera de contexto para evitar recursion.
                line.with_context(**{_CTX_FLAG: True}).write(
                    {_FIELD_AUTO_ACCOUNT: account.id}
                )
            except Exception:  # noqa: BLE001 - nunca romper create/write.
                _logger.exception(
                    "zambudio_timesheet_hours_account: fallo al clasificar "
                    "el apunte analitico id=%s; se omite.",
                    line.id,
                )
                continue

    def _zambudio_target_account_name(self):
        """Devuelve el nombre de cuenta destino o False si no clasifica.

        - Interno                      -> ACCOUNT_INTERNAL_NAME
        - Externo + subtipo 'Subco GZ' -> ACCOUNT_EXTERNAL_NAME
        - Cualquier otro caso          -> False (no se toca auto_account_id)
        """
        self.ensure_one()

        emp_type = self[_FIELD_EMP_TYPE]
        if not emp_type:
            return False

        type_name = self._zambudio_master_name(emp_type)

        # Horas internas.
        if type_name == EMP_TYPE_INTERNAL_NAME.strip().lower():
            return ACCOUNT_INTERNAL_NAME

        # Horas externas: requiere tipo Externo Y subtipo Subco GZ.
        if type_name == EMP_TYPE_EXTERNAL_NAME.strip().lower():
            # El subtipo puede no existir como campo (fase transitoria Studio).
            if _FIELD_EMP_SUBTYPE not in self._fields:
                return False
            subtype = self[_FIELD_EMP_SUBTYPE]
            if not subtype:
                return False
            subtype_name = self._zambudio_master_name(subtype)
            if subtype_name == EMP_SUBTYPE_GZ_NAME.strip().lower():
                return ACCOUNT_EXTERNAL_NAME

        return False

    @staticmethod
    def _zambudio_master_name(master_record):
        """Nombre normalizado de un registro maestro (x_tipo/x_subtipo_empleado).

        El maestro usa x_name como nombre; si no, se recurre a display_name.
        Se lee en idioma neutro (en_US) para que la comparacion no dependa del
        idioma del usuario, y se compara en minusculas sin espacios extremos.
        """
        rec = master_record.with_context(lang="en_US")
        name = False
        # Acceso defensivo: x_name puede no existir en el maestro.
        if "x_name" in rec._fields:
            name = rec.x_name
        if not name:
            name = rec.display_name
        if not name:
            return ""
        return name.strip().lower()
