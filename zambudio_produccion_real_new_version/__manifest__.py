{'version': '19.0.2.0.1',
 'author': 'AUNNA IT',
 'category': 'Services/Project',
 'auto_install': False,
 'installable': True,
 'application': False,
 'license': 'LGPL-3',
 'name': 'Producción — Seguimiento económico_new_version',
 'summary': 'Costes reales del mes abierto sobre la planificación existente',
 'description': 'Amplía los módulos originales sin duplicar planes, avances, permisos ni tareas. '
                'El mes en curso muestra costes acumulados hasta hoy, con color propio y '
                'exportación Excel.',
 'website': 'https://aunnait.es',
 'depends': ['zambudio_produccion_new_version', 'zambudio_produccion_real'],
 'external_dependencies': {'python': ['openpyxl']},
 'data': ['views/project_views.xml'],
 'assets': {'web.assets_backend': ['zambudio_produccion_real_new_version/static/src/br_view/**/*']}}
