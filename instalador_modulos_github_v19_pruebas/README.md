# Instalador OCA para Odoo 19 Pruebas

## Objetivo

Este modulo es la variante de pruebas del instalador OCA para Odoo 19.

Sirve para clonar, exponer e instalar addons OCA desde GitHub en el entorno de pruebas, usando rutas separadas con sufijo `_pruebas`.

## Para que se usa

Se usa para preparar repositorios OCA en una instancia PRE o de pruebas sin mezclar rutas con el entorno Odoo 19 principal.

Permite:

- Clonar repositorios OCA.
- Actualizar repositorios ya clonados.
- Detectar addons.
- Leer manifests.
- Exponer addons en carpeta OCA compartida de pruebas.
- Refrescar Apps.
- Instalar el addon seleccionado.
- Diagnosticar errores de rutas, dependencias y estado final.

## Version objetivo

Este modulo esta configurado para Odoo 19 en entorno de pruebas.

Valores por defecto:

- Rama: `19.0`.
- Carpeta de clonado: `/opt/odoo19_pruebas/addons/oca/repositories`.
- Carpeta OCA compartida: `/opt/odoo19_pruebas/addons/oca`.
- Fichero de configuracion: `/etc/odoo19_pruebas.conf`.

## Diferencia frente al instalador Odoo 19 normal

La diferencia principal son las rutas y parametros tecnicos.

Este modulo usa claves de configuracion propias:

- `instalador_modulos_github_v19_pruebas.oca_git_branch`
- `instalador_modulos_github_v19_pruebas.oca_clone_root`
- `instalador_modulos_github_v19_pruebas.oca_shared_addons_path`
- `instalador_modulos_github_v19_pruebas.oca_path_strategy`
- `instalador_modulos_github_v19_pruebas.oca_persist_addons_path_to_config`
- `instalador_modulos_github_v19_pruebas.oca_odoo_config_path`
- `instalador_modulos_github_v19_pruebas.oca_auto_install_python_deps`
- `instalador_modulos_github_v19_pruebas.oca_auto_install_binary_deps`
- `instalador_modulos_github_v19_pruebas.oca_python_install_command`
- `instalador_modulos_github_v19_pruebas.oca_binary_install_command`

Esto permite mantener separada la configuracion del entorno de pruebas.

## Dependencias

El modulo depende solo de:

- `base`

## Modelos principales

### `oca.repository.installer`

Modelo principal de instalacion de repositorios.

Gestiona:

- URL del repositorio.
- Rama.
- Ruta de clonado.
- Ruta compartida.
- Addons detectados.
- Preparacion del repositorio.
- Refresco de Apps.
- Instalacion del addon seleccionado.
- Diagnosticos.

### `oca.repository.installer.addon`

Modelo de addons detectados en el repositorio.

Guarda datos como:

- Nombre del addon.
- Manifest.
- Dependencias.
- Estado en disco.
- Estado en Odoo.
- Resultado de instalacion.

## Menu

El modulo crea la aplicacion:

`OCA Installer`

Menus:

- `OCA Installer > Instalaciones`
- `OCA Installer > Configuracion`

## Configuracion

Campos de ajustes:

- Rama OCA por defecto.
- Carpeta de clonado.
- Carpeta OCA visible por Odoo.
- Estrategia de rutas.
- Persistir `addons_path` en fichero de configuracion.
- Fichero de configuracion.
- Auto instalar dependencias Python.
- Comando Python.
- Auto instalar dependencias binarias.
- Comando binario.

Comando Python sugerido por la vista:

```text
sudo -n /opt/odoo19_pruebas/venv/bin/pip install {packages}
```

Comando binario sugerido:

```text
sudo -n apt-get install -y {packages}
```

## Flujo funcional

1. Abrir `OCA Installer > Configuracion`.
2. Confirmar que las rutas apuntan a `/opt/odoo19_pruebas`.
3. Crear una instalacion.
4. Informar la URL de GitHub del repositorio OCA.
5. Indicar rama si procede.
6. Pulsar `Preparar repositorio`.
7. El modulo clona o actualiza el repositorio.
8. Detecta addons con manifest en el primer nivel.
9. Expone los addons en `/opt/odoo19_pruebas/addons/oca`.
10. Registra la ruta en `addons_path`.
11. Refresca Apps.
12. Selecciona el addon.
13. Pulsa `Instalar addon`.
14. Revisa el diagnostico y estado final.

## Validaciones

El modulo valida:

- Rutas de pruebas.
- Permisos de escritura.
- Manifests.
- `installable`.
- Dependencias Odoo.
- Dependencias Python.
- Dependencias binarias.
- Conflictos de nombre.
- Presencia en Apps.
- Estado final tras la instalacion.

## Control de conflictos

Si ya existe un addon con el mismo nombre en la carpeta OCA compartida y no pertenece al repositorio actual, el modulo bloquea la exposicion y muestra la causa.

Esto protege el entorno de pruebas contra sobreescrituras accidentales.

## Seguridad

El modulo crea categoria, privilegio y grupo `OCA Installer User`.

Los menus de instalaciones estan disponibles para usuarios internos.

La configuracion esta limitada a administradores de sistema.

## Archivos relevantes

- `models/oca_repository_installer.py`: logica principal.
- `models/res_config_settings.py`: parametros de configuracion de pruebas.
- `views/oca_repository_installer_views.xml`: vistas y botones.
- `views/res_config_settings_views.xml`: bloque de ajustes.
- `security/security.xml`: categoria, privilegio y grupo.
- `security/ir.model.access.csv`: permisos.
- `static/description/icon.png`: icono.
