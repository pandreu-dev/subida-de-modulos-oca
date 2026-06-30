# AUNNA PyG Hide Total Analytic

## Objetivo

Ocultar la columna `Total` del informe de Perdidas y Ganancias.

## Funcionamiento

El modulo carga un asset JavaScript en el backend de Odoo.

Solo en la pantalla del informe de Perdidas y Ganancias, el script revisa la tabla renderizada y elimina visualmente cualquier columna cuyo encabezado sea exactamente `Total`.

Aplica siempre en PyG, con o sin filtros analiticos y con comparativas de periodos.

No modifica importes, apuntes ni calculos contables; solo cambia la visualizacion del informe.

## Pruebas

1. Abrir PyG sin filtro analitico: no debe verse columna `Total`.
2. Abrir PyG con filtro analitico/proyecto: no debe verse columna `Total`.
3. Probar comparacion de periodos.
4. Abrir otros informes contables y confirmar que no cambian.
