# -*- coding: utf-8 -*-
{
    "name": "Zambudio CRM Automations",
    "version": "19.0.1.0.0",
    "summary": "Automatizaciones de crm.lead migradas de Odoo Studio a Python",
    "description": """
Reune en metodos Python (create/write del modelo crm.lead) varias
automatizaciones que antes vivian en Odoo Studio:

1. Sincronizar probabilidad + fase (x_studio_etapa_1) segun la etapa.
2. Ingreso esperado = SoS + COGS.
3. Fecha de cierre = hoy al pasar a Ganado o Perdida.
4. Pasar a Perdido cuando hay motivo de perdida.
5. Fechas de inicio/fin de contrato al guardar.

No usa base.automation ni ir.actions.server: solo overrides de metodos
del modelo con guardas de contexto para evitar recursion.
""",
    "author": "Zambudio",
    "website": "https://www.zambudio.example",
    "category": "Sales/CRM",
    "license": "LGPL-3",
    "depends": [
        "crm",
    ],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
