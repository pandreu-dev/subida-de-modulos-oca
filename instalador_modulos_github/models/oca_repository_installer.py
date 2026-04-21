import ast
import configparser
import importlib.util
import logging
import os
import re
import shlex
import shutil
import subprocess
import traceback
from urllib.parse import urlparse, urlunparse

import odoo
from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)

PARAM_BRANCH = "instalador_modulos_github.oca_git_branch"
PARAM_CLONE_ROOT = "instalador_modulos_github.oca_clone_root"
PARAM_SHARED_ROOT = "instalador_modulos_github.oca_shared_addons_path"
PARAM_PATH_STRATEGY = "instalador_modulos_github.oca_path_strategy"
PARAM_PERSIST_CONFIG = "instalador_modulos_github.oca_persist_addons_path_to_config"
PARAM_ODOO_CONFIG_PATH = "instalador_modulos_github.oca_odoo_config_path"
PARAM_AUTO_PYTHON = "instalador_modulos_github.oca_auto_install_python_deps"
PARAM_AUTO_BINARY = "instalador_modulos_github.oca_auto_install_binary_deps"
PARAM_PYTHON_COMMAND = "instalador_modulos_github.oca_python_install_command"
PARAM_BINARY_COMMAND = "instalador_modulos_github.oca_binary_install_command"

PYTHON_PACKAGE_HINTS = {
    "Crypto": {"pip": "pycryptodome"},
    "OpenSSL": {"pip": "pyOpenSSL"},
    "PIL": {"pip": "Pillow"},
    "dateutil": {"pip": "python-dateutil"},
    "ldap": {"pip": "python-ldap", "apt": "libsasl2-dev libldap2-dev libssl-dev"},
    "phonenumbers": {"pip": "phonenumbers"},
    "psycopg2": {"pip": "psycopg2-binary", "apt": "libpq-dev"},
    "requests": {"pip": "requests"},
    "stdnum": {"pip": "python-stdnum"},
    "yaml": {"pip": "PyYAML"},
    "zeep": {"pip": "zeep"},
}

BINARY_PACKAGE_HINTS = {
    "gs": "ghostscript",
    "pdftotext": "poppler-utils",
    "tesseract": "tesseract-ocr",
    "wkhtmltoimage": "wkhtmltopdf",
    "wkhtmltopdf": "wkhtmltopdf",
}

ORIGIN_MARKER = ".oca_installer_origin"


class OcaRepositoryInstaller(models.Model):
    _name = "oca.repository.installer"
    _description = "OCA Repository Installer"
    _order = "write_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    repo_url = fields.Char(string="URL del repositorio", required=True)
    branch = fields.Char(string="Rama", default=lambda self: self._default_branch(), required=True)
    repo_name = fields.Char(string="Repositorio", readonly=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("prepared", "Preparado"),
            ("installed", "Instalado"),
            ("error", "Error"),
        ],
        string="Estado",
        default="draft",
        readonly=True,
    )
    clone_path = fields.Char(string="Ruta del clon", readonly=True)
    shared_addons_path = fields.Char(string="Ruta OCA compartida", readonly=True)
    runtime_path_registered = fields.Boolean(string="Ruta registrada en runtime", readonly=True)
    config_path_persisted = fields.Boolean(string="Ruta persistida en config", readonly=True)
    target_addon_id = fields.Many2one(
        "oca.repository.installer.addon",
        string="Addon a instalar",
        domain="[('installer_id', '=', id)]",
    )
    addon_ids = fields.One2many(
        "oca.repository.installer.addon",
        "installer_id",
        string="Addons detectados",
        readonly=True,
    )
    addon_count = fields.Integer(string="Numero de addons", compute="_compute_addon_count")
    last_operation = fields.Char(string="Ultima operacion", readonly=True)
    last_command = fields.Text(string="Ultimo comando", readonly=True)
    last_stdout = fields.Text(string="Salida estandar", readonly=True)
    last_stderr = fields.Text(string="Salida de error", readonly=True)
    diagnostic_summary = fields.Text(string="Resumen", readonly=True)
    resolution_hint = fields.Text(string="Como resolverlo", readonly=True)
    missing_python_dependencies = fields.Text(string="Dependencias Python faltantes", readonly=True)
    missing_binary_dependencies = fields.Text(string="Dependencias binarias faltantes", readonly=True)
    missing_odoo_dependencies = fields.Text(string="Dependencias Odoo faltantes", readonly=True)
    error_details = fields.Text(string="Detalle tecnico", readonly=True)

    @api.depends("repo_name", "repo_url")
    def _compute_name(self):
        for record in self:
            record.name = record.repo_name or record.repo_url or _("Nueva instalacion OCA")

    @api.depends("addon_ids")
    def _compute_addon_count(self):
        for record in self:
            record.addon_count = len(record.addon_ids)

    @api.model
    def _default_branch(self):
        return self._get_param(PARAM_BRANCH, "18.0")

    @api.model
    def _get_param(self, key, default=None):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        if value in (None, False, ""):
            return default
        return value

    @api.model
    def _get_bool_param(self, key, default=False):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        if value in (None, False, ""):
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _get_settings(self):
        return {
            "branch": self._get_param(PARAM_BRANCH, "18.0"),
            "clone_root": self._get_param(PARAM_CLONE_ROOT, "/opt/odoo18/addons/oca/repositories"),
            "shared_root": self._get_param(PARAM_SHARED_ROOT, "/opt/odoo18/addons/oca"),
            "path_strategy": self._get_param(PARAM_PATH_STRATEGY, "symlink"),
            "persist_to_config": self._get_bool_param(PARAM_PERSIST_CONFIG, True),
            "odoo_config_path": self._get_param(PARAM_ODOO_CONFIG_PATH, "/etc/odoo18.conf"),
            "auto_install_python": self._get_bool_param(PARAM_AUTO_PYTHON, False),
            "auto_install_binary": self._get_bool_param(PARAM_AUTO_BINARY, False),
            "python_command": self._get_param(PARAM_PYTHON_COMMAND, False),
            "binary_command": self._get_param(PARAM_BINARY_COMMAND, False),
        }

    def _normalize_repo_url(self, repo_url):
        raw_url = (repo_url or "").strip()
        if not raw_url:
            raise ValidationError(_("Debes indicar una URL del repositorio."))
        if "://" not in raw_url:
            raw_url = "https://%s" % raw_url.lstrip("/")
        parsed = urlparse(raw_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValidationError(_("La URL del repositorio no es valida."))
        clean_path = parsed.path.rstrip("/")
        if not clean_path or clean_path == "/":
            raise ValidationError(_("La URL del repositorio no contiene la ruta del proyecto."))
        if not clean_path.endswith(".git"):
            clean_path = "%s.git" % clean_path
        return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))

    def _repo_name_from_url(self, normalized_url):
        repo_path = urlparse(normalized_url).path.rstrip("/")
        repo_name = repo_path.split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        if not repo_name:
            raise ValidationError(_("No se ha podido deducir el nombre del repositorio."))
        return repo_name

    def _clear_diagnostics(self):
        self.write(
            {
                "last_command": False,
                "last_stdout": False,
                "last_stderr": False,
                "diagnostic_summary": False,
                "resolution_hint": False,
                "missing_python_dependencies": False,
                "missing_binary_dependencies": False,
                "missing_odoo_dependencies": False,
                "error_details": False,
            }
        )

    def _notify(self, message, notification_type="success", title=None):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title or _("Instalador OCA"),
                "message": message,
                "type": notification_type,
                "sticky": notification_type in {"warning", "danger"},
            },
        }

    def _mark_error(
        self,
        summary,
        resolution=None,
        error_details=None,
        missing_python=None,
        missing_binary=None,
        missing_odoo=None,
    ):
        self.write(
            {
                "state": "error",
                "diagnostic_summary": summary,
                "resolution_hint": resolution or False,
                "error_details": error_details or False,
                "missing_python_dependencies": missing_python or False,
                "missing_binary_dependencies": missing_binary or False,
                "missing_odoo_dependencies": missing_odoo or False,
            }
        )

    def _ensure_directory(self, path):
        os.makedirs(path, exist_ok=True)

    def _run_process(self, command, cwd=None):
        command_display = " ".join(shlex.quote(part) for part in command)
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        self.write(
            {
                "last_command": command_display,
                "last_stdout": result.stdout or False,
                "last_stderr": result.stderr or False,
            }
        )
        return result

    def _render_template_command(self, template, packages=None):
        package_text = " ".join(shlex.quote(package_name) for package_name in (packages or []))
        rendered = template.format(packages=package_text)
        return shlex.split(rendered)

    def _read_manifest(self, manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as manifest_file:
            return ast.literal_eval(manifest_file.read())

    def _discover_addons(self, repo_path):
        addons = []
        for entry_name in sorted(os.listdir(repo_path)):
            entry_path = os.path.join(repo_path, entry_name)
            manifest_path = os.path.join(entry_path, "__manifest__.py")
            if not os.path.isdir(entry_path) or not os.path.isfile(manifest_path):
                continue
            manifest = self._read_manifest(manifest_path)
            addons.append(
                {
                    "name": entry_name,
                    "summary": manifest.get("summary") or manifest.get("name") or entry_name,
                    "category": manifest.get("category") or False,
                    "license": manifest.get("license") or False,
                    "dependency_names": ",".join(manifest.get("depends", [])),
                    "python_dependency_names": ",".join(
                        manifest.get("external_dependencies", {}).get("python", [])
                    ),
                    "binary_dependency_names": ",".join(
                        manifest.get("external_dependencies", {}).get("bin", [])
                    ),
                    "source_path": entry_path,
                    "manifest_path": manifest_path,
                }
            )
        return addons

    def _sync_addon_lines(self, addons):
        self.ensure_one()
        existing_by_name = {line.name: line for line in self.addon_ids}
        addon_names = {addon_info["name"] for addon_info in addons}
        for line in self.addon_ids.filtered(lambda addon_line: addon_line.name not in addon_names):
            line.unlink()

        target_name = self.target_addon_id.name
        for addon_info in addons:
            values = {
                "summary": addon_info["summary"],
                "category": addon_info["category"],
                "license": addon_info["license"],
                "dependency_names": addon_info["dependency_names"],
                "python_dependency_names": addon_info["python_dependency_names"],
                "binary_dependency_names": addon_info["binary_dependency_names"],
                "source_path": addon_info["source_path"],
                "manifest_path": addon_info["manifest_path"],
            }
            line = existing_by_name.get(addon_info["name"])
            if line:
                line.write(values)
            else:
                self.env["oca.repository.installer.addon"].create(
                    dict(values, installer_id=self.id, name=addon_info["name"])
                )

        refreshed_lines = self.env["oca.repository.installer.addon"].search(
            [("installer_id", "=", self.id)],
            order="name",
        )
        if target_name and target_name in refreshed_lines.mapped("name"):
            self.target_addon_id = refreshed_lines.filtered(lambda line: line.name == target_name)[:1]
        elif len(refreshed_lines) == 1:
            self.target_addon_id = refreshed_lines[:1]
        else:
            self.target_addon_id = False

    def _refresh_addon_odoo_states(self):
        self.ensure_one()
        module_model = self.env["ir.module.module"].sudo()
        modules = module_model.search([("name", "in", self.addon_ids.mapped("name"))])
        module_by_name = {module.name: module for module in modules}
        for addon in self.addon_ids:
            module_record = module_by_name.get(addon.name)
            addon.write(
                {
                    "available_in_odoo": bool(module_record),
                    "installed_in_odoo": bool(module_record and module_record.state == "installed"),
                    "odoo_module_state": module_record.state if module_record else "not_found",
                    "status_message": self._module_status_message(module_record),
                }
            )

    def _module_status_message(self, module_record):
        if not module_record:
            return _("No visible todavia en Apps")
        if module_record.state == "installed":
            return _("Instalado")
        if module_record.state in {"to install", "to upgrade"}:
            return _("Pendiente")
        return _("Disponible")

    def _ensure_runtime_addons_path(self, addons_path):
        normalized_path = os.path.abspath(addons_path)
        raw_value = tools.config.get("addons_path") or ""
        current_paths = [
            os.path.abspath(path.strip())
            for path in str(raw_value).split(",")
            if path and path.strip()
        ]
        if normalized_path not in current_paths:
            current_paths.append(normalized_path)
            tools.config["addons_path"] = ",".join(current_paths)

        try:
            from odoo.modules import module as module_loader

            if hasattr(module_loader, "ad_paths"):
                module_loader.ad_paths = current_paths
            if hasattr(module_loader, "initialize_sys_path"):
                module_loader.initialize_sys_path()
        except Exception:
            _logger.exception("No se pudo refrescar la cache runtime de addons_path")

        try:
            addons_namespace = getattr(odoo, "addons", None)
            namespace_path = getattr(addons_namespace, "__path__", None)
            if namespace_path is not None:
                normalized_runtime_paths = {os.path.abspath(path) for path in namespace_path}
                if normalized_path not in normalized_runtime_paths and hasattr(namespace_path, "append"):
                    namespace_path.append(normalized_path)
        except Exception:
            _logger.exception("No se pudo registrar la ruta runtime en odoo.addons.__path__")

        runtime_registered = normalized_path in {
            os.path.abspath(path.strip())
            for path in str(tools.config.get("addons_path") or "").split(",")
            if path and path.strip()
        }
        return runtime_registered

    def _persist_addons_path_to_config(self, addons_path, settings):
        config_path = settings.get("odoo_config_path")
        if not settings.get("persist_to_config") or not config_path:
            return False, False, False
        if not os.path.isfile(config_path):
            return False, False, _("La ruta del fichero de configuracion no existe: %s") % config_path

        try:
            parser = configparser.RawConfigParser()
            parser.read(config_path, encoding="utf-8")
            if not parser.has_section("options"):
                parser.add_section("options")

            current_value = parser.get("options", "addons_path", fallback="")
            current_paths = [path.strip() for path in current_value.split(",") if path.strip()]
            normalized_requested = os.path.abspath(addons_path)
            normalized_current = {os.path.abspath(path) for path in current_paths}
            already_present = normalized_requested in normalized_current
            if not already_present:
                current_paths.append(addons_path)
                parser.set("options", "addons_path", ",".join(current_paths))
                with open(config_path, "w", encoding="utf-8") as config_file:
                    parser.write(config_file)
                return True, True, False
            return True, False, False
        except Exception as error:
            _logger.exception("No se pudo persistir addons_path en %s", config_path)
            return False, False, _(
                "No se pudo escribir en %s. El repo puede funcionar ahora en runtime, pero conviene revisar permisos."
            ) % config_path

    def _safe_remove_path(self, target_path, managed_root):
        abs_target = os.path.abspath(target_path)
        abs_root = os.path.abspath(managed_root)
        if os.path.commonpath([abs_target, abs_root]) != abs_root:
            raise UserError(_("La ruta %s esta fuera de la carpeta gestionada.") % target_path)
        if not os.path.lexists(target_path):
            return
        if os.path.islink(target_path) or os.path.isfile(target_path):
            os.unlink(target_path)
        elif os.path.isdir(target_path):
            shutil.rmtree(target_path)

    def _read_origin_marker(self, target_path):
        marker_path = os.path.join(target_path, ORIGIN_MARKER)
        if not os.path.isfile(marker_path):
            return False
        with open(marker_path, "r", encoding="utf-8") as marker_file:
            return marker_file.read().strip()

    def _write_origin_marker(self, target_path, source_path):
        marker_path = os.path.join(target_path, ORIGIN_MARKER)
        with open(marker_path, "w", encoding="utf-8") as marker_file:
            marker_file.write(os.path.realpath(source_path))

    def _expose_addon(self, addon_path, shared_root, strategy):
        addon_name = os.path.basename(addon_path)
        target_path = os.path.join(shared_root, addon_name)
        if os.path.lexists(target_path):
            same_target = False
            if os.path.islink(target_path):
                same_target = os.path.realpath(target_path) == os.path.realpath(addon_path)
            elif os.path.isdir(target_path):
                same_target = self._read_origin_marker(target_path) == os.path.realpath(addon_path)
            if same_target:
                self._safe_remove_path(target_path, shared_root)
            else:
                raise UserError(
                    _(
                        "Ya existe un addon llamado %s en la carpeta OCA compartida y no parece pertenecer a este repositorio. Revisa el conflicto antes de continuar."
                    )
                    % addon_name
                )

        if strategy == "symlink":
            try:
                os.symlink(addon_path, target_path, target_is_directory=True)
                return "symlink"
            except OSError:
                _logger.exception("No se pudo crear el enlace simbolico para %s", addon_name)

        shutil.copytree(addon_path, target_path)
        self._write_origin_marker(target_path, addon_path)
        return "copy"

    def _python_package_name(self, import_name):
        root_name = import_name.split(".")[0]
        return PYTHON_PACKAGE_HINTS.get(root_name, {}).get("pip", root_name)

    def _binary_package_name(self, binary_name):
        return BINARY_PACKAGE_HINTS.get(binary_name, binary_name)

    def _collect_preflight(self, addon_line):
        module_model = self.env["ir.module.module"].sudo()
        dependency_names = [
            dependency_name
            for dependency_name in addon_line._split_csv(addon_line.dependency_names)
            if dependency_name != "base"
        ]
        module_records = module_model.search([("name", "in", dependency_names)])
        module_by_name = {module.name: module for module in module_records}

        unavailable_odoo = [name for name in dependency_names if name not in module_by_name]
        installable_odoo = [
            name
            for name in dependency_names
            if name in module_by_name and module_by_name[name].state != "installed"
        ]
        missing_python = [
            dependency_name
            for dependency_name in addon_line._split_csv(addon_line.python_dependency_names)
            if importlib.util.find_spec(dependency_name) is None
        ]
        missing_binary = [
            dependency_name
            for dependency_name in addon_line._split_csv(addon_line.binary_dependency_names)
            if shutil.which(dependency_name) is None
        ]

        return {
            "missing_python": missing_python,
            "missing_binary": missing_binary,
            "missing_odoo_unavailable": unavailable_odoo,
            "missing_odoo_installable": installable_odoo,
        }

    def _attempt_auto_install_dependencies(self, addon_line, settings):
        preflight = self._collect_preflight(addon_line)
        notes = []

        if preflight["missing_python"] and settings.get("auto_install_python") and settings.get("python_command"):
            packages = [self._python_package_name(name) for name in preflight["missing_python"]]
            result = self._run_process(self._render_template_command(settings["python_command"], packages))
            if result.returncode != 0:
                notes.append(
                    _("No se han podido instalar automaticamente las dependencias Python. Revisa stderr.")
                )

        if preflight["missing_binary"] and settings.get("auto_install_binary") and settings.get("binary_command"):
            packages = [self._binary_package_name(name) for name in preflight["missing_binary"]]
            result = self._run_process(self._render_template_command(settings["binary_command"], packages))
            if result.returncode != 0:
                notes.append(
                    _("No se han podido instalar automaticamente las dependencias del sistema. Revisa stderr.")
                )

        return self._collect_preflight(addon_line), notes

    def _build_dependency_resolution(self, addon_line, preflight):
        resolution_lines = []
        missing_python_lines = []
        missing_binary_lines = []
        missing_odoo_lines = []
        has_blocking_issues = False

        for import_name in preflight["missing_python"]:
            package_name = self._python_package_name(import_name)
            hint = _("Falta la libreria Python '%s'. Prueba con pip install %s.") % (
                import_name,
                package_name,
            )
            missing_python_lines.append(hint)
            resolution_lines.append(hint)
            has_blocking_issues = True

        for binary_name in preflight["missing_binary"]:
            package_name = self._binary_package_name(binary_name)
            hint = _("Falta el binario '%s'. En Debian/Ubuntu suele venir en el paquete %s.") % (
                binary_name,
                package_name,
            )
            missing_binary_lines.append(hint)
            resolution_lines.append(hint)
            has_blocking_issues = True

        for module_name in preflight["missing_odoo_unavailable"]:
            hint = _(
                "No se encuentra el addon Odoo '%s'. Busca ese nombre tecnico dentro de OCA u otro repositorio compatible."
            ) % module_name
            missing_odoo_lines.append(hint)
            resolution_lines.append(hint)
            has_blocking_issues = True

        if preflight["missing_odoo_installable"]:
            resolution_lines.append(
                _(
                    "Las dependencias Odoo %s ya estan disponibles en Apps y Odoo intentara instalarlas automaticamente."
                )
                % ", ".join(preflight["missing_odoo_installable"])
            )

        if has_blocking_issues:
            summary = _("El addon %s no esta listo para instalarse.") % addon_line.name
        else:
            summary = _("El addon %s ha superado la validacion previa.") % addon_line.name

        return {
            "summary": summary,
            "resolution": "\n".join(resolution_lines) or False,
            "missing_python": "\n".join(missing_python_lines) or False,
            "missing_binary": "\n".join(missing_binary_lines) or False,
            "missing_odoo": "\n".join(missing_odoo_lines) or False,
        }

    def _extract_missing_python_from_text(self, text):
        candidates = set()
        for match in re.findall(r"No module named ['\"]([^'\"]+)['\"]", text or ""):
            candidates.add(match.split(".")[0])
        return sorted(candidates)

    def _extract_missing_odoo_from_text(self, text):
        candidates = set()
        patterns = [
            r"depends on module ['\"]([^'\"]+)['\"]",
            r"Unmet dependencies:\s*\[([^\]]+)\]",
            r"Missing dependencies:\s*\[([^\]]+)\]",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, text or ""):
                raw_names = [name.strip(" '\"") for name in match.split(",")]
                for module_name in raw_names:
                    if module_name:
                        candidates.add(module_name)
        return sorted(candidates)

    def _build_exception_report(self, error, addon_line=False):
        trace_text = traceback.format_exc()
        error_text = "%s\n%s" % (tools.ustr(error), trace_text)
        missing_python = self._extract_missing_python_from_text(error_text)
        missing_odoo = self._extract_missing_odoo_from_text(error_text)

        resolution_lines = []
        if addon_line:
            summary = _("La instalacion del addon %s ha fallado.") % addon_line.name
        else:
            summary = _("La operacion ha fallado.")

        if missing_python:
            for import_name in missing_python:
                resolution_lines.append(
                    _("Falta la libreria Python '%s'. Prueba con pip install %s.") % (
                        import_name,
                        self._python_package_name(import_name),
                    )
                )

        if missing_odoo:
            for module_name in missing_odoo:
                resolution_lines.append(
                    _(
                        "El modulo depende del addon Odoo '%s'. Comprueba si existe en otro repo OCA y anadelo antes de instalar."
                    )
                    % module_name
                )

        if not resolution_lines:
            resolution_lines.append(
                _("Revisa el detalle tecnico y stderr; ahi suele aparecer la causa exacta del fallo.")
            )

        return {
            "summary": summary,
            "resolution": "\n".join(resolution_lines),
            "missing_python": "\n".join(
                _("Falta la libreria Python '%s'.") % name for name in missing_python
            )
            or False,
            "missing_binary": False,
            "missing_odoo": "\n".join(
                _("Falta el addon Odoo '%s'.") % name for name in missing_odoo
            )
            or False,
            "details": error_text,
        }

    def _prepare_repository(self):
        self.ensure_one()
        settings = self._get_settings()
        normalized_url = self._normalize_repo_url(self.repo_url)
        repo_name = self._repo_name_from_url(normalized_url)
        branch = self.branch or settings["branch"]
        repo_path = os.path.join(settings["clone_root"], repo_name)
        shared_root = settings["shared_root"]

        self._clear_diagnostics()
        self.write(
            {
                "branch": branch,
                "repo_name": repo_name,
                "clone_path": repo_path,
                "shared_addons_path": shared_root,
                "last_operation": "prepare_repository",
            }
        )

        try:
            self._ensure_directory(settings["clone_root"])
            self._ensure_directory(shared_root)

            if os.path.isdir(repo_path):
                if not os.path.isdir(os.path.join(repo_path, ".git")):
                    raise UserError(
                        _("La ruta %s ya existe, pero no parece un repositorio git valido.") % repo_path
                    )
                result = self._run_process(["git", "-C", repo_path, "pull", "--ff-only", "origin", branch])
            else:
                result = self._run_process(
                    ["git", "clone", "-b", branch, "--depth", "1", normalized_url, repo_path]
                )

            if result.returncode != 0:
                self._mark_error(
                    _("No se ha podido descargar o actualizar el repositorio."),
                    resolution=_("Comprueba la URL, la conectividad del servidor y los permisos de escritura."),
                    error_details=(result.stderr or result.stdout or False),
                )
                return False, self.diagnostic_summary

            addons = self._discover_addons(repo_path)
            if not addons:
                self._mark_error(
                    _("El repositorio se ha descargado, pero no se han detectado addons Odoo validos."),
                    resolution=_(
                        "Asegurate de que la rama elegida contiene carpetas hijas con __manifest__.py."
                    ),
                )
                return False, self.diagnostic_summary

            exposure_notes = []
            for addon_info in addons:
                mode_used = self._expose_addon(
                    addon_info["source_path"],
                    shared_root,
                    settings["path_strategy"],
                )
                if mode_used == "copy":
                    exposure_notes.append(
                        _("Se ha usado copia en lugar de enlace simbolico para %s.") % addon_info["name"]
                    )

            runtime_registered = self._ensure_runtime_addons_path(shared_root)
            config_registered, _, config_note = self._persist_addons_path_to_config(shared_root, settings)
            if config_note:
                exposure_notes.append(config_note)

            self.env["ir.module.module"].sudo().update_list()
            self._sync_addon_lines(addons)
            self._refresh_addon_odoo_states()

            resolution = exposure_notes and "\n".join(exposure_notes) or _(
                "Selecciona un addon del repositorio y pulsa instalar."
            )
            message = _("Repositorio preparado correctamente. Addons detectados: %s.") % len(addons)
            self.write(
                {
                    "state": "prepared",
                    "runtime_path_registered": runtime_registered,
                    "config_path_persisted": config_registered,
                    "diagnostic_summary": message,
                    "resolution_hint": resolution,
                }
            )
            return True, message
        except (UserError, ValidationError) as error:
            message = tools.ustr(error)
            self._mark_error(message, error_details=message)
            return False, message
        except Exception as error:
            report = self._build_exception_report(error)
            self._mark_error(
                report["summary"],
                resolution=report["resolution"],
                error_details=report["details"],
                missing_python=report["missing_python"],
                missing_binary=report["missing_binary"],
                missing_odoo=report["missing_odoo"],
            )
            return False, report["summary"]

    def _install_addon(self, addon_line):
        self.ensure_one()
        settings = self._get_settings()
        self._clear_diagnostics()
        self.write({"last_operation": "install_addon", "target_addon_id": addon_line.id})

        runtime_registered = self._ensure_runtime_addons_path(self.shared_addons_path or settings["shared_root"])
        self.write({"runtime_path_registered": runtime_registered})
        self.env["ir.module.module"].sudo().update_list()
        self._refresh_addon_odoo_states()

        preflight, auto_install_notes = self._attempt_auto_install_dependencies(addon_line, settings)
        report = self._build_dependency_resolution(addon_line, preflight)
        if preflight["missing_python"] or preflight["missing_binary"] or preflight["missing_odoo_unavailable"]:
            resolution = report["resolution"] or False
            if auto_install_notes:
                resolution = "\n".join(auto_install_notes + [resolution] if resolution else auto_install_notes)
            self._mark_error(
                report["summary"],
                resolution=resolution,
                missing_python=report["missing_python"],
                missing_binary=report["missing_binary"],
                missing_odoo=report["missing_odoo"],
            )
            addon_line.write({"install_result": report["summary"]})
            return False, report["summary"]

        module_record = self.env["ir.module.module"].sudo().search([("name", "=", addon_line.name)], limit=1)
        if not module_record:
            summary = _("Odoo todavia no ve el addon %s en Apps.") % addon_line.name
            resolution = _(
                "Revisa que la ruta compartida exista, que este en addons_path y vuelve a pulsar refrescar."
            )
            self._mark_error(summary, resolution=resolution)
            addon_line.write({"install_result": summary})
            return False, summary

        if module_record.state == "installed":
            summary = _("El addon %s ya estaba instalado.") % addon_line.name
            self.write(
                {
                    "state": "installed",
                    "diagnostic_summary": summary,
                    "resolution_hint": _("No hace falta ninguna accion adicional."),
                }
            )
            addon_line.write({"install_result": summary})
            self._refresh_addon_odoo_states()
            return True, summary

        try:
            module_record.button_immediate_install()
            self._refresh_addon_odoo_states()
            summary = _("El addon %s se ha instalado correctamente.") % addon_line.name
            resolution = _(
                "Si el addon tenia dependencias Odoo disponibles, Odoo tambien las habra instalado."
            )
            self.write(
                {
                    "state": "installed",
                    "diagnostic_summary": summary,
                    "resolution_hint": resolution,
                }
            )
            addon_line.write({"install_result": summary})
            return True, summary
        except (UserError, ValidationError) as error:
            message = tools.ustr(error)
            self._mark_error(message, error_details=message)
            addon_line.write({"install_result": message})
            return False, message
        except Exception as error:
            report = self._build_exception_report(error, addon_line=addon_line)
            self._mark_error(
                report["summary"],
                resolution=report["resolution"],
                error_details=report["details"],
                missing_python=report["missing_python"],
                missing_binary=report["missing_binary"],
                missing_odoo=report["missing_odoo"],
            )
            addon_line.write({"install_result": report["summary"]})
            return False, report["summary"]

    def action_prepare_repository(self):
        self.ensure_one()
        ok, message = self._prepare_repository()
        return self._notify(message, "success" if ok else "warning")

    def action_refresh_available_modules(self):
        self.ensure_one()
        try:
            shared_root = self.shared_addons_path or self._get_settings()["shared_root"]
            runtime_registered = self._ensure_runtime_addons_path(shared_root)
            self.env["ir.module.module"].sudo().update_list()
            self._refresh_addon_odoo_states()
            self.write(
                {
                    "state": "prepared" if self.state != "installed" else self.state,
                    "runtime_path_registered": runtime_registered,
                    "diagnostic_summary": _("La lista de Apps se ha refrescado correctamente."),
                    "resolution_hint": _("Ahora puedes instalar cualquier addon detectado."),
                    "last_operation": "refresh_modules",
                }
            )
            return self._notify(_("Lista de Apps actualizada."))
        except (UserError, ValidationError) as error:
            message = tools.ustr(error)
            self._mark_error(message, error_details=message)
            return self._notify(message, "warning")
        except Exception as error:
            report = self._build_exception_report(error)
            self._mark_error(
                report["summary"],
                resolution=report["resolution"],
                error_details=report["details"],
                missing_python=report["missing_python"],
                missing_binary=report["missing_binary"],
                missing_odoo=report["missing_odoo"],
            )
            return self._notify(report["summary"], "warning")

    def action_install_selected_addon(self):
        self.ensure_one()
        if not self.addon_ids:
            ok, message = self._prepare_repository()
            if not ok:
                return self._notify(message, "warning")

        addon_line = self.target_addon_id
        if not addon_line and len(self.addon_ids) == 1:
            addon_line = self.addon_ids[:1]
            self.target_addon_id = addon_line

        if not addon_line:
            raise UserError(
                _("Selecciona el addon concreto a instalar. Este repositorio contiene varios addons.")
            )

        ok, message = self._install_addon(addon_line)
        return self._notify(message, "success" if ok else "warning")


class OcaRepositoryInstallerAddon(models.Model):
    _name = "oca.repository.installer.addon"
    _description = "Detected OCA Addon"
    _order = "name"

    installer_id = fields.Many2one("oca.repository.installer", required=True, ondelete="cascade")
    name = fields.Char(string="Addon", required=True, readonly=True)
    summary = fields.Char(string="Resumen", readonly=True)
    category = fields.Char(string="Categoria", readonly=True)
    license = fields.Char(string="Licencia", readonly=True)
    dependency_names = fields.Char(string="Dependencias Odoo", readonly=True)
    python_dependency_names = fields.Char(string="Dependencias Python", readonly=True)
    binary_dependency_names = fields.Char(string="Dependencias binarias", readonly=True)
    source_path = fields.Char(string="Ruta fuente", readonly=True)
    manifest_path = fields.Char(string="Manifest", readonly=True)
    available_in_odoo = fields.Boolean(string="Visible en Apps", readonly=True)
    installed_in_odoo = fields.Boolean(string="Instalado", readonly=True)
    odoo_module_state = fields.Char(string="Estado Odoo", readonly=True)
    status_message = fields.Char(string="Estado funcional", readonly=True)
    install_result = fields.Text(string="Ultimo resultado", readonly=True)

    @api.model
    def _split_csv(self, csv_text):
        return [item.strip() for item in (csv_text or "").split(",") if item and item.strip()]

    def action_install_addon(self):
        self.ensure_one()
        self.installer_id.target_addon_id = self
        return self.installer_id.action_install_selected_addon()
