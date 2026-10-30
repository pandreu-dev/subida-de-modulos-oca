{'version': '19.0.2.1.0',
 'author': 'AUNNA IT',
 'category': 'Services/Project',
 'auto_install': False,
 'installable': True,
 'application': False,
 'license': 'LGPL-3',
 'name': 'Producción — Seguimiento económico_new_version',
 'summary': 'Costes reales del mes abierto sobre la planificación existente',
 'description': 'Añade una página y un Excel propios conservando las páginas y cálculos originales. '
                'Comparte planes y avances. El mes en curso muestra costes acumulados hasta hoy '
                'y un color propio.',
 'website': 'https://aunnait.es',
 'depends': ['zambudio_produccion_new_version', 'zambudio_produccion_real'],
 'external_dependencies': {'python': ['openpyxl']},
 'data': ['security/ir.model.access.csv', 'views/exportar_views.xml', 'views/project_views.xml'],
 'assets': {'web.assets_backend': ['zambudio_produccion_real_new_version/static/src/br_view/**/*']}}
