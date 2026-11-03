# -*- coding: utf-8 -*-
{'name': 'AUNNA - Seguimiento economico (referencia PRE - BORRAR)',
 'version': '19.0.1.2.2',
 'summary': 'Datos reales (actuals) + seguimiento económico en la ficha del proyecto',
 'description': '\n'
                'Producción REAL + Seguimiento económico\n'
                '=======================================\n'
                'Completa la pestaña «Producción» (previsión) con los datos REALES del proyecto,\n'
                'calculados en vivo desde las fuentes nativas de Odoo:\n'
                '\n'
                '* Horas internas / externas: partes de horas (dimensión analítica P&L).\n'
                '* Compras de bienes: recepción del pedido menos devoluciones (precio del '
                'pedido).\n'
                '  Servicios y facturas sin pedido: factura de proveedor contabilizada.\n'
                '  Material servido desde almacén (albarán con proyecto) y gastos de empleado.\n'
                '* Facturación: facturas de cliente con analítica del proyecto.\n'
                '* Avance (ingreso reconocido): confirmación mensual con doble sugerencia\n'
                '  (previsión propia y curva lineal por días).\n'
                '* PM (Rentabilidad), %PM, %PM acumulado y WIP calculados al vuelo.\n'
                '\n'
                'Incluye pestaña «Seguimiento económico» con el código de colores del BR '
                'corporativo\n'
                '(pasado cian / futuro morado / agregados Q-H-FY), recálculo automático diario\n'
                'y mensual, detección de datos obsoletos, y exportación Excel con los colores BR.\n'
                '\n'
                'No modifica la pestaña «Producción» existente ni depende de módulos de terceros\n'
                'más allá de los nativos.\n'
                '    ',
 'author': 'AUNNA IT',
 'website': 'https://aunnait.es',
 'category': 'Services/Project',
 'depends': ['aunna_produccion_borrar', 'hr_timesheet', 'account', 'purchase', 'project'],
 'data': ['security/security.xml',
          'security/ir.model.access.csv',
          'data/cron.xml',
          'views/avance_views.xml',
          'views/purchase_views.xml',
          'views/exportar_views.xml',
          'views/project_views.xml'],
 'assets': {'web.assets_backend': ['aunna_produccion_real_borrar/static/src/br_view/**/*']},
 'installable': False,
 'application': False,
 'license': 'LGPL-3',
 'auto_install': False}
