# -*- coding: utf-8 -*-
"""Extensión del wizard de plantilla: al exportar, añade una hoja «Datos reales»
con los actuals de los meses pasados. El import del módulo base lee solo la
primera hoja, así que la plantilla sigue siendo reimportable sin cambios."""
import base64
import io

from odoo import fields, models

from odoo.addons.aunna_produccion.models.produccion import CONCEPTOS


class ProduccionImportarExt(models.TransientModel):
    _inherit = "produccion.importar"

    def action_exportar(self):
        accion = super().action_exportar()
        if not self.plantilla:
            return accion
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            return accion

        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(self.plantilla)))
        p = self.project_id
        lineas = p.produccion_linea_ids
        meses = sorted({l.fecha_mes for l in lineas})
        if not meses:
            return accion

        hoy = fields.Date.context_today(self)
        mes_actual = hoy.replace(day=1)
        ws = wb.create_sheet("Datos reales")
        negrita = Font(bold=True)
        ws.cell(row=1, column=1, value="DATOS REALES (solo lectura — esta hoja "
                "no se importa)").font = negrita
        ws.cell(row=2, column=1, value="Cifras en €. Meses pasados y en curso: "
                "coste/ingreso real registrado. Horas: solo las validadas.")
        fila0 = 4
        ws.cell(row=fila0, column=1, value="Concepto").font = negrita
        for j, m in enumerate(meses):
            c = ws.cell(row=fila0, column=2 + j, value=m.strftime("%m/%Y"))
            c.font = negrita
            if m < mes_actual:
                c.fill = PatternFill("solid", fgColor="6DD9FF")
            elif m == mes_actual:
                c.fill = PatternFill("solid", fgColor="4BD0FF")
            else:
                c.fill = PatternFill("solid", fgColor="BD92DE")
        indice = {(l.fecha_mes, l.concepto): l for l in lineas}
        conceptos = list(CONCEPTOS)
        if not any(k == "licencias_software" for k, _v in conceptos):
            conceptos.append(("licencias_software", "Licencias software"))
        for i, (clave, etiqueta) in enumerate(conceptos):
            fila = fila0 + 1 + i
            ws.cell(row=fila, column=1, value=etiqueta)
            for j, m in enumerate(meses):
                l = indice.get((m, clave))
                celda = ws.cell(row=fila, column=2 + j,
                                value=l.importe_real if l else 0.0)
                celda.number_format = "#,##0.00"
        ws.column_dimensions["A"].width = 30

        buf = io.BytesIO()
        wb.save(buf)
        self.plantilla = base64.b64encode(buf.getvalue())
        return accion
