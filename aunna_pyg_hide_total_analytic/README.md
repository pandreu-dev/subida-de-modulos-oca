# AUNNA PyG Hide Total Analytic

## Objetivo

Ocultar la columna `Total` del informe de Perdidas y Ganancias.

## Funcionamiento

El modulo hereda `account.report` y, solo para el informe de Perdidas y Ganancias, elimina de la salida cualquier columna cuyo encabezado sea exactamente `Total`.

Aplica siempre en PyG, con o sin filtros analiticos.

No modifica importes ni calculos contables; solo filtra columnas en la respuesta del informe.

## Pruebas

1. Abrir PyG sin filtro analitico: no debe verse columna `Total`.
2. Abrir PyG con filtro analitico/proyecto: no debe verse columna `Total`.
3. Probar comparacion de periodos.
4. Abrir otros informes contables y confirmar que no cambian.
