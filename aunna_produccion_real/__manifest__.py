# -*- coding: utf-8 -*-
{
    "name": "AUNNA - Seguimiento económico (copia de desarrollo)",
    "version": "19.0.1.2.3",
    "summary": "Datos reales (actuals) + seguimiento económico en la ficha del proyecto",
    "description": """
Producción REAL + Seguimiento económico
=======================================
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
(pasado cian / futuro morado / agregados Q-H-FY), recálculo automático diario
y mensual, detección de datos obsoletos, y exportación Excel con los colores BR.

No modifica la pestaña «Producción» existente ni depende de módulos de terceros
más allá de los nativos.
    """,
    "author": "AUNNA IT",
    "website": "https://aunnait.es",
    "category": "Services/Project",
    # Nota: la integración con zambudio_project_tcv (TCV nativo de pedidos de
    # venta) es automática si ese módulo está instalado — el campo tcv_efectivo
    # lo detecta en tiempo de ejecución. No es dependencia dura para poder
    # instalar también en entornos donde aún no esté (p. ej. réplicas).
    "depends": [
        "aunna_produccion",
        "hr_timesheet",
        "account",
        "purchase",
        "project",
    ],
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
            "aunna_produccion_real/static/src/br_view/**/*",
        ],
    },
    "auto_install": False,
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
