# AUNNA WIP - Informe anual/mensual

Modulo para crear informes WIP por proyecto o cuenta analitica desde
Contabilidad > Informes.

## Funcionamiento

- En `Configuracion informes WIP` el usuario crea un informe indicando rango de
  meses, compania y proyecto o cuenta analitica.
- El boton `Recalcular reales` genera/actualiza el detalle mensual.
- En `Informe WIP mensual` se trabaja en una vista lista operativa, exportable a
  Excel y filtrable como cualquier lista de Odoo.
- En la configuracion del informe tambien hay una pestana `Vista horizontal` con
  una matriz compacta de meses en columnas y conceptos en filas.
- El boton `Exportar Excel` descarga esa matriz horizontal en formato `.xlsx`,
  con cabeceras, primera columna congelada y formato numerico.
- Cada fila representa un mes y un concepto, en este orden: Ingreso reconocido,
  Facturacion y WIP real acumulado.
- La columna `Prev.` es editable por el usuario.
- Las columnas `Real` y `Dif.` se calculan desde Odoo.
- La lista permite ocultar columnas, filtrar por proyecto/cuenta analitica, filtrar
  periodos, ocultar lineas vacias y agrupar por mes, concepto, proyecto o compania.
- Al cambiar el rango de fechas se crean las lineas mensuales necesarias, pero no
  se borran las lineas anteriores. Asi se conservan los importes `Prev.` ya escritos
  aunque el usuario cambie temporalmente el periodo visible.
- La vista lista aplica por defecto el filtro `Rango activo`; si se necesita revisar
  informacion conservada fuera del rango, se puede quitar ese filtro o usar
  `Fuera de rango`.
- En la ficha del informe, `Detalle mensual` y `Vista horizontal` usan el rango
  `Desde` / `Hasta`. Si el informe empieza en febrero, los importes escritos en
  enero se conservan, pero no se muestran dentro de ese informe hasta ampliar el
  rango.
- La vista horizontal es solo visual. La columna de concepto queda fija al desplazar
  horizontalmente, para que se pueda revisar el dato sin perder la referencia de fila.
- Si se modifican importes `Prev.` manualmente en `Detalle mensual`, la matriz
  visual se regenera al guardar el informe o la linea mensual. El boton
  `Actualizar vista horizontal` fuerza la regeneracion para informes existentes.

## Conceptos (filas) y fuentes de datos reales

El orden de filas es: **Ingreso reconocido**, **Facturacion** y **WIP real acumulado**.

- Ingreso reconocido: apuntes publicados contra la cuenta de ingreso WIP configurada
  en la compania (`Configuracion WIP > Cuenta ingreso WIP`), filtrados por la cuenta
  analitica del informe.
- Facturacion: apuntes de ingreso publicados de facturas/abonos de cliente
  (`out_invoice` / `out_refund`) con distribucion analitica hacia la cuenta del
  informe.
- WIP real acumulado: acumulado mensual de `Ingreso reconocido - Facturacion`.
  El primer mes visible arrastra como saldo inicial todo lo anterior al rango para
  que el acumulado no se reinicie artificialmente al filtrar de un mes a otro.

> El concepto ER/OE (pedidos de venta) se retiro a partir de la version 19.0.7.0.0.
> La migracion elimina esa fila de los informes ya existentes.

## Notas

El calculo se filtra por la cuenta analitica seleccionada. Si se selecciona un
proyecto, el modulo intenta localizar automaticamente su cuenta analitica.

Para una explicacion detallada de cada calculo y del contexto del modulo consulta
[docs/GUIA_CALCULOS.md](docs/GUIA_CALCULOS.md).
