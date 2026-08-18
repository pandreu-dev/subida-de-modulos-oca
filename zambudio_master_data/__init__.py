from . import models

# Nombres tecnicos de los 5 maestros de Studio y sus campos de negocio.
MASTER_MODELS = (
    "x_tipo_empleado",
    "x_subtipo_empleado",
    "x_tipo_de_personal",
    "x_sector",
    "x_crm_practica",
)
MASTER_FIELDS = ("x_name", "x_active", "x_studio_sequence", "x_studio_divisin")


def _adopt_masters(cr):
    """Adopta los 5 maestros como CODIGO sin mover datos (idempotente).

    Dos operaciones de METADATOS (no toca ninguna columna de datos):
      1) state='base' en los modelos y sus campos -> rompe el bucle que los
         mantiene 'manual' (deja de re-inyectarse el modelo como custom).
      2) INSERT de un ir.model.data PROPIO del modulo por cada modelo/campo,
         SIN borrar el de studio_customization -> por reference-count, el dia
         que se desinstale studio_customization estos modelos SOBREVIVEN.

    Debe correr ANTES de la reflexion:
      - Instalacion nueva (p.ej. PRO)  -> se llama desde pre_init_hook.
      - Actualizacion (p.ej. PRE)      -> se llama desde migrations/19.0.1.1.0/pre-migration.py.
    """
    cr.execute("UPDATE ir_model SET state='base' WHERE model IN %s", (MASTER_MODELS,))
    cr.execute(
        "UPDATE ir_model_fields SET state='base' WHERE model IN %s AND name IN %s",
        (MASTER_MODELS, MASTER_FIELDS),
    )
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'zambudio_master_data', 'model_'||replace(m.model,'.','_'), 'ir.model', m.id, true
        FROM ir_model m WHERE m.model IN %s
        ON CONFLICT (module, name) DO NOTHING
        """,
        (MASTER_MODELS,),
    )
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'zambudio_master_data', 'field_'||replace(f.model,'.','_')||'__'||f.name, 'ir.model.fields', f.id, true
        FROM ir_model_fields f WHERE f.model IN %s AND f.name IN %s
        ON CONFLICT (module, name) DO NOTHING
        """,
        (MASTER_MODELS, MASTER_FIELDS),
    )


def pre_init_hook(env):
    """Instalacion NUEVA (p.ej. PRO): adoptar los maestros ANTES de reflejar."""
    _adopt_masters(env.cr)


def post_init_hook(env):
    """Permisos de los 5 maestros, buscando el modelo por nombre.

    (No se pueden declarar por ir.model.access.csv: el xmlid model_x_... no
    queda bajo este modulo al ser modelos adoptados de Studio.)
    """
    Access = env["ir.model.access"]
    IrModel = env["ir.model"]
    g_user = env.ref("base.group_user")
    g_system = env.ref("base.group_system")
    for name in MASTER_MODELS:
        model = IrModel.search([("model", "=", name)], limit=1)
        if not model:
            continue
        if not Access.search_count([
            ("model_id", "=", model.id),
            ("group_id", "=", g_user.id),
            ("perm_read", "=", True),
        ]):
            Access.create({
                "name": "%s.user" % name,
                "model_id": model.id,
                "group_id": g_user.id,
                "perm_read": True,
            })
        if not Access.search_count([
            ("model_id", "=", model.id),
            ("group_id", "=", g_system.id),
            ("perm_write", "=", True),
        ]):
            Access.create({
                "name": "%s.mgr" % name,
                "model_id": model.id,
                "group_id": g_system.id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
                "perm_unlink": True,
            })
