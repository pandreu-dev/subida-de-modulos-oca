{
    "name": "Zambudio - Apuntes analiticos: columnas Tarea y Ticket",
    "summary": "Anade Tarea (task_id) y Ticket (helpdesk_ticket_id) al listado de apuntes analiticos",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Zambudio",
    "license": "LGPL-3",
    # task_id lo aporta hr_timesheet; helpdesk_ticket_id lo aporta helpdesk_timesheet.
    # Si en tu instancia el ticket viene de otro modulo helpdesk, ajustar esta linea.
    "depends": [
        "hr_timesheet",
        "helpdesk_timesheet",
    ],
    "data": [
        "views/account_analytic_line_views.xml",
    ],
    "installable": True,
    "application": False,
}
