# Zambudio - Helpdesk: aviso de nueva incidencia

Al **crear un ticket** de helpdesk, envía un **correo de aviso** a un listado de
personas, usando una plantilla. Sustituye la automatización de Odoo Studio
*"Aviso de nueva incidencia"*.

> Nota: la automatización de Studio tenía dos partes; la de **crear una actividad** era
> una **prueba** y NO se migra. Aquí solo va el **envío de correo** (que sí es real).

## Qué hace

- En `helpdesk.ticket`, override de `create`: por cada ticket nuevo, envía el correo.
- El correo (asunto, cuerpo y **destinatarios**) está en la plantilla
  `mail_template_new_ticket_notice` (editable desde la interfaz; se crea con `noupdate`
  para que no se sobrescriba al actualizar el módulo).
- **Destinatarios actuales** (campo `email_to` de la plantilla): `lmoreno`, `vpinar`,
  `jhurtado`, `lmyances`, `ccledesma`, `aarmero` (@aunnait.es).
- Se encola (`force_send=False`) para no bloquear la creación del ticket, y va envuelto
  en `try/except`: un fallo de correo **nunca** impide crear el ticket.

## Configuración

- **Equipos**: por defecto se envía para **todos los equipos**. Para restringir a uno,
  edita la constante `NOTICE_TEAM_NAMES` en `models/helpdesk_ticket.py` con el nombre del
  equipo (el original de Studio filtraba por el equipo id 1).
- **Destinatarios / texto**: editar la plantilla en Ajustes → Técnico → Plantillas de
  correo → *Aviso de nueva incidencia*.

## Dependencias

- `helpdesk`
