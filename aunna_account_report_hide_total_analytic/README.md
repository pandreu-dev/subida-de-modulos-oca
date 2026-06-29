# AUNNA Account Report Hide Total Analytic - Analisis

## Objetivo

Ocultar la columna `Total` del informe de Perdidas y Ganancias cuando el usuario aplica filtro analitico/proyecto.

## Decision tras revision

No se deja codigo activo en esta version.

El motivo es que el motor de `account_reports` de Odoo Enterprise cambia bastante entre versiones y un override generico de `account.report` podria afectar a pantalla, PDF, XLSX u otros informes.

La carpeta queda como documentacion para no romper produccion. Si se confirma que no hay opcion estandar, el desarrollo debe hacerse revisando el codigo real de `account_reports` instalado en la BD objetivo.

## Pruebas

1. Abrir PyG sin filtro analitico: debe verse estandar.
2. Abrir PyG con filtro analitico/proyecto: no debe verse columna `Total`.
3. Probar comparacion de periodos.
4. Probar PDF/XLSX y confirmar si debe ocultarse tambien fuera de pantalla.

