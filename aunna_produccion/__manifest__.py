# -*- coding: utf-8 -*-
{
    "name": "AUNNA - Producción (copia de desarrollo)",
    "version": "1.2.3",
    "summary": "Planificación mensual de ingresos y costes por proyecto",
    "description": """
Proceso de declaración de producción
====================================
Planificación mensualizada de ingresos y costes de cada proyecto, integrada en la
ficha del proyecto, según las Especificaciones funcionales de AUNNA IT (23/07/2026).

* Planificación inicial y revisión mensual.
* Cuadrícula mes × concepto con las 10 tipologías de coste.
* Ingresos automáticos: proyecto cerrado (avance de coste) y recurrente (TCV/meses);
  manual en Tiempo & Materiales.
* Reglas: mes en curso siempre previsión · ingreso total <= TCV · meses pasados
  no modificables · import/export Excel.
* TCV, tipo de proyecto y fechas se toman de la FICHA del proyecto (tcv_amount,
  zambudio_project_type, Fecha planificada). Si el TCV cambia, el reparto se rehace.
* «Puerta de atrás» controlada: asistente de carga inicial / corrección de meses
  cerrados, restringido por grupo y con registro de auditoría por celda.
""",
    "author": "AUNNA IT",
    "category": "Services/Project",
    # zambudio_project_type aporta el «Tipo de proyecto» de la ficha, que es la
    # fuente del tipo de producción (antes lo duplicábamos en la pestaña).
    "depends": ["project", "hr_timesheet", "analytic", "zambudio_project_type"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/produccion_views.xml",
        "wizard/importar_views.xml",
        "wizard/carga_inicial_views.xml",
        "views/project_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "auto_install": False,
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
