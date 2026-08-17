from . import models

MASTER_MODELS = [
    "x_tipo_empleado",
    "x_subtipo_empleado",
    "x_tipo_de_personal",
    "x_sector",
    "x_crm_practica",
]


def post_init_hook(env):
    """Crea los permisos de los 5 maestros buscando el modelo por nombre.

    Se hace aqui (y no en ir.model.access.csv) porque cada modelo ya existia
    como modelo 'manual' de Studio: su xmlid no queda bajo este modulo, asi que
    un CSV con model_id:id=model_x_... no resuelve al instalar. Buscando el
    modelo por su nombre tecnico funciona igual y es idempotente.

    Permisos (replican los de Studio): usuarios internos leen; Administracion
    (Ajustes) crea/edita/borra.
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
