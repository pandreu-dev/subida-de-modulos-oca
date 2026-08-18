from . import models

# Campos x_studio_ (de Studio) que este modulo ADOPTA como codigo, por modelo.
# NO se incluyen a proposito (decision de negocio, Laura):
#   - hr.employee.x_studio_subtipo_de_empleado (selection ANTIGUO, duplicado del m2o)
#   - project.project.x_studio_inactividad_directa (no se usa)
FIELDS_BY_MODEL = {
    "hr.employee": (
        "x_studio_tipo_empleado_1",
        "x_studio_subtipo_empleado",
        "x_studio_tipo_de_personal_1",
        "x_studio_fecha_de_alta_1",
    ),
    "project.project": (
        "x_studio_selection_field_3ib_1j1am422d",  # Productividad
    ),
}


def _adopt(cr):
    """Adopta los campos: state='base' + ir.model.data propio (idempotente).

    Solo METADATOS (no toca columnas): mismos ids y valores. Corre ANTES de la
    reflexion (pre_init_hook) para que Odoo los reclame como codigo y no como
    manuales de Studio. Ver zambudio_master_data (misma tecnica, verificada).
    """
    for model, names in FIELDS_BY_MODEL.items():
        cr.execute(
            "UPDATE ir_model_fields SET state='base' WHERE model=%s AND name IN %s",
            (model, names),
        )
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            SELECT 'zambudio_hr_project_fields',
                   'field_'||replace(f.model,'.','_')||'__'||f.name,
                   'ir.model.fields', f.id, true
            FROM ir_model_fields f
            WHERE f.model=%s AND f.name IN %s
            ON CONFLICT (module, name) DO NOTHING
            """,
            (model, names),
        )


def pre_init_hook(env):
    _adopt(env.cr)
