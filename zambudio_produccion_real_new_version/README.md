# Producción — Seguimiento económico

**Ampliación `zambudio_produccion_real_new_version`, versión 19.0.2.1.0.**
El cambio del mes en curso solicitado por Laura está descrito en
[Mes en curso: comportamiento, pruebas e instalación](docs/mes_en_curso.md).
Esta versión depende de los módulos originales `zambudio_produccion` y
`zambudio_produccion_real` y amplía sus modelos mediante herencia. Reutiliza
los proyectos, planes, avances, permisos y tareas existentes. Añade las páginas
**Producción (new_version)** y **Seguimiento económico (new_version)**.
Las dos páginas originales permanecen con sus widgets y cálculos originales.
La planificación es compartida: editar previsiones, confirmar avances o recalcular
los datos guardados desde cualquiera de las páginas afecta al mismo proyecto.
El cambio exclusivo de la consulta nueva es mostrar los costes actuales hasta
hoy en una columna azul intenso, también en su Excel independiente.

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

- Se conservan el cron y el botón **Recalcular datos reales** originales,
  con sus permisos, sin añadir otra tarea ni sustituir su motor.
- El coste del mes actual en la página nueva se consulta al abrirla o actualizarla;
  no necesita pulsar el recálculo persistente.
- Sin fechas válidas la página nueva se abre con un aviso. Los botones que
  necesitan fechas no aparecen hasta completarlas. El aviso de la captura de
  PRE se produjo al pulsar el recálculo original sin fechas, no al abrir la página.

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

Los originales deben permanecer instalados. `zambudio_produccion_new_version`
añade la página de planificación; `zambudio_produccion_grid_new_version`
añade a esa página el acceso a la cuadrícula original.
`openpyxl` es necesario para exportar. Detalles y validación en
[la documentación del cambio](docs/mes_en_curso.md#instalación-y-validación-en-odoo).

No desinstalar los originales. Las antiguas carpetas `aunna_produccion*` eran
copias independientes y no forman parte de este procedimiento. Las carpetas
con sufijo `_borrar` siguen siendo referencias no instalables.

## Verificación

La actualización a 19.0.2.1.0 se probó con los nombres actuales en una copia
neutralizada de PRE: 9 pruebas ORM correctas, cuatro páginas y dos consultas
independientes, sin cambios en planes, avances ni proyectos existentes.
También pasaron 10 pruebas locales y la comprobación del widget en navegador.
Ver [detalle de la validación actual](docs/mes_en_curso.md).

### Validación histórica

El módulo de origen documentaba que sus fórmulas y fuentes fueron validadas al céntimo contra el sistema anterior
(«Informe operativo financiero») sobre datos reales de producción el 11/08/2026:
facturación, horas internas/externas por dimensión P&L, PM y WIP exactos en
todos los puntos comprobados (2 proyectos, ~20 valores). Esa validación histórica
no sustituye las pruebas de esta ampliación. El 30/10/2026 se verificaron nueve
pruebas locales de cálculo/Excel, la vista OWL en navegador y seis pruebas ORM
de la ampliación sobre una copia neutralizada de PRE, conservando sus datos.
La prueba de instalación se realizó antes del cambio de nombre técnico;
las referencias y las pruebas locales se verifican también con `_new_version`.
