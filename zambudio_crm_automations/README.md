# Zambudio CRM Automations

Migracion a Python de varias automatizaciones de Odoo Studio sobre `crm.lead`.
No usa `base.automation` ni `ir.actions.server`: toda la logica vive en overrides
de `create` (`@api.model_create_multi`) y `write` del modelo, delegando en helpers
privados `_zambudio_apply_*()`.

## Automatizaciones incluidas

1. **Sincronizar probabilidad + fase** (`_zambudio_apply_prob`): ajusta
   `probability` y `x_studio_etapa_1` segun el nombre de la etapa. Guarda de
   contexto `skip_zambudio_prob`.
2. **Ingreso esperado = SoS + COGS** (`_zambudio_apply_expected`):
   `expected_revenue = x_studio_ingresos_sos + x_studio_ingresos_cogs`. Si ambos
   son ~0 no toca nada. Guarda `skip_zambudio_expected`.
3. **Fecha de cierre = hoy** al pasar a Ganado o Perdida
   (`_zambudio_apply_close`). Guarda `skip_zambudio_close`.
4. **Pasar a Perdido** cuando hay `lost_reason_id` (`_zambudio_apply_lost`):
   mueve la etapa a la de Perdida (busqueda por nombre). Guarda
   `skip_zambudio_lost`.
5. **Contrato: inicio/fin** (`_zambudio_apply_contract`): calcula
   `x_studio_fecha_inicio_contrato` (primer dia del mes siguiente al cierre) y
   `x_studio_fecha_fin_de_contrato` (inicio + meses de duracion). Guarda
   `skip_zambudio_contract`.

## Notas de diseno

- **Campos de Studio**: todo acceso a `x_studio_*` se protege con
  `"campo" in self._fields`. Si el campo no existe (fase transitoria), se salta
  sin error.
- **Anti-recursion**: cada logica tiene su propia bandera de contexto; las
  reescrituras se hacen con `with_context(skip_zambudio_...=True)`.
- **Referencias por nombre**: las etapas se referencian por
  `crm.stage.name` mediante constantes, nunca por id de BD.
- **Multi-compania**: la busqueda de la etapa de Perdida filtra por la compania
  del lead (o etapas compartidas).
- **Eficiencia**: solo se escribe cuando el valor cambia de verdad.

## Descartado (no implementado)

- **Inicializar probabilidades a 0 al crear**: la automatizacion original tenia
  trigger `on_unlink` (bug), no se reproduce.
- **Prueba correo asistencia**: descartada por no formar parte del objetivo.

## Constantes a confirmar

- `STAGE_WON_NAME = "Ganado"`
- `STAGE_LOST_NAME = "Perdida"`
- Nombres de etapa comparados en la logica 1 (con acentos/erratas tal cual del
  Studio original): `Sin cualificar`, `Cualificada`, `Abandonada`,
  `En preparacion`, `Entregada`, `En negociacion`, `Perdida`, `Retirada`,
  `Ganado`.
- Nombres de campo Studio con erratas: `x_studio_probabilidad_negociacin`,
  `x_studio_meses_de_duracin`.
