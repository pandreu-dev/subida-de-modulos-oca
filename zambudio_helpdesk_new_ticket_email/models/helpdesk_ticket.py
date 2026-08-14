# -*- coding: utf-8 -*-
"""Aviso por correo al crear una incidencia (helpdesk.ticket).

Sustituye la automatizacion de Studio "Aviso de nueva incidencia": al crear un
ticket, envia un correo a un listado fijo de personas usando una plantilla.
(La parte de "crear una actividad" era una prueba y NO se migra.)
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Plantilla de correo (definida en data/mail_template.xml).
_TEMPLATE_XMLID = "zambudio_helpdesk_new_ticket_email.mail_template_new_ticket_notice"

# Equipos para los que se envia el aviso, por NOMBRE. Vacio () = TODOS los equipos.
# El original de Studio filtraba por el equipo con id 1; si quereis restringir a un
# equipo concreto, poned aqui su nombre exacto, p.ej. ("Soporte",).
NOTICE_TEAM_NAMES = ()

# Bandera de contexto para poder desactivar el envio (imports, procesos automaticos).
_CTX_SKIP = "zambudio_no_ticket_notice"


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        if not self.env.context.get(_CTX_SKIP):
            tickets._zambudio_send_new_ticket_notice()
        return tickets

    def _zambudio_send_new_ticket_notice(self):
        """Envia el correo de aviso por cada ticket nuevo que aplique.

        Nunca lanza excepciones: un fallo de correo no debe impedir crear el ticket.
        """
        template = self.env.ref(_TEMPLATE_XMLID, raise_if_not_found=False)
        if not template:
            return
        for ticket in self:
            try:
                # Filtro por equipo (si se ha configurado alguno).
                if NOTICE_TEAM_NAMES:
                    team_name = (ticket.team_id.name or "").strip()
                    if team_name not in NOTICE_TEAM_NAMES:
                        continue
                # force_send=False: se encola y lo envia el cron de correo
                # (no bloquea la creacion del ticket).
                template.send_mail(ticket.id, force_send=False)
            except Exception:  # noqa: BLE001 - nunca romper la creacion del ticket.
                _logger.exception(
                    "zambudio_helpdesk_new_ticket_email: no se pudo enviar el aviso "
                    "de nueva incidencia para el ticket %s.",
                    ticket.id,
                )
