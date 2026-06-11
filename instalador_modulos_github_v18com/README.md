# Instalador OCA para Odoo 18 Community

## Objetivo

Este modulo proporciona un instalador visual para clonar, exponer e instalar addons OCA desde repositorios de GitHub en una instancia Odoo 18 Community.

El objetivo es que un usuario funcional o administrador pueda preparar repositorios OCA sin ejecutar comandos manuales en consola para cada instalacion.

Esta variante esta pensada para un servidor Plesk/Debian con servicio `odoo18`, usuario de sistema `odoo18` y rutas bajo `/opt/odoo18`.

## Para que se usa

Se usa para:

- Registrar una URL de repositorio OCA.
- Clonar o actualizar el repositorio.
- Detectar addons Odoo dentro del repositorio.
- Leer manifests.
- Exponer addons en una carpeta OCA compartida visible por Odoo.
- Registrar la ruta en `addons_path` en runtime.
- Persistir opcionalmente la ruta en el fichero de configuracion.
- Refrescar Apps.
- Instalar el addon seleccionado.
- Diagnosticar errores de rutas, manifests, dependencias y estado final.

## Entorno objetivo

Este modulo esta configurado para Odoo 18 Community.

Valores por defecto:

- Rama: `18.0`.
- Carpeta de clonado: `/opt/odoo18/addons/oca/repositories`.
- Carpeta OCA compartida: `/opt/odoo18/addons/oca`.
- Fichero de configuracion: `/etc/odoo18.conf`.
- Servicio: `odoo18`.
- Usuario sistema esperado para permisos de rutas: `odoo18:odoo18`.
- Ruta base: `/opt/odoo18`.
- Codigo Odoo: `/opt/odoo18/odoo`.
- Entorno virtual: `/opt/odoo18/venv`.
- Log: `/var/log/odoo18/odoo.log`.

El `addons_path` esperado del servidor incluye:

- `/opt/odoo18/odoo/addons`
- `/opt/odoo18/addons/oca`
- `/opt/odoo18/addons/custom`

Los repositorios OCA se clonan dentro de:

```text
/opt/odoo18/addons/oca/repositories/<repo>
```

Los addons detectados se exponen a Odoo mediante enlaces simbolicos en:

```text
/opt/odoo18/addons/oca/<nombre_modulo>
```

Ejemplo:

```text
/opt/odoo18/addons/oca/repositories/l10n-spain/l10n_es_aeat
```

queda expuesto como:

```text
/opt/odoo18/addons/oca/l10n_es_aeat
```

Los repositorios completos no deben anadirse uno a uno al `addons_path`; solo debe estar la carpeta padre compartida `/opt/odoo18/addons/oca`.

## Dependencias

El modulo depende solo de:

- `base`

Las operaciones de Git, sistema de ficheros, lectura de manifests e instalacion de modulos se gestionan desde el propio modulo.

## Modelos principales

### `oca.repository.installer`

Representa una instalacion de repositorio OCA.

Campos principales:

- URL del repositorio.
- URL normalizada.
- Rama.
- Nombre de repositorio.
- Estado.
- Ruta del clon.
- Ruta OCA compartida.
- Ruta usada en `addons_path`.
- Addon objetivo.
- Addons detectados.
- Ultima operacion.
- Ultimo comando.
- Salida estandar.
- Salida de error.
- Resumen funcional.
- Causa detectada.
- Como resolverlo.
- Diagnostico de rutas.
- Mensajes Odoo detectados.
- Dependencias Python faltantes.
- Dependencias binarias faltantes.
- Dependencias Odoo faltantes.
- Codigo de fallo.
- Estado final del modulo.
- Detalle tecnico.

### `oca.repository.installer.addon`

Representa cada addon detectado dentro del repositorio.

Campos principales:

- Addon.
- Resumen.
- Categoria.
- Licencia.
- Dependencias Odoo.
- Dependencias Python.
- Dependencias binarias.
- Ruta fuente.
- Manifest.
- Ruta compartida.
- Existe en disco.
- Tiene manifest.
- Manifest legible.
- Installable.
- Nombre tecnico coincide con ruta.
- Expuesto en ruta compartida.
- Visible en Apps.
- Instalado.
- Estado Odoo.
- Estado funcional.
- Ultimo resultado.

## Menu

El modulo crea la aplicacion:

`OCA Installer`

Menus:

- `OCA Installer > Instalaciones`
- `OCA Installer > Configuracion`

La configuracion se abre sobre `res.config.settings`.

## Configuracion

Campos de ajustes:

- Rama OCA por defecto.
- Carpeta de clonado.
- Carpeta OCA visible por Odoo.
- Estrategia de exposicion de addons.
- Persistir `addons_path` en el fichero de configuracion.
- Ruta del fichero de configuracion Odoo.
- Instalar dependencias Python automaticamente.
- Comando de instalacion Python.
- Instalar dependencias binarias automaticamente.
- Comando de instalacion binaria.

La estrategia de exposicion puede ser:

- Symlink.
- Copia.

En este entorno la estrategia recomendada es `Symlink`.

Comando Python por defecto:

```text
sudo -n /opt/odoo18/venv/bin/pip install {packages}
```

Comando de sistema por defecto:

```text
sudo -n apt-get install -y {packages}
```

Las instalaciones automaticas de dependencias estan desactivadas por defecto. Los comandos quedan preparados para activarlas solo si el usuario del servicio Odoo puede ejecutarlos sin password.

## Flujo de uso

1. Entrar en `OCA Installer > Configuracion`.
2. Revisar rama, rutas y estrategia.
3. Entrar en `OCA Installer > Instalaciones`.
4. Crear una nueva instalacion.
5. Informar la URL del repositorio, por ejemplo `https://github.com/OCA/l10n-spain.git`.
6. Informar la rama si no se quiere usar la rama por defecto.
7. Pulsar `Preparar repositorio`.
8. El modulo clona o actualiza el repositorio.
9. El modulo detecta addons con `__manifest__.py`.
10. El modulo expone los addons en la carpeta compartida.
11. El modulo registra la ruta en runtime y opcionalmente en el fichero de configuracion.
12. Pulsar `Refrescar Apps` si se quiere relanzar la deteccion.
13. Seleccionar el addon objetivo.
14. Pulsar `Instalar addon`.
15. Revisar el resultado final y los diagnosticos.

En el servidor real, despues de clonar y crear symlinks puede ser recomendable reiniciar el servicio si se quiere asegurar una carga limpia del entorno:

```text
systemctl restart odoo18
```

Despues se debe actualizar la lista de aplicaciones desde Odoo o por CLI.

## Validaciones

El modulo valida:

- URL de GitHub.
- Rama.
- Existencia y permisos de carpetas.
- Lectura de `__manifest__.py`.
- `installable`.
- Dependencias Odoo.
- Dependencias Python declaradas.
- Dependencias binarias declaradas.
- Que la ruta compartida sea carpeta padre de addons.
- Que Odoo tenga la ruta en `addons_path`.
- Que el modulo quede realmente instalado.

## Diagnostico de errores

El modulo guarda mensajes funcionales para facilitar la resolucion:

- Resumen funcional.
- Causa detectada.
- Como resolverlo.
- Diagnostico de rutas.
- Logs relevantes de Odoo.
- Dependencias faltantes.
- Estado final del modulo.

Ejemplos de situaciones diagnosticadas:

- No hay manifest.
- Manifest invalido.
- Addon no installable.
- Ruta incorrecta en `addons_path`.
- Odoo no ve la carpeta compartida.
- Conflicto de nombre con un addon ya existente.
- Dependencia Python faltante.
- Dependencia binaria faltante.
- Dependencia Odoo no disponible.

## Control de conflictos

Cuando expone addons en la carpeta OCA compartida, el modulo usa un marcador de origen para reconocer si una carpeta fue creada por el instalador.

Si ya existe un addon con el mismo nombre y no parece pertenecer a ese repositorio, se bloquea la operacion y se muestra un conflicto funcional. Esto evita sobrescribir addons existentes.

Esto es importante en la ruta `/opt/odoo18/addons/oca`, porque esa carpeta es compartida para todos los addons OCA expuestos por symlink.

## Seguridad

El modulo crea una categoria y grupo funcional `OCA Installer User`.

Los menus de instalaciones estan disponibles para usuarios internos.

El menu de configuracion esta limitado a administradores de sistema.

## Archivos relevantes

- `models/oca_repository_installer.py`: logica principal.
- `models/res_config_settings.py`: parametros de configuracion.
- `views/oca_repository_installer_views.xml`: vistas, botones y menus.
- `views/res_config_settings_views.xml`: bloque de ajustes.
- `security/security.xml`: categoria y grupo.
- `security/ir.model.access.csv`: permisos de modelos.
- `static/description/icon.png`: icono de aplicacion.
