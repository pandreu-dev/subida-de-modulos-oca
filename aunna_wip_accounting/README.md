# Aunnna WIP - Contabilizacion

## Objetivo

Este modulo contabiliza el WIP calculado por `aunna_wip_budget_calc`.

Su responsabilidad es crear el asiento WIP y su asiento de reversion, tanto manualmente como mediante un proceso automatico mensual.

Este modulo no calcula por si solo el WIP desde cero: depende del modulo de calculo y utiliza sus snapshots.

## Dependencias

El modulo depende de:

- `aunna_wip_budget_calc`

Al depender de ese modulo hereda el modelo `aunna.wip.calculation` y usa los calculos WIP ya generados.

## Configuracion

Ruta:

`Contabilidad > Contabilidad > Transacciones > Configuracion WIP`

Tambien se integra en Ajustes como bloque de configuracion WIP.

La configuracion WIP es por compania. Cada compania debe tener informado su propio diario WIP y sus cuentas. Esto evita que un presupuesto de CITRIC use por error el diario WIP de AUNNA, o al reves.

Campos de configuracion:

- Diario WIP.
- Cuenta ingreso WIP.
- Cuenta ingresos anticipados.
- Publicar asientos WIP automaticamente.
- Habilitar contabilizacion automatica del WIP.
- Dias de espera para contabilizacion automatica.
- Permitir WIP negativo.

Ejemplo funcional de cuentas:

- Cuenta ingreso WIP: `705001`.
- Cuenta de ingresos anticipados: `485000`.

El diario WIP debe ser de tipo Miscelanea y pertenecer a la compania del calculo.
Las cuentas deben estar disponibles para la compania del calculo.

## Campos anadidos al presupuesto analitico

En `budget.analytic` se anade:

- `wip_auto_accounting`: check de Contabilizacion WIP automatica.
- `wip_account_move_count`: contador de asientos WIP asociados.

El check se usa para decidir que presupuestos entran en el proceso automatico.

## Campos anadidos al calculo WIP

En `aunna.wip.calculation` se anade:

- `journal_id`: diario usado.
- `move_id`: asiento WIP.
- `reversal_move_id`: asiento de reversion.
- `reversal_date`: fecha de reversion.
- `accounting_state`: estado contable.
- `budget_wip_auto_accounting`: indicador relacionado del presupuesto.

## Flujo manual

1. Entrar en un presupuesto analitico.
2. Pulsar `Calcular WIP`.
3. Elegir fecha de corte.
4. Revisar el calculo generado.
5. Ajustar lineas si procede.
6. Pulsar `Crear asiento WIP`.
7. El sistema crea el asiento WIP con fecha de corte.
8. El sistema crea la reversion.
9. Si esta activada la publicacion automatica, ambos asientos se publican cuando corresponde.

Si no se indica una fecha de reversion, el modulo usa el dia siguiente a la fecha de calculo.

## Flujo automatico

El modulo incluye un cron diario:

- Nombre: `WIP - Contabilizacion mensual automatica`.
- Modelo: `aunna.wip.calculation`.
- Metodo: `_cron_monthly_auto_accounting`.
- Frecuencia: diaria.

La logica automatica funciona asi:

1. Lee la configuracion WIP de la compania de cada presupuesto.
2. Comprueba que la contabilizacion automatica este habilitada.
3. Calcula el primer dia del mes de ejecucion.
4. Calcula el dia de disparo segun los dias de espera configurados.
5. Si aun no se ha llegado al dia de disparo, no genera nada.
6. Toma como fecha de corte el ultimo dia del mes anterior.
7. Busca presupuestos analiticos abiertos con `Contabilizacion WIP automatica` marcado.
8. Si durante el plazo de espera ya se creo manualmente un asiento WIP para ese presupuesto, lo omite.
9. Si ya existe un asiento para ese presupuesto, fecha y compania, lo omite.
10. Calcula el WIP con origen automatico.
11. Crea el asiento WIP con fecha fin del mes anterior.
12. Crea la reversion con fecha primer dia del mes actual.

Ejemplo:

- Fecha de ejecucion: 05/06/2026.
- Dias de espera: 5.
- Fecha de corte: 31/05/2026.
- Fecha del asiento WIP: 31/05/2026.
- Fecha de reversion: 01/06/2026.

Si el cron no se ejecuta el dia previsto, puede actuar en dias posteriores porque la condicion es que la fecha de ejecucion sea igual o posterior al dia de disparo.

## Asiento WIP

Para WIP positivo:

- Debe: cuenta de ingresos anticipados.
- Haber: cuenta de ingreso WIP.
- La imputacion analitica se aplica en la linea de ingreso WIP usando la cuenta analitica de la linea WIP.

Para WIP negativo:

- Solo se permite si esta activada la opcion `Permitir WIP negativo`.
- La direccion contable se invierte.

Si el WIP es cero, no se crea asiento y el calculo queda como no requerido.

## Reversion

La reversion se crea usando la funcion nativa de Odoo `_reverse_moves`.

Si la opcion de publicacion automatica esta activa:

- Si la fecha de reversion es hoy o anterior, se publica.
- Si la fecha de reversion es futura, se deja con autopost a fecha.

## Control de duplicados

El modulo evita duplicados por:

- Presupuesto.
- Fecha de corte.
- Compania.
- Existencia de asiento WIP previo.

Tambien bloquea el presupuesto con `FOR UPDATE` al crear el asiento para reducir riesgos de doble generacion concurrente.

## Prueba controlada del automatico

En la configuracion WIP existe el boton:

- `Probar automatico WIP`

Permite simular una fecha de ejecucion sin cambiar la fecha del servidor.

Campos del asistente:

- Fecha simulada de ejecucion.
- Presupuesto analitico opcional.
- Solo calcular, sin crear asientos.

Esto sirve para probar cierres mensuales en cualquier dia.

## Botones y vistas

En el presupuesto analitico:

- `Asientos WIP`: abre los asientos WIP y reversiones asociados.

En el calculo WIP:

- `Crear asiento WIP`.
- `Abrir asiento`.
- `Abrir reversion`.

En el formulario de calculo se muestra un bloque de informacion contable con diario, asiento, reversion, fecha de reversion y estado.

## Permisos

El asistente de prueba del automatico esta disponible para:

- `account.group_account_manager`

La contabilizacion usa los permisos normales de contabilidad y los permisos heredados del modulo de calculo WIP.

## Tests

El modulo incluye pruebas para:

- Existencia de campos de configuracion.
- Tratamiento de valores invalidos en dias de espera.

## Archivos relevantes

- `models/wip_calculation.py`: creacion de asientos, reversiones, duplicados y automatico.
- `models/budget_analytic.py`: check automatico y smart button de asientos.
- `models/res_company.py`: configuracion WIP por compania.
- `models/res_config_settings.py`: ajustes visibles por compania.
- `wizard/wip_auto_test_wizard.py`: prueba controlada del automatico.
- `views/res_config_settings_views.xml`: bloque de configuracion WIP.
- `views/wip_calculation_views.xml`: botones y campos contables en calculo WIP.
- `views/budget_analytic_views.xml`: check y boton en presupuesto analitico.
- `data/ir_cron.xml`: cron mensual ejecutado diariamente.
- `security/ir.model.access.csv`: permisos del asistente.
