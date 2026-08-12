{
    "name": "Zambudio - Helpdesk: posicion de Cuenta analitica",
    "summary": "Coloca la cuenta analitica del ticket justo despues de email_cc",
    "version": "19.0.1.0.0",
    "category": "Services/Helpdesk",
    "author": "Zambudio",
    "license": "LGPL-3",
    # La cuenta analitica del ticket (analytic_account_id) la aporta helpdesk_timesheet.
    # Si en tu instancia viene de otro modulo helpdesk, ajustar esta linea.
    "depends": [
        "helpdesk_timesheet",
    ],
    "data": [
        "views/helpdesk_ticket_views.xml",
    ],
    "installable": True,
    "application": False,
}
