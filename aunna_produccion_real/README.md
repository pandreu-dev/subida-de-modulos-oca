# Producción — Seguimiento económico

**Copia de desarrollo `aunna_produccion_real`, versión 19.0.1.2.3.**
El cambio del mes en curso solicitado por Laura está descrito en
[Mes en curso: comportamiento, pruebas e instalación](docs/mes_en_curso.md).
Esta copia conserva los modelos de los módulos `zambudio_produccion*`:
**no instalar ambas familias juntas en la misma base de datos**.

Módulo de AUNNA IT para Odoo 19 (Enterprise/Community). Completa la pestaña
**Producción** (previsión) con los **datos reales** del proyecto y presenta ambos
en una pestaña **Seguimiento económico** con el código de colores del BR corporativo.

## Qué aporta

| Bloque | Contenido |
|---|---|
| **Avance** | Ingreso reconocido mensual, confirmable por el gestor. El sistema sugiere dos valores: la previsión propia del proyecto y la curva lineal por días (presupuesto × días transcurridos ÷ días del periodo). |
| **Costes reales** | Calculados en vivo desde las fuentes nativas: partes de horas **validados** (internas/externas según la dimensión analítica P&L); compras de **bienes** por recepción del pedido menos devoluciones al proveedor (al precio del pedido); **servicios** y facturas sin pedido por factura de proveedor contabilizada (el abono resta; la factura de un bien ya recibido no se cuenta dos veces); gastos de empleado; material servido desde almacén al proyecto (su retorno resta). Clasificación por el «Tipo de coste (producción)» del pedido de compra o de la factura. |
| **PM (Rentabilidad)** | PM = Avance − Costes · %PM · %PM acumulado. |
| **Facturación y WIP** | Facturas de cliente posteadas · WIP = avance acumulado − facturado acumulado. |

## La pestaña Seguimiento económico

- Colores: **cian** = mes pasado (dato real guardado),
  **azul intenso** = mes en curso abierto, **morado** = previsión futura,
  **morado oscuro** = agregados Q / H / FY.
- **Mes en curso:** costes reales desde el día 1 hasta hoy, consultados al cargar
  o pulsar **Actualizar tabla**, e ingreso previsto. No se cierra el mes.
- **Meses futuros:** costes e ingresos previstos. El detalle
  previsto/real/desviación aparece al pasar el ratón. La desviación del coste
  actual compara un acumulado parcial con la previsión del mes completo.
- **Clic en una celda** de coste o facturación → los apuntes de origen.
- Toggle «Ver desviaciones» y filtro por año / periodo completo.
- **Chip de frescura** del plan guardado: informa del último recálculo persistido;
  es independiente de la consulta del mes en curso. Puede seguir ámbar aunque
  los costes actuales ya se hayan refrescado en la tabla.

## Recalculo

- Cron diario (mes en curso + 2 anteriores) y repaso completo el día 1 de cada mes.
- Botón **Recalcular datos reales** en la pestaña (grupo «Producción: confirmar
  avance y recalcular», implícito en Project/Administrator).

## Exportación

Botón **Exportar Excel (formato BR)**: genera el libro con la paleta y estructura
del BR (columnas Ene..FY coloreadas, grupos Avance/Costes/PM/WIP), todo el
periodo o el año filtrado.

## Integraciones automáticas (sin dependencia dura)

- `zambudio_project_tcv`: si está instalado, el TCV es el de la **ficha del
  proyecto** (`tcv_amount`); si no, el campo manual de la pestaña Producción. La
  fuente en uso se muestra siempre. Si el TCV de la ficha cambia, el reparto del
  ingreso se rehace solo (y si no cabe, avisa sin bloquear).
- El Tipo de proyecto (`zambudio_project_type`) y la Fecha planificada
  (`date_start`/`date`) de la ficha mandan sobre las pestañas.
- «Puerta de atrás» controlada (módulo base): asistente de carga inicial /
  corrección de meses cerrados, por grupo y con registro de auditoría.
- Dimensión P&L («Horas internas»/«Horas externas»): si una compañía no la tiene,
  las horas cuentan como internas (comportamiento documentado).

## Instalación

Validar primero en una **base aislada de Odoo 19 sin los módulos originales**.
Se necesitan `aunna_produccion` y sus dependencias; `aunna_produccion_grid` es
opcional para este cambio. Procedimiento y comando de pruebas en
[la documentación del cambio](docs/mes_en_curso.md#instalación-y-validación-pendiente-en-odoo).

No usar desinstalaciones de los originales como procedimiento de migración:
ambas familias comparten modelos/tablas y hace falta una migración específica.

## Verificación

El módulo de origen documentaba que sus fórmulas y fuentes fueron validadas al céntimo contra el sistema anterior
(«Informe operativo financiero») sobre datos reales de producción el 11/08/2026:
facturación, horas internas/externas por dimensión P&L, PM y WIP exactos en
todos los puntos comprobados (2 proyectos, ~20 valores). Esa validación histórica
no equivale a una instalación probada de esta copia. El 30/10/2026 se ejecutaron
las pruebas locales de cálculo/Excel y de la vista OWL descritas en el documento
del cambio; la suite ORM y la instalación completa quedan pendientes.
