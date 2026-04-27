{
    "name": "Instalador OCA para Odoo 18",
    "summary": "Clona, expone e instala addons OCA desde una URL de GitHub",
    "version": "18.0.1.3.0",
    "category": "Administration",
    "author": "OpenAI",
    "maintainer": "OpenAI",
    "website": "https://www.odoo.com",
    "license": "LGPL-3",
    "description": """
Instalador visual de repositorios OCA para Odoo 18.

Funciones principales:
- Clonado o actualizacion de repositorios desde GitHub.
- Exposicion de addons en una carpeta OCA comun para que Odoo los detecte.
- Refresco de Apps desde la propia interfaz.
- Instalacion guiada del addon seleccionado.
- Diagnostico claro de errores, dependencias Python, binarios y addons Odoo faltantes.
- Validacion fuerte de rutas, manifests, installable y estado final real del modulo.

Pensado para que una persona funcional pueda preparar e instalar addons OCA
sin depender de comandos manuales en consola.
    """,
    "depends": [
        "base",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/oca_repository_installer_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "application": True,
    "installable": True,
    "sequence": 5,
}
