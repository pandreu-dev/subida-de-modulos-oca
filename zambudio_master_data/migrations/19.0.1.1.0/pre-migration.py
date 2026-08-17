# -*- coding: utf-8 -*-
"""Adopta los 5 maestros de Studio como modelos de CODIGO sin mover datos.

Por que hace falta (verificado contra la fuente de Odoo 19):
- Mientras `ir_model.state='manual'`, `_add_manual_models()` re-inyecta en cada
  arranque una clase CustomModel(_custom=True) para ese nombre, y la reflexion
  recalcula `state='manual'` desde `_custom`. Bucle que el codigo no rompe solo.
- La propiedad `ir.model.data` (xmlid) es un eje aparte que la reflexion NUNCA
  transfiere: el puntero de `studio_customization` sigue siendo el unico dueno.

Esta pre-migracion (corre ANTES de cargar/reflejar en el -u):
  1) Pone state='base' en los 5 modelos y en sus 4 campos de negocio -> deja de
     inyectarse como manual y la reflexion los reclama como codigo (_custom=False,
     _module='zambudio_master_data').
  2) Anade un ir.model.data PROPIO por cada modelo/campo (idempotente, ON CONFLICT
     DO NOTHING), SIN borrar el de studio_customization. Asi, por reference-count,
     el dia que se desinstale studio_customization estos modelos SOBREVIVEN.

NO toca ninguna columna fisica (jsonb de x_name, selection, m2o) -> los datos y las
referencias quedan intactos. Solo metadatos, dentro de la transaccion del -u.

Nota deliberada: NO se adoptan los campos "chatter" (message_*/activity_*) ni se
hereda mail.thread; en estos maestros el chatter no aporta y queda como estaba.
"""

NAMES = (
    "x_tipo_empleado",
    "x_subtipo_empleado",
    "x_tipo_de_personal",
    "x_sector",
    "x_crm_practica",
)
FIELDS = ("x_name", "x_active", "x_studio_sequence", "x_studio_divisin")


def migrate(cr, version):
    if not version:
        # Instalacion desde cero: no hay modelo Studio que adoptar.
        return

    # 1) Romper el bucle 'manual': state='base' en modelos y campos de negocio.
    cr.execute("UPDATE ir_model SET state='base' WHERE model IN %s", (NAMES,))
    cr.execute(
        "UPDATE ir_model_fields SET state='base' WHERE model IN %s AND name IN %s",
        (NAMES, FIELDS),
    )

    # 2) Reclamar propiedad SIN borrar la de studio (idempotente).
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'zambudio_master_data',
               'model_' || replace(m.model, '.', '_'),
               'ir.model', m.id, true
        FROM ir_model m
        WHERE m.model IN %s
        ON CONFLICT (module, name) DO NOTHING
        """,
        (NAMES,),
    )
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'zambudio_master_data',
               'field_' || replace(f.model, '.', '_') || '__' || f.name,
               'ir.model.fields', f.id, true
        FROM ir_model_fields f
        WHERE f.model IN %s AND f.name IN %s
        ON CONFLICT (module, name) DO NOTHING
        """,
        (NAMES, FIELDS),
    )
