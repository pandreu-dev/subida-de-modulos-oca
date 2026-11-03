# -*- coding: utf-8 -*-
{
    "name": "Declaración de producción de proyectos_new_version",
    "version": "19.0.3.0.0",
    "summary": "Planificación mensual de ingresos y costes por proyecto",
    "description": """
Proceso de declaración de producción
====================================
Versión autónoma de la declaración de producción (módulo original
zambudio_produccion): mismo modelo de datos, mismas pantallas y mismas reglas.
No depende del módulo original y NO debe instalarse junto a él en la misma base
(ambos definen los mismos modelos).

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
    # fuente del tipo de producción.
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
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
