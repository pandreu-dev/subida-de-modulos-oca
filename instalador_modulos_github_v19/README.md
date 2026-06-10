# Instalador OCA para Odoo 19

## Objetivo

Este modulo proporciona un instalador visual para clonar, exponer e instalar addons OCA desde repositorios de GitHub en una instancia Odoo 19.

Permite trabajar con repositorios OCA desde la interfaz de Odoo, con diagnostico funcional de errores y validaciones de rutas, manifests, dependencias y estado final.

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
- Ver diagnosticos claros cuando algo falla.

## Version objetivo

Este modulo esta configurado para Odoo 19.

Valores por defecto:

- Rama: `19.0`.
- Carpeta de clonado: `/opt/odoo19/addons/oca/repositories`.
- Carpeta OCA compartida: `/opt/odoo19/addons/oca`.
- Fichero de configuracion: `/etc/odoo19.conf`.

## Dependencias

El modulo depende solo de:

- `base`

## Modelos principales

### `oca.repository.installer`

Modelo principal de instalacion.

Gestiona:

- URL y rama del repositorio.
- Clonado y actualizacion por Git.
- Deteccion de addons.
- Exposicion de addons en ruta compartida.
- Registro de `addons_path`.
- Refresco de Apps.
- Instalacion del addon seleccionado.
- Diagnostico y estado final.

### `oca.repository.installer.addon`

Modelo de addons detectados.

Guarda:

- Nombre tecnico.
- Resumen.
- Categoria.
- Licencia.
- Dependencias Odoo.
- Dependencias Python.
- Dependencias binarias.
- Ruta fuente.
- Ruta compartida.
- Estado del manifest.
- Visibilidad en Apps.
- Estado del modulo en Odoo.
- Resultado de instalacion.

## Menu

El modulo crea la aplicacion:

`OCA Installer`

Menus:

- `OCA Installer > Instalaciones`
- `OCA Installer > Configuracion`

## Configuracion

Campos disponibles en ajustes:

- Rama OCA por defecto.
- Carpeta de clonado.
- Carpeta OCA visible por Odoo.
- Estrategia de rutas.
- Persistir `addons_path` en fichero de configuracion.
- Fichero de configuracion de Odoo.
- Auto instalar dependencias Python.
- Comando Python.
- Auto instalar dependencias binarias.
- Comando binario.

Comando Python sugerido por la vista:

```text
sudo -n /opt/odoo19/venv/bin/pip install {packages}
```

Comando binario sugerido:

```text
sudo -n apt-get install -y {packages}
```

## Flujo funcional

1. Abrir `OCA Installer > Configuracion`.
2. Revisar rutas, rama y estrategia.
3. Crear una instalacion en `OCA Installer > Instalaciones`.
4. Informar la URL del repositorio.
5. Pulsar `Preparar repositorio`.
6. El modulo normaliza la URL.
7. El modulo clona o actualiza el repositorio con Git.
8. Se inspeccionan las carpetas del primer nivel buscando addons con `__manifest__.py`.
9. Se leen dependencias y metadatos de cada manifest.
10. Se exponen los addons en la carpeta compartida mediante symlink o copia.
11. Se registra la carpeta compartida en `addons_path` de runtime.
12. Se persiste la ruta en el fichero de configuracion si esta activado.
13. Se refresca la lista de Apps.
14. Se selecciona un addon.
15. Se pulsa `Instalar addon`.
16. El modulo valida dependencias y ejecuta la instalacion.
17. Se comprueba el estado final real del modulo.

## Validaciones principales

El modulo valida:

- Que la URL sea valida.
- Que la rama exista o sea usable.
- Que las carpetas de clonado y compartida sean accesibles.
- Que el repositorio contenga carpetas hijas con `__manifest__.py`.
- Que el manifest sea legible.
- Que el addon sea `installable`.
- Que la carpeta compartida sea padre de addons, no un addon suelto.
- Que la ruta este en `addons_path`.
- Que no haya conflictos de nombre.
- Que las dependencias Odoo existan o sean instalables.
- Que las dependencias Python y binarias esten disponibles o puedan instalarse.
- Que el estado final sea realmente instalado.

## Diagnosticos

El formulario muestra informacion de diagnostico:

- Ultima operacion.
- Ultimo comando.
- Salida estandar.
- Salida de error.
- Resumen funcional.
- Causa detectada.
- Como resolverlo.
- Diagnostico de rutas.
- Mensajes Odoo detectados.
- Dependencias faltantes.
- Codigo de fallo.
- Estado final del modulo.
- Detalle tecnico.

Esto permite entender errores sin revisar directamente consola o logs completos.

## Control de conflictos

El instalador usa un marcador de origen en los addons expuestos.

Si detecta una carpeta de addon ya existente en la ruta compartida y esa carpeta no fue expuesta desde el repositorio actual, no la sobreescribe. En su lugar informa de un conflicto de nombre para que se revise antes de continuar.

## Seguridad

El modulo crea una categoria y un grupo `OCA Installer User`.

Los menus de instalaciones estan disponibles para usuarios internos.

La configuracion esta limitada a administradores de sistema.

## Archivos relevantes

- `models/oca_repository_installer.py`: logica de clonado, exposicion, validacion, refresco e instalacion.
- `models/res_config_settings.py`: parametros de ajustes.
- `views/oca_repository_installer_views.xml`: vistas del instalador.
- `views/res_config_settings_views.xml`: configuracion.
- `security/security.xml`: categoria, privilegio y grupo.
- `security/ir.model.access.csv`: permisos.
- `static/description/icon.png`: icono.
