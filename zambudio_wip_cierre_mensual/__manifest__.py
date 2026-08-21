{
    "name": "Zambudio - Cierre mensual WIP (ingreso reconocido)",
    "summary": "El responsable de contabilidad cierra un mes y genera un asiento de "
    "ingreso reconocido (WIP) por proyecto desde el avance confirmado, con reversion al dia 1",
    "version": "19.0.1.0.1",
    "category": "Accounting/Accounting",
    "author": "Zambudio",
    "license": "LGPL-3",
    "depends": [
        # App de produccion de Veronica: define produccion.avance.mes (importe_confirmado).
        # Arrastra zambudio_produccion (produccion.plan.linea). NO depender de
        # zambudio_produccion_grid (se auto-instala, es solo la vista cuadricula).
        "zambudio_produccion_real",
        # Reutilizamos su motor de asiento WIP (ajustes contables + lineas + reversion).
        "aunna_wip_accounting",
        "account",
        "project",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/wip_month_close_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
