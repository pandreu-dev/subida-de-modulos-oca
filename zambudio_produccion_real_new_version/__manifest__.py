# -*- coding: utf-8 -*-
{
    "name": "Producción — Seguimiento económico_new_version",
    "version": "19.0.3.0.0",
    "summary": "Datos reales (actuals) + seguimiento económico en la ficha del proyecto",
    "description": """
Producción REAL + Seguimiento económico
=======================================
Versión autónoma del seguimiento económico (módulo original
zambudio_produccion_real) con el mes en curso abierto: sus costes reales se
consultan hasta hoy al abrir o actualizar la tabla y se pintan en azul intenso.
No depende del módulo original y NO debe instalarse junto a él en la misma base
(ambos definen los mismos modelos).

Completa la pestaña «Producción» (previsión) con los datos REALES del proyecto,
calculados en vivo desde las fuentes nativas de Odoo:

* Horas internas / externas: partes de horas (dimensión analítica P&L).
* Compras de bienes: recepción del pedido menos devoluciones (precio del pedido).
  Servicios y facturas sin pedido: factura de proveedor contabilizada.
  Material servido desde almacén (albarán con proyecto) y gastos de empleado.
* Facturación: facturas de cliente con analítica del proyecto.
* Avance (ingreso reconocido): confirmación mensual con doble sugerencia
  (previsión propia y curva lineal por días).
* PM (Rentabilidad), %PM, %PM acumulado y WIP calculados al vuelo.

Incluye pestaña «Seguimiento económico» con el código de colores del BR corporativo
(pasado cian / mes en curso azul intenso / futuro morado / agregados Q-H-FY),
recálculo automático diario, detección de datos obsoletos y exportación Excel
con los mismos colores.
    """,
    "author": "AUNNA IT",
    "website": "https://aunnait.es",
    "category": "Services/Project",
    # La integración con zambudio_project_tcv (TCV de la ficha) es automática si
    # ese módulo está instalado; no es dependencia dura.
    "depends": [
        "zambudio_produccion_new_version",
        "hr_timesheet",
        "account",
        "purchase",
        "project",
    ],
    "external_dependencies": {"python": ["openpyxl"]},
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/avance_views.xml",
        "views/purchase_views.xml",
        "views/exportar_views.xml",
        "views/project_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "zambudio_produccion_real_new_version/static/src/br_view/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
