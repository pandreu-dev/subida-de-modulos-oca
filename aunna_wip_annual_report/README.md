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
- La `Vista horizontal` se muestra agrupada por secciones (Ingresos / Costes / PM /
  WIP), con colores, al estilo del cuadro de referencia.
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

**Ingresos** (grupo contable **70**, imputado a la analitica del informe). Se alimentan
de los **asientos WIP (ingreso reconocido)**, **NO de las facturas de cliente**:

- **Venta de servicios**: cuentas **705** en asientos que no son factura de cliente.
- **Venta de productos**: resto del grupo **70** (`700...`) en asientos que no son
  factura de cliente.
- **Total ingresos** = servicios + productos = ingreso reconocido via asientos WIP.

**WIP**:

- **Facturacion**: facturas/abonos de cliente (`out_invoice` / `out_refund`) en cuentas
  del grupo 70. Se muestra aparte; no entra en Ingresos.
- **WIP**: acumulado del **ingreso reconocido** (arrastra el saldo anterior al rango).
  Lo mueve el **asiento WIP**; una factura no lo mueve. Queda a 0 al facturar el
  proyecto al 100% (dentro del flujo WIP).

**Costes** (Horas internas, Horas externas, Pedidos, Materiales, Gastos) salen de las
mismas fuentes que el panel de **Rentabilidad** del proyecto. **PM** se calcula a partir
de Ingresos y Costes.

> Historico: la fila **ER/OE** se retiro en `19.0.7.0.0`; en `19.0.8.0.0` se separo
> Venta de servicios / Venta de productos y se retiro **Ingreso reconocido**. En
> `19.0.12.0.0` los **Ingresos** dejaron de incluir las facturas de cliente (solo
> asientos WIP), para que una factura no infle "Venta de productos". Las migraciones
> adaptan los informes ya existentes.

## Notas

El calculo se filtra por la cuenta analitica seleccionada. Si se selecciona un
proyecto, el modulo intenta localizar automaticamente su cuenta analitica.

## Documentacion

- **Manual de usuario** (como usarlo, como conseguir que salgan los datos y por que a
  veces sale 0): [docs/MANUAL_USUARIO.md](docs/MANUAL_USUARIO.md).
- **Guia de calculos** (detalle tecnico de cada dato): [docs/GUIA_CALCULOS.md](docs/GUIA_CALCULOS.md).
