# AUNNA WIP - Enlace de proyecto analítico

Normaliza los apuntes analíticos que Odoo genera para los asientos de **ingreso
reconocido WIP** (cuenta 705), para que queden bien imputados a la analítica del proyecto
y **sin comportarse como partes de horas**.

## Qué resuelve

Los asientos WIP llevan distribución analítica y aparecen en PyG, pero las líneas
analíticas que Odoo genera desde ellos pueden quedar mal: sin importe (`0,00`), con la
distribución al `0%`, o sin quedar bien asociadas al proyecto en la analítica.

> **Cambio jul-2026 (Opción B).** Antes el módulo rellenaba el `project_id` estándar en
> esas líneas para poder agruparlas por proyecto en *Apuntes analíticos*. Pero en Odoo
> **cualquier apunte con `project_id` se trata como parte de horas**, así que esas líneas
> "WIP…" aparecían en el tablero del proyecto, en Rentabilidad y en las listas de partes,
> **contando incluso como horas**. Por eso, **desde `19.0.3.0.0` el módulo YA NO pone el
> `project_id` estándar** (y lo retira de las existentes vía migración). El vínculo con el
> proyecto se conserva por la **cuenta analítica** (1:1 con el proyecto) y por el campo
> propio `aunna_wip_project_id`. En *Apuntes analíticos* se agrupan por **cuenta
> analítica** en vez de por proyecto. El informe operativo financiero y los asientos de
> coste **no** se ven afectados (verificado).

## Cómo funciona

Al crear/publicar el asiento WIP (y al reparar asientos existentes), sobre las líneas
analíticas de ingreso reconocido:

- **Etiqueta** cada línea con su línea de cálculo WIP (`aunna_wip_calculation_line_id`) y
  su proyecto de origen (`aunna_wip_project_id`, campo propio).
- **Normaliza la distribución analítica**: si estuviera al `0%`, la deja al `100%` en la
  cuenta analítica del cálculo. Si ya es correcta, no la reescribe (evita disparar en
  vano el mecanismo nativo, que borra y recrea el apunte).
- **Reconstruye el importe** si el apunte se había generado a `0,00`, usando el importe
  real del debe/haber de la línea contable.
- **(Opción B) Retira el `project_id` estándar** y pone las horas (`unit_amount`) a 0 (y
  desmarca `validated` si viniera puesto), para que la línea deje de ser parte de horas.

**No cambia importes ni cuentas contables** (debe/haber/saldo intactos).

## Reparación de asientos existentes

- **Migración `19.0.3.0.0`**: al actualizar, reprocesa los asientos WIP existentes para
  retirarles el `project_id` (reutiliza la reparación idempotente del módulo).
- **Manual**: abrir el cálculo WIP desde `Cálculos` y entrar con `Abrir asiento` vuelve a
  normalizar y reconstruir el apunte si estaba a cero.

## Cómo probar

1. Calcular el avance/WIP de un presupuesto con proyecto y crear el asiento.
2. En **Contabilidad > Apuntes analíticos**, agrupar por **cuenta analítica**: las líneas
   WIP aparecen bajo la cuenta del proyecto, con su importe (no a `0,00` ni al `0%`).
3. En **Partes de horas** y en el **tablero del proyecto**: las líneas "WIP…" **NO**
   aparecen (ya no son partes de horas) y no suman horas.

## Notas y dependencias

- **Depende de:** `aunna_wip_accounting`, `project`.
- Tras la Opción B, `zambudio_wip_hide_timesheets` deja de ser imprescindible (ya no hay
  líneas WIP con `project_id` que ocultar), pero puede mantenerse como red de seguridad.
- Historial completo de la incidencia de distribución analítica WIP:
  `docs/INCIDENCIA_DISTRIBUCION_ANALITICA_WIP.md`.
