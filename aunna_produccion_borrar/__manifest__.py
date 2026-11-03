# -*- coding: utf-8 -*-
{'name': 'AUNNA - Produccion (referencia PRE - BORRAR)',
 'version': '1.2.3',
 'summary': 'Planificación mensual de ingresos y costes por proyecto',
 'description': '\n'
                'Proceso de declaración de producción\n'
                '====================================\n'
                'Planificación mensualizada de ingresos y costes de cada proyecto, integrada en '
                'la\n'
                'ficha del proyecto, según las Especificaciones funcionales de AUNNA IT '
                '(23/07/2026).\n'
                '\n'
                '* Planificación inicial y revisión mensual.\n'
                '* Cuadrícula mes × concepto con las 10 tipologías de coste.\n'
                '* Ingresos automáticos: proyecto cerrado (avance de coste) y recurrente '
                '(TCV/meses);\n'
                '  manual en Tiempo & Materiales.\n'
                '* Reglas: mes en curso siempre previsión · ingreso total <= TCV · meses pasados\n'
                '  no modificables · import/export Excel.\n'
                '* TCV, tipo de proyecto y fechas se toman de la FICHA del proyecto (tcv_amount,\n'
                '  zambudio_project_type, Fecha planificada). Si el TCV cambia, el reparto se '
                'rehace.\n'
                '* «Puerta de atrás» controlada: asistente de carga inicial / corrección de meses\n'
                '  cerrados, restringido por grupo y con registro de auditoría por celda.\n',
 'author': 'AUNNA IT',
 'category': 'Services/Project',
 'depends': ['project', 'hr_timesheet', 'analytic', 'zambudio_project_type'],
 'data': ['security/security.xml',
          'security/ir.model.access.csv',
          'data/cron.xml',
          'views/produccion_views.xml',
          'wizard/importar_views.xml',
          'wizard/carga_inicial_views.xml',
          'views/project_views.xml'],
 'post_init_hook': 'post_init_hook',
 'installable': False,
 'application': False,
 'license': 'LGPL-3',
 'auto_install': False}
