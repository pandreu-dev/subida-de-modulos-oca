# Analisis estandar

No se ha identificado una opcion funcional visible que oculte automaticamente la columna `Total` del PyG.

Se implementa un override acotado a `account.report` para el informe de Perdidas y Ganancias:

- Solo actua si el informe es PyG.
- Solo elimina columnas con encabezado exacto `Total`.
- No modifica importes ni formulas.

Si Odoo cambia la estructura interna de `account_reports`, revisar `models/account_report.py`.
