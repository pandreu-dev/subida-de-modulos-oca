# Incidencia pendiente: distribucion analitica en asientos WIP

## Modulo

`aunna_wip_project_link_fix`

## Tarea funcional

Ajuste WIP: asientos vinculados a proyecto.

El objetivo es que, al crear un asiento WIP desde un calculo WIP, la linea contable de ingreso WIP tenga distribucion analitica al proyecto/cuenta analitica de la linea del presupuesto.

El resultado esperado es:

- El asiento WIP mantiene sus importes contables correctos.
- La linea de ingreso WIP muestra `Distribucion analitica` con la cuenta analitica del proyecto al 100%.
- No debe aparecer una distribucion al `0%`.
- Los apuntes analiticos generados desde ese asiento no deben quedar a `0,00`.
- Al agrupar los apuntes analiticos por proyecto, el WIP debe aparecer bajo el proyecto correcto y con importe.

## Contexto de modulos implicados

`aunna_wip_budget_calc`

- Calcula el WIP.
- Crea registros en `aunna.wip.calculation`.
- Crea lineas en `aunna.wip.calculation.line`.
- En las lineas se guarda el importe WIP, la cuenta analitica y, cuando se detecta, el proyecto.

`aunna_wip_accounting`

- Crea el asiento WIP y su reversion.
- Usa la configuracion WIP por compania: diario, cuenta de ingreso WIP y cuenta de ingresos anticipados.
- El asiento se genera con importes correctos en debe/haber.

`aunna_wip_project_link_fix`

- Intenta completar el enlace entre las lineas contables WIP, la linea del calculo WIP y el proyecto.
- Intenta normalizar la distribucion analitica para evitar `0%`.
- Intenta reconstruir los apuntes analiticos si quedaron a `0,00`.

## Datos observados en pruebas

Se han probado casos nuevos y antiguos.

Ejemplos revisados durante la incidencia:

- `WIP/2026/06/0004`
- `WIP/2026/07/0010`
- `WIP/2026/07/0011`
- `WIP/2026/07/0013`
- presupuestos/casos de prueba tipo `eje9`, `eje11`
- caso real de referencia: `S00032 - NOKIA SPAIN`

En los calculos WIP se ve que la linea tiene datos correctos:

- cuenta analitica informada, por ejemplo `Interno`;
- proyecto informado, por ejemplo `Interno - CITRIC NETWORKS...`;
- importe WIP a contabilizar distinto de cero.

En los asientos WIP se ve que el asiento contable tambien se crea con importe:

- linea de `485001 Ingresos anticipados (WIP)` en debe;
- linea de `705001 WIP` en haber;
- importes correctos y asiento publicado.

El problema que sigue ocurriendo:

- la columna `Distribucion analitica` de la linea `705001 WIP` aparece vacia;
- en intentos anteriores llego a verse como `0% S00032 - NOKIA SPAIN`;
- los apuntes analiticos WIP siguen apareciendo a `0,00`;
- abrir el asiento desde el calculo no esta reparando la distribucion visible en Odoo.

## Pruebas funcionales realizadas

1. Crear un presupuesto analitico con proyecto.
2. Calcular WIP.
3. Abrir el calculo WIP.
4. Confirmar que la linea del calculo tiene cuenta analitica/proyecto.
5. Crear asiento WIP.
6. Abrir el asiento generado.
7. Revisar la linea de ingreso WIP.
8. Revisar apuntes analiticos.
9. Agrupar apuntes analiticos por proyecto.
10. Repetir la prueba con presupuestos nuevos.
11. Repetir la prueba con calculos/asientos ya existentes.
12. Abrir el asiento antiguo desde el calculo para intentar que se repare.
13. Revisar tambien la reversion.

Resultado actual:

- El calculo WIP funciona.
- El asiento WIP se crea.
- El importe contable del asiento es correcto.
- La distribucion analitica sigue sin aparecer en la linea WIP.
- El apunte analitico sigue quedando a `0,00`.

## Cambios tecnicos que se han intentado

Se ha intentado resolver el problema por varias vias:

1. Preparar la distribucion analitica antes de crear el asiento.

   Se intento completar `analytic_distribution` durante la preparacion de `move_vals`, usando la cuenta analitica de la linea WIP.

2. Forzar la distribucion despues de crear el asiento.

   Se intento localizar la linea contable de ingreso WIP y escribir `analytic_distribution` despues de crear el `account.move`.

3. Marcar las lineas contables WIP.

   Se anadieron campos tecnicos:

   - `aunna_wip_calculation_line_id`
   - `aunna_wip_project_id`

   La idea era dejar enlazada cada linea contable con su linea de calculo WIP y su proyecto.

4. Reparar al publicar el asiento.

   Se intento ejecutar la reparacion antes y despues de `action_post`.

5. Reparar al abrir el asiento desde el calculo.

   Se intento que `action_open_wip_move` y `action_open_reversal_move` volvieran a normalizar la distribucion.

6. Buscar el calculo WIP por referencia/nombre del asiento.

   Se intento emparejar el asiento con el calculo usando `ref`, `name` y variantes del nombre.

7. Buscar el calculo WIP por relacion directa.

   Se cambio la logica para buscar primero por:

   - `move_id`
   - `reversal_move_id`

   Esto evita depender del nombre/ref del asiento.

8. Forzar la distribucion directamente desde el calculo.

   Se anadio una reparacion directa desde `aunna.wip.calculation`, usando `calculation.move_id` y `calculation.reversal_move_id`.

9. Evitar errores con distribuciones vacias.

   Se corrigio un error detectado:

   ```text
   TypeError: 'bool' object is not iterable
   ```

   Ocurria cuando `analytic_distribution` venia como `False`.

10. Reconstruir apuntes analiticos.

    Se intento reconstruir apuntes analiticos desde la linea contable WIP cuando el importe quedaba a cero.

## Errores encontrados durante las pruebas

Error detectado y corregido en una iteracion:

```text
TypeError: 'bool' object is not iterable
```

Origen:

- el metodo intentaba iterar una distribucion analitica que podia venir como `False`;
- se normalizo a diccionario vacio antes de procesarla.

Estado despues de corregirlo:

- ya no bloquea la creacion del asiento por ese error;
- pero la distribucion analitica sigue sin verse en la linea contable WIP.

## Estado actual

La incidencia sigue abierta.

Lo que funciona:

- calculo WIP;
- importes WIP;
- creacion del asiento;
- publicacion del asiento;
- configuracion WIP por compania;
- uso del diario correcto por compania;
- cuentas contables correctas en el asiento.

Lo que no funciona todavia:

- la linea WIP no conserva/muestra `analytic_distribution`;
- el asiento sigue sin mostrar la cuenta analitica del proyecto;
- los apuntes analiticos derivados siguen quedando a `0,00`;
- los asientos ya creados tampoco se reparan al abrirlos desde el calculo.

## Hipotesis pendientes de confirmar

1. El modulo cargado en Odoo puede no ser exactamente la misma version que la carpeta local.

   Si el metodo de reparacion directa no existe en servidor, o no se esta ejecutando, Odoo seguira creando los asientos igual que antes.

2. La escritura de `analytic_distribution` puede estar siendo eliminada por otro proceso posterior.

   Puede ocurrir si otro modulo o una logica estandar recalcula/limpia la distribucion despues de crear o publicar el asiento.

3. Puede haber una diferencia entre la cuenta de ingreso WIP configurada y la linea real del asiento.

   Visualmente parece ser `705001 WIP`, pero hay que confirmarlo en base de datos por ID de cuenta, no solo por codigo/nombre.

4. Puede haber una restriccion de planes analiticos.

   Si Odoo espera una combinacion de dimensiones analiticas y solo se esta informando la cuenta del proyecto, puede que el valor no se comporte como se espera.

5. Puede que el asiento se este creando desde una ruta distinta.

   Si otro modulo sobrescribe la creacion del asiento WIP despues de este, podria no estar pasando por la reparacion del modulo.

## Comprobaciones recomendadas en Odoo shell

Comprobar que el modulo esta actualizado y cargado:

```python
module = env["ir.module.module"].search([("name", "=", "aunna_wip_project_link_fix")], limit=1)
module.state
module.latest_version
```

Comprobar si el metodo nuevo existe realmente en servidor:

```python
hasattr(env["aunna.wip.calculation"], "_aunna_wip_force_own_move_distributions")
```

Comprobar un calculo concreto:

```python
calc = env["aunna.wip.calculation"].search([("name", "ilike", "eje11")], limit=1)
calc.name
calc.move_id.name
calc.line_ids.read(["analytic_account_id", "project_id", "wip_amount"])
calc.move_id.line_ids.read(["account_id", "debit", "credit", "analytic_distribution"])
```

Forzar manualmente la reparacion desde shell:

```python
calc._aunna_wip_force_own_move_distributions(moves=calc.move_id)
calc.move_id.line_ids.read(["account_id", "analytic_distribution"])
```

Prueba minima de escritura directa:

```python
line = calc.move_id.line_ids.filtered(lambda l: l.account_id.code == "705001")[:1]
analytic_account = calc.line_ids[:1].analytic_account_id
line.with_context(check_move_validity=False).write({
    "analytic_distribution": {str(analytic_account.id): 100.0},
})
line.read(["analytic_distribution"])
```

Interpretacion:

- Si esta escritura directa funciona, el problema esta en que la reparacion no se esta ejecutando o no esta localizando la linea.
- Si esta escritura directa no funciona, el problema esta en una restriccion/limpieza posterior del campo `analytic_distribution`.
- Si el metodo no existe en servidor, el codigo local no esta cargado realmente en Odoo.

## Pendiente antes de darlo por resuelto

No se debe cerrar esta tarea hasta comprobar en Odoo que:

1. En un asiento WIP nuevo, la linea `705001 WIP` muestra distribucion analitica al 100%.
2. En un asiento WIP antiguo, abrirlo desde el calculo repara la distribucion.
3. En `Contabilidad > Contabilidad > Apuntes analiticos`, el apunte WIP ya no queda a `0,00`.
4. Al agrupar por proyecto, el apunte aparece bajo el proyecto correcto.
5. La reversion no rompe la distribucion ni genera efectos secundarios.
