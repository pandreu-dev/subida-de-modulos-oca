import ast
import configparser
import importlib.util
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import traceback
from contextlib import contextmanager
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

KNOWN_LOG_PATTERNS = (
    ("not installable, skipped", "not_installable"),
    ("no manifest file found", "no_manifest_found"),
    ("some modules are not loaded", "modules_not_loaded"),
    ("some modules have inconsistent states", "modules_inconsistent"),
)

ORIGIN_MARKER = ".oca_installer_origin"


class OdooLogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.INFO)
        self.messages = []

    def emit(self, record):
        if not record.name.startswith("odoo"):
            return
        self.messages.append(self.format(record))


class OcaRepositoryInstaller(models.Model):
    _name = "oca.repository.installer"
    _description = "OCA Repository Installer"
    _order = "write_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    repo_url = fields.Char(string="URL del repositorio", required=True)
    normalized_repo_url = fields.Char(string="URL normalizada", readonly=True)
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
    addons_path_to_use = fields.Char(string="Ruta usada en addons_path", readonly=True)
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
    diagnostic_summary = fields.Text(string="Resumen funcional", readonly=True)
    detected_cause = fields.Text(string="Causa detectada", readonly=True)
    resolution_hint = fields.Text(string="Como resolverlo", readonly=True)
    path_diagnostics = fields.Text(string="Diagnostico de rutas", readonly=True)
    odoo_log_highlights = fields.Text(string="Mensajes Odoo detectados", readonly=True)
    missing_python_dependencies = fields.Text(string="Dependencias Python faltantes", readonly=True)
    missing_binary_dependencies = fields.Text(string="Dependencias binarias faltantes", readonly=True)
    missing_odoo_dependencies = fields.Text(string="Dependencias Odoo faltantes", readonly=True)
    failure_code = fields.Char(string="Codigo de fallo", readonly=True)
    final_module_state = fields.Char(string="Estado final del modulo", readonly=True)
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

    def _yesno(self, value):
        return _("Si") if value else _("No")

    def _split_text_lines(self, text):
        return [line.strip() for line in tools.ustr(text or "").splitlines() if line and line.strip()]

    def _unique_lines(self, lines):
        ordered = []
        seen = set()
        for line in lines or []:
            text = tools.ustr(line).strip()
            if not text or text in seen:
                continue
            ordered.append(text)
            seen.add(text)
        return ordered

    def _format_user_message(self, summary=None, detected_cause=None, resolution=None):
        parts = [part for part in [summary, detected_cause and _("Causa detectada:\n%s") % detected_cause, resolution and _("Como resolverlo:\n%s") % resolution] if part]
        return "\n\n".join(parts)

    def _raise_functional_error(self, summary=None, detected_cause=None, resolution=None):
        raise UserError(self._format_user_message(summary, detected_cause, resolution))

    def _exception_summary(self, error):
        message = tools.ustr(error).strip()
        return "%s: %s" % (error.__class__.__name__, message or _("sin detalle adicional"))

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
                "detected_cause": False,
                "resolution_hint": False,
                "path_diagnostics": False,
                "odoo_log_highlights": False,
                "missing_python_dependencies": False,
                "missing_binary_dependencies": False,
                "missing_odoo_dependencies": False,
                "failure_code": False,
                "final_module_state": False,
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
        detected_cause=None,
        error_details=None,
        path_diagnostics=None,
        odoo_log_highlights=None,
        missing_python=None,
        missing_binary=None,
        missing_odoo=None,
        failure_code=None,
        final_module_state=None,
    ):
        self.write(
            {
                "state": "error",
                "diagnostic_summary": summary,
                "detected_cause": detected_cause or False,
                "resolution_hint": resolution or False,
                "path_diagnostics": path_diagnostics or False,
                "odoo_log_highlights": odoo_log_highlights or False,
                "error_details": error_details or False,
                "missing_python_dependencies": missing_python or False,
                "missing_binary_dependencies": missing_binary or False,
                "missing_odoo_dependencies": missing_odoo or False,
                "failure_code": failure_code or False,
                "final_module_state": final_module_state or False,
            }
        )

    def _mark_success(
        self,
        state,
        summary,
        resolution=None,
        detected_cause=None,
        path_diagnostics=None,
        odoo_log_highlights=None,
        final_module_state=None,
        failure_code=None,
    ):
        self.write(
            {
                "state": state,
                "diagnostic_summary": summary,
                "detected_cause": detected_cause or False,
                "resolution_hint": resolution or False,
                "path_diagnostics": path_diagnostics or False,
                "odoo_log_highlights": odoo_log_highlights or False,
                "failure_code": failure_code or False,
                "final_module_state": final_module_state or False,
            }
        )

    def _ensure_directory(self, path):
        os.makedirs(path, exist_ok=True)

    def _run_process(self, command, cwd=None):
        command_display = " ".join(shlex.quote(part) for part in command)
        _logger.info("Instalador OCA: ejecutando comando externo: %s", command_display)
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        _logger.info(
            "Instalador OCA: comando finalizado con codigo %s: %s",
            result.returncode,
            command_display,
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
            manifest = ast.literal_eval(manifest_file.read())
        if not isinstance(manifest, dict):
            raise ValueError(_("El manifest %s no define un diccionario Python valido.") % manifest_path)
        return manifest

    def _read_manifest_safe(self, manifest_path):
        result = {"manifest": False, "manifest_readable": False, "manifest_error": False}
        if not manifest_path or not os.path.isfile(manifest_path):
            return result
        try:
            manifest = self._read_manifest(manifest_path)
            result.update({"manifest": manifest, "manifest_readable": True})
        except Exception as error:
            result["manifest_error"] = tools.ustr(error)
        return result

    def _read_config_addons_paths(self, settings=None):
        settings = settings or self._get_settings()
        config_path = settings.get("odoo_config_path")
        if not config_path or not os.path.isfile(config_path):
            return []
        try:
            parser = configparser.RawConfigParser()
            parser.read(config_path, encoding="utf-8")
            raw_value = parser.get("options", "addons_path", fallback="")
        except Exception:
            _logger.exception(
                "Instalador OCA: no se pudo leer addons_path del fichero %s",
                config_path,
            )
            return []
        return [
            os.path.abspath(path.strip())
            for path in raw_value.split(",")
            if path and path.strip()
        ]

    def _inspect_addon_path(self, addon_path, expected_name=None):
        normalized_path = os.path.abspath(addon_path) if addon_path else False
        folder_name = os.path.basename(normalized_path) if normalized_path else False
        addon_name = expected_name or folder_name or False
        manifest_path = os.path.join(normalized_path, "__manifest__.py") if normalized_path else False
        disk_path_exists = bool(normalized_path and os.path.isdir(normalized_path))
        manifest_exists = bool(manifest_path and os.path.isfile(manifest_path))
        manifest_info = self._read_manifest_safe(manifest_path) if manifest_exists else {"manifest": False, "manifest_readable": False, "manifest_error": False}
        manifest = manifest_info["manifest"] or {}
        manifest_installable = bool(manifest.get("installable", True)) if manifest_info["manifest_readable"] else False
        return {
            "name": addon_name,
            "path": normalized_path,
            "manifest_path": manifest_path,
            "disk_path_exists": disk_path_exists,
            "manifest_exists": manifest_exists,
            "manifest_readable": manifest_info["manifest_readable"],
            "manifest_installable": manifest_installable,
            "technical_name_matches_path": bool(not addon_name or addon_name == folder_name),
            "manifest_error": manifest_info["manifest_error"] or False,
            "summary": manifest.get("summary") or manifest.get("name") or addon_name,
            "category": manifest.get("category") or False,
            "license": manifest.get("license") or False,
            "dependency_names": ",".join(manifest.get("depends", [])),
            "python_dependency_names": ",".join(
                manifest.get("external_dependencies", {}).get("python", [])
            ),
            "binary_dependency_names": ",".join(
                manifest.get("external_dependencies", {}).get("bin", [])
            ),
        }

    def _find_nested_manifest_dirs(self, root_path, max_depth=3):
        found = []
        if not root_path or not os.path.isdir(root_path):
            return found
        for current_root, dirnames, filenames in os.walk(root_path):
            rel_path = os.path.relpath(current_root, root_path)
            depth = 0 if rel_path == "." else rel_path.count(os.sep) + 1
            if depth > max_depth:
                dirnames[:] = []
                continue
            if rel_path != "." and "__manifest__.py" in filenames:
                found.append(rel_path)
        return found

    def _discover_addons(self, repo_path):
        addons = []
        issues = []
        if not os.path.isdir(repo_path):
            return addons, [_("La ruta clonada no existe o no es una carpeta: %s") % repo_path]

        entry_names = sorted(os.listdir(repo_path))
        for entry_name in entry_names:
            entry_path = os.path.join(repo_path, entry_name)
            if not os.path.isdir(entry_path) or entry_name.startswith("."):
                continue
            inspection = self._inspect_addon_path(entry_path, expected_name=entry_name)
            if inspection["manifest_exists"] and inspection["manifest_readable"]:
                addons.append(inspection)
                if not inspection["manifest_installable"]:
                    issues.append(_("El addon %s existe, pero installable es False.") % entry_name)
            elif inspection["manifest_exists"] and not inspection["manifest_readable"]:
                issues.append(
                    _("El manifest del addon %s es invalido o no se puede parsear: %s")
                    % (entry_name, inspection["manifest_error"])
                )

        if not addons:
            nested_manifests = self._find_nested_manifest_dirs(repo_path)
            if nested_manifests:
                issues.append(
                    _(
                        "El repositorio no expone addons Odoo en su primer nivel. Se han encontrado manifests en subcarpetas: %s"
                    )
                    % ", ".join(nested_manifests[:10])
                )
            else:
                issues.append(
                    _("El repositorio no contiene carpetas hijas validas con __manifest__.py en su primer nivel.")
                )

        return addons, issues

    def _sync_addon_lines(self, addons):
        self.ensure_one()
        existing_by_name = {line.name: line for line in self.addon_ids}
        addon_names = {addon_info["name"] for addon_info in addons}
        shared_root = self.addons_path_to_use or self.shared_addons_path or self._get_settings()["shared_root"]

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
                "source_path": addon_info["path"],
                "manifest_path": addon_info["manifest_path"],
                "disk_path_exists": addon_info["disk_path_exists"],
                "manifest_exists": addon_info["manifest_exists"],
                "manifest_readable": addon_info["manifest_readable"],
                "manifest_installable": addon_info["manifest_installable"],
                "technical_name_matches_path": addon_info["technical_name_matches_path"],
                "manifest_error": addon_info["manifest_error"],
                "shared_path": os.path.join(shared_root, addon_info["name"]) if shared_root else False,
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

    def _module_status_message(self, module_record):
        if not module_record:
            return _("No visible todavia en Apps")
        if module_record.state == "installed":
            return _("Instalado")
        if module_record.state == "uninstallable":
            return _("Odoo lo considera no instalable")
        if module_record.state in {"to install", "to upgrade"}:
            return _("Pendiente")
        return _("Disponible")

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

    def _runtime_addons_paths(self):
        raw_value = tools.config.get("addons_path") or ""
        return [
            os.path.abspath(path.strip())
            for path in str(raw_value).split(",")
            if path and path.strip()
        ]

    def _path_in_runtime(self, addons_path):
        normalized_path = os.path.abspath(addons_path)
        return normalized_path in self._runtime_addons_paths()

    def _addons_path_health_report(self, settings=None):
        settings = settings or self._get_settings()
        shared_root = os.path.abspath(
            self.addons_path_to_use or self.shared_addons_path or settings["shared_root"]
        )
        runtime_paths = self._runtime_addons_paths()
        config_paths = self._read_config_addons_paths(settings)
        runtime_nested = [
            path
            for path in runtime_paths
            if path != shared_root and self._is_path_within(path, shared_root)
        ]
        config_nested = [
            path
            for path in config_paths
            if path != shared_root and self._is_path_within(path, shared_root)
        ]

        cause_lines = []
        resolution_lines = []
        diagnostic_lines = [
            _("addons_path runtime actual: %s")
            % (", ".join(runtime_paths) or _("vacio")),
            _("addons_path detectado en config: %s")
            % (", ".join(config_paths) or _("no legible o vacio")),
        ]

        if runtime_nested:
            cause_lines.append(
                _(
                    "He detectado rutas hijas dentro de la carpeta OCA compartida en addons_path runtime: %s"
                )
                % ", ".join(runtime_nested[:10])
            )
        if config_nested:
            cause_lines.append(
                _(
                    "He detectado rutas hijas dentro de la carpeta OCA compartida en el fichero de configuracion: %s"
                )
                % ", ".join(config_nested[:10])
            )
        if runtime_nested or config_nested:
            resolution_lines.extend(
                [
                    _("Deja una sola ruta OCA padre en addons_path: %s") % shared_root,
                    _(
                        "Elimina rutas especificas de repositorio o de la carpeta repositories, por ejemplo %s"
                    )
                    % settings["clone_root"],
                ]
            )

        return {
            "cause_lines": self._unique_lines(cause_lines),
            "resolution_lines": self._unique_lines(resolution_lines),
            "diagnostic_lines": diagnostic_lines,
        }

    @contextmanager
    def _capture_odoo_logs(self):
        handler = OdooLogCaptureHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            yield handler
        finally:
            root_logger.removeHandler(handler)

    def _extract_log_signals(self, log_messages):
        matched_lines = []
        cause_lines = []
        resolution_lines = []
        codes = []
        for message in self._unique_lines(log_messages):
            lowered = message.lower()
            for pattern, code in KNOWN_LOG_PATTERNS:
                if pattern not in lowered:
                    continue
                matched_lines.append(message)
                codes.append(code)
                if code == "not_installable":
                    cause_lines.append(
                        _("Odoo ha escrito 'not installable, skipped' durante la carga del modulo.")
                    )
                    resolution_lines.append(
                        _("Revisa installable = True, el manifest y que la ruta expuesta sea la carpeta padre correcta del addon.")
                    )
                elif code == "no_manifest_found":
                    cause_lines.append(
                        _("Odoo ha escrito 'no manifest file found', asi que no encuentra __manifest__.py en la ruta cargada.")
                    )
                    resolution_lines.append(
                        _("Comprueba que la carpeta compartida contiene una subcarpeta por addon y que dentro exista __manifest__.py.")
                    )
                elif code == "modules_not_loaded":
                    cause_lines.append(
                        _("Odoo ha informado de que algunos modulos no se han cargado.")
                    )
                    resolution_lines.append(
                        _("Revisa las dependencias y los errores de carga del registro antes de reintentar la instalacion.")
                    )
                elif code == "modules_inconsistent":
                    cause_lines.append(
                        _("Odoo ha informado de estados inconsistentes en algunos modulos.")
                    )
                    resolution_lines.append(
                        _("Comprueba modulos pendientes, dependencias y vuelve a refrescar Apps.")
                    )
        return {
            "raw": "\n".join(self._unique_lines(matched_lines)) or False,
            "cause": "\n".join(self._unique_lines(cause_lines)) or False,
            "resolution": "\n".join(self._unique_lines(resolution_lines)) or False,
            "codes": self._unique_lines(codes),
        }

    def _update_module_list(self):
        _logger.info("Instalador OCA: antes de update_list() para %s", self.repo_url)
        with self.env.cr.savepoint():
            with self._capture_odoo_logs() as capture:
                self.env["ir.module.module"].sudo().update_list()
        _logger.info("Instalador OCA: despues de update_list() para %s", self.repo_url)
        return capture.messages

    def _safe_update_module_list(self):
        capture = False
        try:
            _logger.info("Instalador OCA: antes de update_list() para %s", self.repo_url)
            with self.env.cr.savepoint():
                with self._capture_odoo_logs() as capture:
                    self.env["ir.module.module"].sudo().update_list()
            _logger.info("Instalador OCA: despues de update_list() para %s", self.repo_url)
            messages = capture.messages
            return {"ok": True, "messages": messages, "report": False}
        except Exception as error:
            messages = capture and capture.messages or []
            report = self._build_exception_report(error, log_messages=messages)
            report["summary"] = self._error_summary_for_code("update_list_failed")
            report["failure_code"] = "update_list_failed"
            report["cause"] = "\n".join(
                self._unique_lines(
                    [
                        _("Excepcion real durante el refresco de Apps: %s")
                        % self._exception_summary(error),
                    ]
                    + self._split_text_lines(report["cause"])
                )
            )
            return {"ok": False, "messages": messages, "report": report}

    def _ensure_runtime_addons_path(self, addons_path):
        normalized_path = os.path.abspath(addons_path)
        _logger.info(
            "Instalador OCA: validando registro runtime en addons_path: %s",
            normalized_path,
        )
        current_paths = self._runtime_addons_paths()
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
            _logger.exception("Instalador OCA: no se pudo refrescar la cache runtime de addons_path")

        try:
            addons_namespace = getattr(odoo, "addons", None)
            namespace_path = getattr(addons_namespace, "__path__", None)
            if namespace_path is not None:
                normalized_runtime_paths = {os.path.abspath(path) for path in namespace_path}
                if normalized_path not in normalized_runtime_paths and hasattr(namespace_path, "append"):
                    namespace_path.append(normalized_path)
        except Exception:
            _logger.exception(
                "Instalador OCA: no se pudo registrar la ruta runtime en odoo.addons.__path__"
            )

        runtime_registered = self._path_in_runtime(normalized_path)
        _logger.info(
            "Instalador OCA: ruta runtime %sregistrada: %s",
            "" if runtime_registered else "no ",
            normalized_path,
        )
        return runtime_registered

    def _persist_addons_path_to_config(self, addons_path, settings):
        config_path = settings.get("odoo_config_path")
        if not settings.get("persist_to_config") or not config_path:
            return False, False, False
        if not os.path.isfile(config_path):
            return False, False, _("La ruta del fichero de configuracion no existe: %s") % config_path

        _logger.info(
            "Instalador OCA: intentando persistir addons_path %s en %s",
            addons_path,
            config_path,
        )
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
                _logger.info(
                    "Instalador OCA: addons_path persistido correctamente en %s",
                    config_path,
                )
                return True, True, False
            _logger.info(
                "Instalador OCA: addons_path ya estaba presente en %s",
                config_path,
            )
            return True, False, False
        except Exception:
            _logger.exception(
                "Instalador OCA: no se pudo persistir addons_path en %s",
                config_path,
            )
            return False, False, _(
                "No se pudo escribir en %s. El repo puede funcionar ahora en runtime, pero conviene revisar permisos."
            ) % config_path

    def _assert_directory_writable(self, directory_path, label):
        try:
            self._ensure_directory(directory_path)
        except Exception as error:
            raise UserError(
                _("No se pudo preparar %s en %s: %s")
                % (label, directory_path, tools.ustr(error))
            )

        probe_path = False
        try:
            with tempfile.NamedTemporaryFile(
                dir=directory_path,
                prefix=".oca_installer_probe_",
                delete=False,
            ) as temp_file:
                probe_path = temp_file.name
        except Exception as error:
            raise UserError(
                _("Odoo no puede escribir en %s (%s): %s")
                % (label, directory_path, tools.ustr(error))
            )
        finally:
            if probe_path and os.path.exists(probe_path):
                os.unlink(probe_path)

    def _run_prepare_prechecks(self, settings, shared_root):
        if not shutil.which("git"):
            raise UserError(_("No se ha encontrado el comando git en el servidor."))

        self._assert_directory_writable(settings["clone_root"], _("la carpeta de clonado"))
        self._assert_directory_writable(shared_root, _("la carpeta OCA compartida"))

        cause_lines = []
        resolution_lines = []
        health_report = self._addons_path_health_report(settings)
        cause_lines.extend(health_report["cause_lines"])
        resolution_lines.extend(health_report["resolution_lines"])

        config_path = settings.get("odoo_config_path")
        if settings.get("persist_to_config"):
            if not config_path or not os.path.isfile(config_path):
                cause_lines.append(
                    _("No se ha podido verificar el fichero de configuracion %s antes de persistir addons_path.")
                    % (config_path or "-")
                )
                resolution_lines.append(
                    _(
                        "Si quieres persistir addons_path tras reiniciar Odoo, comprueba esa ruta o desactiva la persistencia automatica."
                    )
                )
            elif not os.access(config_path, os.W_OK):
                cause_lines.append(
                    _("El servicio Odoo probablemente no puede escribir en %s.")
                    % config_path
                )
                resolution_lines.append(
                    _(
                        "Si quieres persistir addons_path tras reiniciar Odoo, concede permisos de escritura o desactiva la persistencia automatica."
                    )
                )

        return {
            "cause_lines": self._unique_lines(cause_lines),
            "resolution_lines": self._unique_lines(resolution_lines),
        }

    def _is_path_within(self, child_path, parent_path):
        if not child_path or not parent_path:
            return False
        try:
            return os.path.commonpath([os.path.abspath(child_path), os.path.abspath(parent_path)]) == os.path.abspath(parent_path)
        except ValueError:
            return False

    def _safe_remove_path(self, target_path, managed_root):
        if not self._is_path_within(target_path, managed_root):
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

    def _shared_target_matches_source(self, target_path, source_path):
        if not target_path or not source_path or not os.path.lexists(target_path):
            return False
        if os.path.islink(target_path):
            return os.path.realpath(target_path) == os.path.realpath(source_path)
        if os.path.isdir(target_path):
            return self._read_origin_marker(target_path) == os.path.realpath(source_path)
        return False

    def _expose_addon(self, addon_path, shared_root, strategy):
        addon_name = os.path.basename(addon_path)
        target_path = os.path.join(shared_root, addon_name)
        _logger.info(
            "Instalador OCA: exponiendo addon %s desde %s hacia %s con estrategia %s",
            addon_name,
            addon_path,
            target_path,
            strategy,
        )
        if os.path.lexists(target_path):
            same_target = self._shared_target_matches_source(target_path, addon_path)
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
                _logger.info(
                    "Instalador OCA: addon %s expuesto por enlace simbolico",
                    addon_name,
                )
                return "symlink"
            except OSError:
                _logger.exception(
                    "Instalador OCA: no se pudo crear enlace simbolico para %s, se intentara copia",
                    addon_name,
                )

        shutil.copytree(addon_path, target_path)
        self._write_origin_marker(target_path, addon_path)
        _logger.info("Instalador OCA: addon %s expuesto por copia", addon_name)
        return "copy"

    def _apply_addon_snapshots(self, addon_line, source_snapshot, shared_snapshot=False, validation_message=False):
        shared_matches_source = bool(
            shared_snapshot
            and shared_snapshot["disk_path_exists"]
            and source_snapshot["disk_path_exists"]
            and self._shared_target_matches_source(shared_snapshot["path"], source_snapshot["path"])
        )
        addon_line.write(
            {
                "source_path": source_snapshot["path"] or addon_line.source_path or False,
                "manifest_path": source_snapshot["manifest_path"] or addon_line.manifest_path or False,
                "disk_path_exists": source_snapshot["disk_path_exists"],
                "manifest_exists": source_snapshot["manifest_exists"],
                "manifest_readable": source_snapshot["manifest_readable"],
                "manifest_installable": source_snapshot["manifest_installable"],
                "technical_name_matches_path": source_snapshot["technical_name_matches_path"],
                "shared_path": shared_snapshot and shared_snapshot["path"] or addon_line.shared_path or False,
                "exposed_in_shared_path": shared_matches_source,
                "manifest_error": source_snapshot["manifest_error"] or shared_snapshot and shared_snapshot["manifest_error"] or False,
                "last_validation_message": validation_message or False,
            }
        )

    def _refresh_addon_path_states(self):
        self.ensure_one()
        shared_root = self.addons_path_to_use or self.shared_addons_path or self._get_settings()["shared_root"]
        for addon in self.addon_ids:
            source_snapshot = self._inspect_addon_path(addon.source_path, expected_name=addon.name)
            shared_snapshot = self._inspect_addon_path(
                os.path.join(shared_root, addon.name),
                expected_name=addon.name,
            )
            validation_lines = []
            if not source_snapshot["disk_path_exists"]:
                validation_lines.append(
                    _("El addon no existe fisicamente en el repositorio clonado.")
                )
            if source_snapshot["disk_path_exists"] and not source_snapshot["manifest_exists"]:
                validation_lines.append(
                    _("La carpeta del addon existe, pero falta __manifest__.py en el repositorio.")
                )
            if source_snapshot["manifest_exists"] and not source_snapshot["manifest_readable"]:
                validation_lines.append(
                    _("El manifest del repositorio no se puede leer: %s")
                    % source_snapshot["manifest_error"]
                )
            if source_snapshot["manifest_readable"] and not source_snapshot["manifest_installable"]:
                validation_lines.append(_("El addon existe, pero installable es False."))
            if shared_snapshot["disk_path_exists"] and not shared_snapshot["manifest_exists"]:
                validation_lines.append(
                    _("La copia expuesta en la ruta compartida carece de __manifest__.py.")
                )
            if shared_snapshot["disk_path_exists"] and not self._shared_target_matches_source(
                shared_snapshot["path"],
                source_snapshot["path"],
            ):
                validation_lines.append(
                    _("Hay un conflicto de nombre con otro addon ya existente en la ruta compartida.")
                )
            elif not shared_snapshot["disk_path_exists"]:
                validation_lines.append(
                    _("El addon todavia no esta expuesto en la ruta compartida.")
                )
            self._apply_addon_snapshots(
                addon,
                source_snapshot,
                shared_snapshot=shared_snapshot,
                validation_message="\n".join(self._unique_lines(validation_lines)) or False,
            )

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
            _logger.info(
                "Instalador OCA: intentando instalar dependencias Python automaticamente para %s: %s",
                addon_line.name,
                ", ".join(packages),
            )
            result = self._run_process(
                self._render_template_command(settings["python_command"], packages)
            )
            if result.returncode != 0:
                notes.append(
                    _("No se han podido instalar automaticamente las dependencias Python. Revisa stderr.")
                )

        if preflight["missing_binary"] and settings.get("auto_install_binary") and settings.get("binary_command"):
            packages = [self._binary_package_name(name) for name in preflight["missing_binary"]]
            _logger.info(
                "Instalador OCA: intentando instalar dependencias binarias automaticamente para %s: %s",
                addon_line.name,
                ", ".join(packages),
            )
            result = self._run_process(
                self._render_template_command(settings["binary_command"], packages)
            )
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
            "resolution": "\n".join(self._unique_lines(resolution_lines)) or False,
            "missing_python": "\n".join(self._unique_lines(missing_python_lines)) or False,
            "missing_binary": "\n".join(self._unique_lines(missing_binary_lines)) or False,
            "missing_odoo": "\n".join(self._unique_lines(missing_odoo_lines)) or False,
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

    def _build_exception_report(self, error, addon_line=False, log_messages=None):
        trace_text = traceback.format_exc()
        error_text = "%s\n%s" % (tools.ustr(error), trace_text)
        missing_python = self._extract_missing_python_from_text(error_text)
        missing_odoo = self._extract_missing_odoo_from_text(error_text)
        log_info = self._extract_log_signals(log_messages or [])

        resolution_lines = []
        cause_lines = [_("Excepcion real: %s") % self._exception_summary(error)]
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

        if log_info["cause"]:
            cause_lines.append(log_info["cause"])
        if log_info["resolution"]:
            resolution_lines.append(log_info["resolution"])
        if self.last_command:
            cause_lines.append(_("Ultimo comando externo ejecutado: %s") % self.last_command)
        stderr_lines = self._split_text_lines(self.last_stderr)
        if stderr_lines:
            cause_lines.append(_("Ultimo stderr relevante: %s") % stderr_lines[0])

        if not resolution_lines:
            resolution_lines.append(
                _("Revisa el detalle tecnico y stderr; ahi suele aparecer la causa exacta del fallo.")
            )

        return {
            "summary": summary,
            "cause": "\n".join(self._unique_lines(cause_lines)) or False,
            "resolution": "\n".join(self._unique_lines(resolution_lines)),
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
            "log_highlights": log_info["raw"],
            "failure_code": log_info["codes"] and log_info["codes"][0] or False,
        }

    def _build_path_diagnostics(self, addon_line=False, direct_shared_addons=None):
        settings = self._get_settings()
        addons_path = os.path.abspath(
            self.addons_path_to_use or self.shared_addons_path or settings["shared_root"]
        )
        health_report = self._addons_path_health_report(settings)
        lines = [
            _("URL normalizada: %s") % (self.normalized_repo_url or self.repo_url or "-"),
            _("Rama usada: %s") % (self.branch or settings["branch"]),
            _("Ruta exacta de clonado: %s") % (self.clone_path or "-"),
            _("Ruta exacta usada en addons_path: %s") % addons_path,
            _("Ruta registrada en runtime: %s") % self._yesno(self._path_in_runtime(addons_path)),
            _("Ruta persistida en config: %s") % self._yesno(bool(self.config_path_persisted)),
        ]
        lines.extend(health_report["diagnostic_lines"])
        if health_report["cause_lines"]:
            lines.extend(health_report["cause_lines"])
        if direct_shared_addons is not None:
            lines.append(
                _("Addons detectados directamente bajo la ruta compartida: %s")
                % (", ".join(direct_shared_addons[:10]) if direct_shared_addons else _("ninguno"))
            )
        if addon_line:
            lines.extend(
                [
                    _("Addon seleccionado: %s") % addon_line.name,
                    _("Ruta fuente del addon: %s") % (addon_line.source_path or "-"),
                    _("Ruta compartida esperada: %s")
                    % os.path.join(addons_path, addon_line.name),
                ]
            )
        return "\n".join(lines)

    def _error_summary_for_code(self, code, addon_name=False):
        addon_name = addon_name or _("el addon")
        if code == "update_list_failed":
            return _("El repositorio se ha preparado, pero Odoo ha fallado al refrescar Apps.")
        if code == "repo_addon_missing":
            return _("El repositorio se ha clonado correctamente pero el addon no existe en la ruta esperada.")
        if code in {"manifest_missing", "shared_manifest_missing"}:
            return _("La carpeta del addon existe, pero falta __manifest__.py.")
        if code in {"manifest_invalid", "shared_manifest_invalid", "no_manifest_found"}:
            return _("El manifest es invalido o no se puede parsear.")
        if code in {"addon_not_installable", "odoo_uninstallable", "not_installable"}:
            return _("El addon fue detectado, pero Odoo lo considera no instalable.")
        if code == "addons_path_missing":
            return _("Odoo no ve el addon porque la ruta compartida no existe.")
        if code in {"addons_path_incorrect", "addons_path_not_in_runtime"}:
            return _("La ruta anadida a addons_path es incorrecta o no esta activa en runtime.")
        if code == "addon_not_exposed":
            return _("El repositorio contiene addons, pero el addon seleccionado no esta expuesto en la ruta compartida.")
        if code == "name_conflict":
            return _("Hay un conflicto de nombre con otro addon ya existente.")
        if code == "odoo_module_not_visible":
            return _("Odoo no ve el addon en Apps aunque existe en disco.")
        if code == "module_stuck_to_install":
            return _("El modulo quedo en estado to install despues de intentar instalarlo.")
        if code == "module_stuck_to_upgrade":
            return _("El modulo quedo en estado to upgrade despues de intentar instalarlo.")
        if code == "module_uninstalled":
            return _("El addon no ha llegado a instalarse y sigue desinstalado.")
        if code == "module_to_remove":
            return _("El modulo ha quedado en estado to remove y la instalacion no es valida.")
        if code == "modules_not_loaded":
            return _("Odoo ha informado de que algunos modulos no se han cargado.")
        if code == "modules_inconsistent":
            return _("Odoo ha informado de estados inconsistentes en algunos modulos.")
        if code == "technical_name_mismatch":
            return _("El nombre tecnico detectado no coincide con la carpeta real del addon.")
        return _("No se ha podido completar la operacion sobre %s.") % addon_name

    def _validate_source_addon(self, addon_line):
        snapshot = self._inspect_addon_path(addon_line.source_path, expected_name=addon_line.name)
        issues = []
        resolution_lines = []
        failure_code = False

        if not snapshot["disk_path_exists"]:
            failure_code = "repo_addon_missing"
            issues.append(
                _("El repositorio se ha clonado correctamente pero el addon no existe en la ruta esperada: %s")
                % (addon_line.source_path or "-")
            )
            resolution_lines.append(
                _("Revisa la rama %s, vuelve a preparar el repositorio y confirma la estructura real del repo.")
                % (self.branch or "-")
            )
        elif not snapshot["manifest_exists"]:
            failure_code = "manifest_missing"
            issues.append(
                _("La carpeta del addon existe, pero falta __manifest__.py en %s.")
                % snapshot["manifest_path"]
            )
            resolution_lines.append(
                _("Comprueba la estructura del repositorio o selecciona el addon correcto.")
            )
        elif not snapshot["manifest_readable"]:
            failure_code = "manifest_invalid"
            issues.append(
                _("El manifest es invalido o no se puede parsear: %s")
                % (snapshot["manifest_error"] or snapshot["manifest_path"])
            )
            resolution_lines.append(
                _("Corrige el __manifest__.py y vuelve a refrescar Apps.")
            )
        elif not snapshot["manifest_installable"]:
            failure_code = "addon_not_installable"
            issues.append(_("El addon existe, pero installable es False."))
            resolution_lines.append(
                _("Activa installable = True en el manifest o usa otra rama compatible con Odoo 18.")
            )

        if snapshot["disk_path_exists"] and not snapshot["technical_name_matches_path"]:
            failure_code = failure_code or "technical_name_mismatch"
            issues.append(
                _("El nombre tecnico detectado no coincide con la carpeta real del addon.")
            )
            resolution_lines.append(
                _("Haz que el nombre tecnico y la carpeta coincidan para que Odoo pueda cargarlo correctamente.")
            )

        return {
            "ok": not issues,
            "summary": self._error_summary_for_code(failure_code, addon_line.name),
            "cause": "\n".join(self._unique_lines(issues)) or False,
            "resolution": "\n".join(self._unique_lines(resolution_lines)) or False,
            "failure_code": failure_code,
            "snapshot": snapshot,
        }

    def _validate_addons_path(self, addon_line, source_snapshot=None, require_visible=False, log_messages=None):
        settings = self._get_settings()
        addons_root = os.path.abspath(
            self.addons_path_to_use or self.shared_addons_path or settings["shared_root"]
        )
        expected_shared_path = os.path.join(addons_root, addon_line.name)
        shared_snapshot = self._inspect_addon_path(
            expected_shared_path,
            expected_name=addon_line.name,
        )
        direct_shared_addons = []
        if os.path.isdir(addons_root):
            for entry_name in sorted(os.listdir(addons_root)):
                entry_path = os.path.join(addons_root, entry_name)
                if os.path.isdir(entry_path) and os.path.isfile(os.path.join(entry_path, "__manifest__.py")):
                    direct_shared_addons.append(entry_name)

        issues = []
        resolution_lines = []
        failure_code = False
        runtime_registered = self._path_in_runtime(addons_root)
        module_record = self.env["ir.module.module"].sudo().search([("name", "=", addon_line.name)], limit=1)
        log_info = self._extract_log_signals(log_messages or [])

        if not os.path.isdir(addons_root):
            failure_code = "addons_path_missing"
            issues.append(_("La ruta anadida a addons_path no existe en disco: %s") % addons_root)
            resolution_lines.append(
                _("Corrige la carpeta compartida y vuelve a preparar el repositorio.")
            )
        elif not direct_shared_addons:
            failure_code = "addons_path_incorrect"
            issues.append(
                _("La ruta anadida a addons_path es incorrecta: %s no contiene subcarpetas con __manifest__.py.")
                % addons_root
            )
            if addon_line.source_path:
                resolution_lines.append(
                    _("La ruta buena esperada para este addon es la carpeta padre %s, o bien la ruta compartida donde lo expongas como carpeta hija.")
                    % os.path.dirname(addon_line.source_path)
                )

        if not runtime_registered:
            failure_code = failure_code or "addons_path_not_in_runtime"
            issues.append(
                _("Odoo no ve el addon porque la ruta padre no esta en addons_path runtime: %s")
                % addons_root
            )
            resolution_lines.append(
                _("Anade %s a addons_path y vuelve a refrescar Apps.") % addons_root
            )

        if source_snapshot and source_snapshot["disk_path_exists"] and not shared_snapshot["disk_path_exists"]:
            failure_code = failure_code or "addon_not_exposed"
            issues.append(
                _("El repositorio contiene addons, pero el addon seleccionado no esta expuesto en la ruta compartida esperada: %s")
                % expected_shared_path
            )
            resolution_lines.append(
                _("Comprueba la estrategia de exposicion o corrige la ruta compartida.")
            )
        elif shared_snapshot["disk_path_exists"] and not shared_snapshot["manifest_exists"]:
            failure_code = failure_code or "shared_manifest_missing"
            issues.append(
                _("La carpeta del addon existe en la ruta compartida, pero falta __manifest__.py.")
            )
            resolution_lines.append(
                _("Vuelve a exponer el addon o revisa el contenido copiado/simbolizado.")
            )
        elif shared_snapshot["manifest_exists"] and not shared_snapshot["manifest_readable"]:
            failure_code = failure_code or "shared_manifest_invalid"
            issues.append(
                _("El manifest del addon expuesto es invalido o no se puede parsear: %s")
                % (shared_snapshot["manifest_error"] or shared_snapshot["manifest_path"])
            )
            resolution_lines.append(
                _("Corrige el manifest en el repositorio y vuelve a preparar el repositorio.")
            )

        if shared_snapshot["disk_path_exists"] and source_snapshot and source_snapshot["disk_path_exists"] and not self._shared_target_matches_source(
            shared_snapshot["path"],
            source_snapshot["path"],
        ):
            failure_code = failure_code or "name_conflict"
            issues.append(_("Hay un conflicto de nombre con otro addon ya existente en la ruta compartida."))
            resolution_lines.append(
                _("Elimina el conflicto o usa una carpeta compartida limpia antes de reinstalar.")
            )

        if require_visible and not module_record:
            failure_code = failure_code or "odoo_module_not_visible"
            issues.append(
                _("Odoo no ve el addon %s en ir.module.module.") % addon_line.name
            )
            if runtime_registered and shared_snapshot["disk_path_exists"]:
                resolution_lines.append(
                    _("Pulsa 'Refrescar Apps'. Si sigue sin aparecer, revisa que %s sea la carpeta padre correcta en addons_path.")
                    % addons_root
                )
            else:
                resolution_lines.append(
                    _("Corrige primero la ruta compartida y vuelve a refrescar Apps.")
                )

        if require_visible and module_record and module_record.state == "uninstallable":
            failure_code = failure_code or "odoo_uninstallable"
            issues.append(_("El addon fue detectado, pero Odoo lo considera no instalable."))
            resolution_lines.append(
                _("Revisa installable = True, dependencias y los mensajes Odoo detectados en esta ficha.")
            )

        if log_info["cause"]:
            issues.append(log_info["cause"])
        if log_info["resolution"]:
            resolution_lines.append(log_info["resolution"])
        if not failure_code and log_info["codes"]:
            failure_code = log_info["codes"][0]

        return {
            "ok": not issues,
            "summary": self._error_summary_for_code(failure_code, addon_line.name),
            "cause": "\n".join(self._unique_lines(issues)) or False,
            "resolution": "\n".join(self._unique_lines(resolution_lines)) or False,
            "failure_code": failure_code,
            "shared_snapshot": shared_snapshot,
            "module_record": module_record,
            "path_diagnostics": self._build_path_diagnostics(
                addon_line=addon_line,
                direct_shared_addons=direct_shared_addons,
            ),
            "log_highlights": log_info["raw"],
        }

    def _validate_selected_addon(self, addon_line, require_visible=False, log_messages=None):
        source_validation = self._validate_source_addon(addon_line)
        path_validation = self._validate_addons_path(
            addon_line,
            source_snapshot=source_validation["snapshot"],
            require_visible=require_visible,
            log_messages=log_messages,
        )

        combined_cause = self._unique_lines(
            self._split_text_lines(source_validation["cause"])
            + self._split_text_lines(path_validation["cause"])
        )
        combined_resolution = self._unique_lines(
            self._split_text_lines(source_validation["resolution"])
            + self._split_text_lines(path_validation["resolution"])
        )
        summary = source_validation["summary"] if not source_validation["ok"] else path_validation["summary"]
        failure_code = source_validation["failure_code"] or path_validation["failure_code"]
        validation_message = "\n".join(combined_cause) or False
        self._apply_addon_snapshots(
            addon_line,
            source_validation["snapshot"],
            shared_snapshot=path_validation["shared_snapshot"],
            validation_message=validation_message,
        )

        return {
            "ok": source_validation["ok"] and path_validation["ok"],
            "summary": summary,
            "cause": "\n".join(combined_cause) or False,
            "resolution": "\n".join(combined_resolution) or False,
            "failure_code": failure_code,
            "path_diagnostics": path_validation["path_diagnostics"],
            "log_highlights": path_validation["log_highlights"],
            "module_record": path_validation["module_record"],
        }

    def _post_validate_installation(self, addon_line, log_messages=None):
        module_record = self.env["ir.module.module"].sudo().search([("name", "=", addon_line.name)], limit=1)
        final_state = module_record.state if module_record else "not_found"
        log_info = self._extract_log_signals(log_messages or [])
        issues = []
        resolution_lines = []
        failure_code = False

        if final_state == "installed":
            summary = _("El addon %s se ha instalado correctamente.") % addon_line.name
            resolution_lines.append(
                _("Si el addon tenia dependencias Odoo disponibles, Odoo tambien las habra instalado.")
            )
            if log_info["resolution"]:
                resolution_lines.append(log_info["resolution"])
            return {
                "ok": True,
                "summary": summary,
                "cause": log_info["cause"],
                "resolution": "\n".join(self._unique_lines(resolution_lines)) or False,
                "failure_code": False,
                "final_state": final_state,
                "log_highlights": log_info["raw"],
            }

        if final_state == "not_found":
            failure_code = "odoo_module_not_visible"
            issues.append(
                _("Odoo no ve el addon %s en ir.module.module despues de intentar instalarlo.")
                % addon_line.name
            )
            resolution_lines.append(
                _("Revisa addons_path, vuelve a refrescar Apps y confirma que el addon este realmente expuesto.")
            )
        elif final_state == "to install":
            failure_code = "module_stuck_to_install"
            issues.append(
                _("El modulo quedo en estado to install despues de button_immediate_install.")
            )
            resolution_lines.append(
                _("Revisa dependencias, logs y que el addon sea cargable desde addons_path.")
            )
        elif final_state == "to upgrade":
            failure_code = "module_stuck_to_upgrade"
            issues.append(
                _("El modulo quedo en estado to upgrade despues de button_immediate_install.")
            )
            resolution_lines.append(
                _("Revisa si existe una instalacion previa inconsistente o dependencias pendientes.")
            )
        elif final_state == "uninstalled":
            failure_code = "module_uninstalled"
            issues.append(
                _("El addon no ha llegado a instalarse y el estado final sigue siendo uninstalled.")
            )
            resolution_lines.append(
                _("Consulta los mensajes Odoo detectados y el detalle tecnico para encontrar el bloqueo real.")
            )
        elif final_state == "to remove":
            failure_code = "module_to_remove"
            issues.append(
                _("El modulo ha quedado en estado to remove y la instalacion no es valida.")
            )
            resolution_lines.append(
                _("Revisa dependencias circulares o fallos de actualizacion previos.")
            )
        elif final_state == "uninstallable":
            failure_code = "odoo_uninstallable"
            issues.append(_("El addon fue detectado, pero Odoo lo considera no instalable."))
            resolution_lines.append(
                _("Revisa installable = True, dependencias, manifest y la ruta desde la que Odoo carga el addon.")
            )
        else:
            issues.append(
                _("La instalacion ha terminado en un estado no esperado: %s") % final_state
            )
            resolution_lines.append(
                _("Revisa el estado real del modulo y los logs del servidor.")
            )

        if log_info["cause"]:
            issues.append(log_info["cause"])
        if log_info["resolution"]:
            resolution_lines.append(log_info["resolution"])
        if not failure_code and log_info["codes"]:
            failure_code = log_info["codes"][0]

        inconsistent_modules = self.env["ir.module.module"].sudo().search(
            [("state", "in", ["to install", "to upgrade", "to remove"])]
        )
        if inconsistent_modules:
            module_names = ", ".join(inconsistent_modules[:10].mapped("name"))
            issues.append(
                _("Odoo mantiene modulos en estado pendiente o inconsistente: %s") % module_names
            )
            resolution_lines.append(
                _("Comprueba dependencias cruzadas y revisa los logs de carga del servidor.")
            )

        return {
            "ok": False,
            "summary": self._error_summary_for_code(failure_code, addon_line.name),
            "cause": "\n".join(self._unique_lines(issues)) or False,
            "resolution": "\n".join(self._unique_lines(resolution_lines)) or False,
            "failure_code": failure_code,
            "final_state": final_state,
            "log_highlights": log_info["raw"],
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
                "normalized_repo_url": normalized_url,
                "clone_path": repo_path,
                "shared_addons_path": shared_root,
                "addons_path_to_use": shared_root,
                "last_operation": "prepare_repository",
            }
        )

        try:
            _logger.info(
                "Instalador OCA: preparando repositorio %s en rama %s",
                normalized_url,
                branch,
            )
            precheck_report = self._run_prepare_prechecks(settings, shared_root)
            precheck_cause_lines = list(precheck_report["cause_lines"])
            precheck_resolution_lines = list(precheck_report["resolution_lines"])

            if os.path.isdir(repo_path):
                if not os.path.isdir(os.path.join(repo_path, ".git")):
                    raise UserError(
                        _("La ruta %s ya existe, pero no parece un repositorio git valido.") % repo_path
                    )
                _logger.info(
                    "Instalador OCA: actualizando repositorio existente en %s",
                    repo_path,
                )
                result = self._run_process(["git", "-C", repo_path, "pull", "--ff-only", "origin", branch])
            else:
                _logger.info(
                    "Instalador OCA: clonando repositorio %s en %s",
                    normalized_url,
                    repo_path,
                )
                result = self._run_process(
                    ["git", "clone", "-b", branch, "--depth", "1", normalized_url, repo_path]
                )

            if result.returncode != 0:
                summary = _("No se ha podido descargar o actualizar el repositorio.")
                cause = result.stderr or result.stdout or _("Git ha devuelto un error sin detalle adicional.")
                self._mark_error(
                    summary,
                    resolution=_("Comprueba la URL, la conectividad del servidor y los permisos de escritura."),
                    detected_cause=cause,
                    error_details=cause,
                    path_diagnostics=self._build_path_diagnostics(),
                )
                return False, summary

            _logger.info(
                "Instalador OCA: repositorio preparado fisicamente en %s",
                repo_path,
            )
            addons, repo_issues = self._discover_addons(repo_path)
            _logger.info(
                "Instalador OCA: addons detectados en %s: %s",
                repo_path,
                ", ".join(addon["name"] for addon in addons) or _("ninguno"),
            )
            if not addons:
                detected_cause = "\n".join(self._unique_lines(repo_issues))
                self._mark_error(
                    _("El repositorio se ha descargado, pero no se han detectado addons Odoo validos."),
                    resolution=_(
                        "Asegurate de que la rama elegida contiene carpetas hijas con __manifest__.py en el primer nivel."
                    ),
                    detected_cause=detected_cause,
                    path_diagnostics=self._build_path_diagnostics(),
                )
                return False, self.diagnostic_summary

            exposure_notes = []
            for addon_info in addons:
                mode_used = self._expose_addon(
                    addon_info["path"],
                    shared_root,
                    settings["path_strategy"],
                )
                if mode_used == "copy":
                    exposure_notes.append(
                        _("Se ha usado copia en lugar de enlace simbolico para %s.")
                        % addon_info["name"]
                    )

            runtime_registered = self._ensure_runtime_addons_path(shared_root)
            config_registered, config_updated, config_note = self._persist_addons_path_to_config(
                shared_root, settings
            )
            self.write(
                {
                    "runtime_path_registered": runtime_registered,
                    "config_path_persisted": config_registered,
                }
            )
            if config_updated:
                _logger.info(
                    "Instalador OCA: addons_path actualizado en el fichero de configuracion"
                )
            if config_note:
                exposure_notes.append(config_note)

            update_result = self._safe_update_module_list()
            update_logs = update_result["messages"]
            log_info = self._extract_log_signals(update_logs)

            self._sync_addon_lines(addons)
            self._refresh_addon_path_states()
            self._refresh_addon_odoo_states()

            resolution_lines = (
                precheck_resolution_lines
                + exposure_notes
                + [_("Selecciona un addon del repositorio y pulsa instalar.")]
            )
            if log_info["resolution"]:
                resolution_lines.append(log_info["resolution"])
            detected_cause_lines = precheck_cause_lines + list(repo_issues)
            if log_info["cause"]:
                detected_cause_lines.append(log_info["cause"])

            if not update_result["ok"]:
                report = update_result["report"]
                resolution_lines.append(
                    _(
                        "El repositorio ya esta clonado y los addons ya estan expuestos. El bloqueo esta en el refresco de Apps, no en la descarga del repo."
                    )
                )
                if report["resolution"]:
                    resolution_lines.append(report["resolution"])
                if report["cause"]:
                    detected_cause_lines.append(report["cause"])
                if report["log_highlights"]:
                    log_info["raw"] = "\n".join(
                        self._unique_lines(
                            self._split_text_lines(log_info["raw"])
                            + self._split_text_lines(report["log_highlights"])
                        )
                    )
                message = _("Repositorio preparado con advertencias. Addons detectados: %s.") % len(addons)
                self._mark_success(
                    "prepared",
                    message,
                    resolution="\n".join(self._unique_lines(resolution_lines)) or False,
                    detected_cause="\n".join(self._unique_lines(detected_cause_lines)) or False,
                    path_diagnostics=self._build_path_diagnostics(
                        direct_shared_addons=[addon.name for addon in self.addon_ids]
                    ),
                    odoo_log_highlights=log_info["raw"],
                    failure_code=report["failure_code"],
                )
                return True, message

            message = _("Repositorio preparado correctamente. Addons detectados: %s.") % len(addons)
            self._mark_success(
                "prepared",
                message,
                resolution="\n".join(self._unique_lines(resolution_lines)) or False,
                detected_cause="\n".join(self._unique_lines(detected_cause_lines)) or False,
                path_diagnostics=self._build_path_diagnostics(
                    direct_shared_addons=[addon.name for addon in self.addon_ids]
                ),
                odoo_log_highlights=log_info["raw"],
            )
            return True, message
        except (UserError, ValidationError) as error:
            message = tools.ustr(error)
            self._mark_error(
                message,
                detected_cause=message,
                error_details=message,
                path_diagnostics=self._build_path_diagnostics(),
            )
            return False, message
        except Exception as error:
            report = self._build_exception_report(error)
            self._mark_error(
                report["summary"],
                resolution=report["resolution"],
                detected_cause=report["cause"],
                error_details=report["details"],
                path_diagnostics=self._build_path_diagnostics(),
                odoo_log_highlights=report["log_highlights"],
                missing_python=report["missing_python"],
                missing_binary=report["missing_binary"],
                missing_odoo=report["missing_odoo"],
                failure_code=report["failure_code"],
            )
            return False, report["summary"]

    def _install_addon(self, addon_line):
        self.ensure_one()
        settings = self._get_settings()
        self._clear_diagnostics()
        self.write(
            {
                "last_operation": "install_addon",
                "target_addon_id": addon_line.id,
                "addons_path_to_use": self.shared_addons_path or settings["shared_root"],
            }
        )

        try:
            _logger.info(
                "Instalador OCA: iniciando validacion previa del addon %s",
                addon_line.name,
            )
            runtime_registered = self._ensure_runtime_addons_path(
                self.addons_path_to_use or settings["shared_root"]
            )
            self.write({"runtime_path_registered": runtime_registered})

            pre_validation = self._validate_selected_addon(addon_line)
            if not pre_validation["ok"]:
                self._mark_error(
                    pre_validation["summary"],
                    resolution=pre_validation["resolution"],
                    detected_cause=pre_validation["cause"],
                    path_diagnostics=pre_validation["path_diagnostics"],
                    odoo_log_highlights=pre_validation["log_highlights"],
                    failure_code=pre_validation["failure_code"],
                )
                addon_line.write(
                    {
                        "install_result": self._format_user_message(
                            pre_validation["summary"],
                            pre_validation["cause"],
                            pre_validation["resolution"],
                        )
                    }
                )
                return False, pre_validation["summary"]

            update_result = self._safe_update_module_list()
            update_logs = update_result["messages"]
            if not update_result["ok"]:
                report = update_result["report"]
                self._mark_error(
                    report["summary"],
                    resolution=report["resolution"],
                    detected_cause=report["cause"],
                    error_details=report["details"],
                    path_diagnostics=self._build_path_diagnostics(addon_line=addon_line),
                    odoo_log_highlights=report["log_highlights"],
                    missing_python=report["missing_python"],
                    missing_binary=report["missing_binary"],
                    missing_odoo=report["missing_odoo"],
                    failure_code=report["failure_code"],
                )
                addon_line.write(
                    {
                        "install_result": self._format_user_message(
                            report["summary"],
                            report["cause"],
                            report["resolution"],
                        )
                    }
                )
                return False, report["summary"]
            self._refresh_addon_path_states()
            self._refresh_addon_odoo_states()
            visibility_validation = self._validate_selected_addon(
                addon_line,
                require_visible=True,
                log_messages=update_logs,
            )
            if not visibility_validation["ok"]:
                self._mark_error(
                    visibility_validation["summary"],
                    resolution=visibility_validation["resolution"],
                    detected_cause=visibility_validation["cause"],
                    path_diagnostics=visibility_validation["path_diagnostics"],
                    odoo_log_highlights=visibility_validation["log_highlights"],
                    failure_code=visibility_validation["failure_code"],
                )
                addon_line.write(
                    {
                        "install_result": self._format_user_message(
                            visibility_validation["summary"],
                            visibility_validation["cause"],
                            visibility_validation["resolution"],
                        )
                    }
                )
                return False, visibility_validation["summary"]

            preflight, auto_install_notes = self._attempt_auto_install_dependencies(addon_line, settings)
            report = self._build_dependency_resolution(addon_line, preflight)
            if preflight["missing_python"] or preflight["missing_binary"] or preflight["missing_odoo_unavailable"]:
                resolution_lines = self._split_text_lines(report["resolution"])
                resolution_lines = auto_install_notes + resolution_lines
                summary = report["summary"]
                detected_cause_lines = (
                    self._split_text_lines(report["missing_python"])
                    + self._split_text_lines(report["missing_binary"])
                    + self._split_text_lines(report["missing_odoo"])
                )
                self._mark_error(
                    summary,
                    resolution="\n".join(self._unique_lines(resolution_lines)) or False,
                    detected_cause="\n".join(self._unique_lines(detected_cause_lines)) or summary,
                    path_diagnostics=self._build_path_diagnostics(addon_line=addon_line),
                    missing_python=report["missing_python"],
                    missing_binary=report["missing_binary"],
                    missing_odoo=report["missing_odoo"],
                    failure_code="missing_dependencies",
                )
                addon_line.write(
                    {
                        "install_result": self._format_user_message(
                            summary,
                            "\n".join(self._unique_lines(detected_cause_lines)) or summary,
                            "\n".join(self._unique_lines(resolution_lines)) or False,
                        )
                    }
                )
                return False, summary

            module_record = self.env["ir.module.module"].sudo().search([("name", "=", addon_line.name)], limit=1)
            if not module_record:
                summary = _("Odoo todavia no ve el addon %s en Apps.") % addon_line.name
                resolution = _(
                    "Revisa que la ruta compartida exista, que este en addons_path y vuelve a pulsar refrescar."
                )
                cause = _("La validacion previa ha confirmado que el addon existe en disco, pero ir.module.module no lo contiene.")
                self._mark_error(
                    summary,
                    resolution=resolution,
                    detected_cause=cause,
                    path_diagnostics=self._build_path_diagnostics(addon_line=addon_line),
                    failure_code="odoo_module_not_visible",
                )
                addon_line.write(
                    {
                        "install_result": self._format_user_message(summary, cause, resolution)
                    }
                )
                return False, summary

            if module_record.state == "installed":
                summary = _("El addon %s ya estaba instalado.") % addon_line.name
                self._mark_success(
                    "installed",
                    summary,
                    resolution=_("No hace falta ninguna accion adicional."),
                    path_diagnostics=self._build_path_diagnostics(addon_line=addon_line),
                    final_module_state="installed",
                )
                addon_line.write({"install_result": summary})
                self._refresh_addon_odoo_states()
                return True, summary

            _logger.info(
                "Instalador OCA: antes de button_immediate_install() para %s. Estado actual: %s",
                addon_line.name,
                module_record.state,
            )
            with self.env.cr.savepoint():
                with self._capture_odoo_logs() as capture:
                    module_record.button_immediate_install()
            install_logs = capture.messages
            _logger.info(
                "Instalador OCA: despues de button_immediate_install() para %s",
                addon_line.name,
            )

            self._refresh_addon_odoo_states()
            post_report = self._post_validate_installation(addon_line, install_logs)
            _logger.info(
                "Instalador OCA: estado final real del modulo %s: %s",
                addon_line.name,
                post_report["final_state"],
            )
            if not post_report["ok"]:
                self._mark_error(
                    post_report["summary"],
                    resolution=post_report["resolution"],
                    detected_cause=post_report["cause"],
                    path_diagnostics=self._build_path_diagnostics(addon_line=addon_line),
                    odoo_log_highlights=post_report["log_highlights"],
                    failure_code=post_report["failure_code"],
                    final_module_state=post_report["final_state"],
                    error_details=post_report["log_highlights"] or False,
                )
                addon_line.write(
                    {
                        "install_result": self._format_user_message(
                            post_report["summary"],
                            post_report["cause"],
                            post_report["resolution"],
                        )
                    }
                )
                return False, post_report["summary"]

            self._mark_success(
                "installed",
                post_report["summary"],
                resolution=post_report["resolution"],
                detected_cause=post_report["cause"],
                path_diagnostics=self._build_path_diagnostics(addon_line=addon_line),
                odoo_log_highlights=post_report["log_highlights"],
                final_module_state=post_report["final_state"],
            )
            addon_line.write({"install_result": post_report["summary"]})
            return True, post_report["summary"]
        except (UserError, ValidationError) as error:
            message = tools.ustr(error)
            self._mark_error(
                message,
                detected_cause=message,
                error_details=message,
                path_diagnostics=self._build_path_diagnostics(addon_line=addon_line),
            )
            addon_line.write({"install_result": message})
            return False, message
        except Exception as error:
            report = self._build_exception_report(error, addon_line=addon_line)
            self._mark_error(
                report["summary"],
                resolution=report["resolution"],
                detected_cause=report["cause"],
                error_details=report["details"],
                path_diagnostics=self._build_path_diagnostics(addon_line=addon_line),
                odoo_log_highlights=report["log_highlights"],
                missing_python=report["missing_python"],
                missing_binary=report["missing_binary"],
                missing_odoo=report["missing_odoo"],
                failure_code=report["failure_code"],
            )
            addon_line.write(
                {
                    "install_result": self._format_user_message(
                        report["summary"],
                        report["cause"],
                        report["resolution"],
                    )
                }
            )
            return False, report["summary"]

    def action_prepare_repository(self):
        self.ensure_one()
        ok, message = self._prepare_repository()
        if not ok:
            self._raise_functional_error(
                self.diagnostic_summary or message,
                self.detected_cause,
                self.resolution_hint,
            )
        return self._notify(message, "warning" if self.failure_code else "success")

    def action_refresh_available_modules(self):
        self.ensure_one()
        self._clear_diagnostics()
        self.write({"last_operation": "refresh_modules"})
        try:
            shared_root = self.addons_path_to_use or self.shared_addons_path or self._get_settings()["shared_root"]
            runtime_registered = self._ensure_runtime_addons_path(shared_root)
            self.write({"runtime_path_registered": runtime_registered})
            update_result = self._safe_update_module_list()
            update_logs = update_result["messages"]
            if not update_result["ok"]:
                report = update_result["report"]
                self._mark_error(
                    report["summary"],
                    resolution=report["resolution"],
                    detected_cause=report["cause"],
                    error_details=report["details"],
                    path_diagnostics=self._build_path_diagnostics(),
                    odoo_log_highlights=report["log_highlights"],
                    missing_python=report["missing_python"],
                    missing_binary=report["missing_binary"],
                    missing_odoo=report["missing_odoo"],
                    failure_code=report["failure_code"],
                )
                self._raise_functional_error(
                    report["summary"],
                    report["cause"],
                    report["resolution"],
                )
            log_info = self._extract_log_signals(update_logs)
            self._refresh_addon_path_states()
            self._refresh_addon_odoo_states()

            detected_cause_lines = []
            resolution_lines = [_("Ahora puedes instalar cualquier addon detectado.")]
            if self.target_addon_id:
                validation = self._validate_selected_addon(
                    self.target_addon_id,
                    require_visible=True,
                    log_messages=update_logs,
                )
                if not validation["ok"]:
                    self._mark_error(
                        validation["summary"],
                        resolution=validation["resolution"],
                        detected_cause=validation["cause"],
                        path_diagnostics=validation["path_diagnostics"],
                        odoo_log_highlights=validation["log_highlights"],
                        failure_code=validation["failure_code"],
                    )
                    self._raise_functional_error(
                        validation["summary"],
                        validation["cause"],
                        validation["resolution"],
                    )
                if validation["cause"]:
                    detected_cause_lines.append(validation["cause"])
                if validation["resolution"]:
                    resolution_lines.append(validation["resolution"])
            elif log_info["cause"]:
                detected_cause_lines.append(log_info["cause"])
            if log_info["resolution"]:
                resolution_lines.append(log_info["resolution"])

            self._mark_success(
                "prepared" if self.state != "installed" else self.state,
                _("La lista de Apps se ha refrescado correctamente."),
                resolution="\n".join(self._unique_lines(resolution_lines)) or False,
                detected_cause="\n".join(self._unique_lines(detected_cause_lines)) or False,
                path_diagnostics=self._build_path_diagnostics(
                    direct_shared_addons=[addon.name for addon in self.addon_ids]
                ),
                odoo_log_highlights=log_info["raw"],
                final_module_state=self.target_addon_id.odoo_module_state if self.target_addon_id else False,
            )
            return self._notify(_("Lista de Apps actualizada."))
        except (UserError, ValidationError):
            raise
        except Exception as error:
            report = self._build_exception_report(error)
            self._mark_error(
                report["summary"],
                resolution=report["resolution"],
                detected_cause=report["cause"],
                error_details=report["details"],
                path_diagnostics=self._build_path_diagnostics(),
                odoo_log_highlights=report["log_highlights"],
                missing_python=report["missing_python"],
                missing_binary=report["missing_binary"],
                missing_odoo=report["missing_odoo"],
                failure_code=report["failure_code"],
            )
            self._raise_functional_error(
                report["summary"],
                report["cause"],
                report["resolution"],
            )

    def action_install_selected_addon(self):
        self.ensure_one()
        if not self.addon_ids:
            ok, _message = self._prepare_repository()
            if not ok:
                self._raise_functional_error(
                    self.diagnostic_summary,
                    self.detected_cause,
                    self.resolution_hint,
                )

        addon_line = self.target_addon_id
        if not addon_line and len(self.addon_ids) == 1:
            addon_line = self.addon_ids[:1]
            self.target_addon_id = addon_line

        if not addon_line:
            raise UserError(
                _("Selecciona el addon concreto a instalar. Este repositorio contiene varios addons.")
            )

        ok, message = self._install_addon(addon_line)
        if not ok:
            self._raise_functional_error(
                self.diagnostic_summary or message,
                self.detected_cause,
                self.resolution_hint,
            )
        return self._notify(message, "success")


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
    shared_path = fields.Char(string="Ruta compartida", readonly=True)
    disk_path_exists = fields.Boolean(string="Existe en disco", readonly=True)
    manifest_exists = fields.Boolean(string="Tiene manifest", readonly=True)
    manifest_readable = fields.Boolean(string="Manifest legible", readonly=True)
    manifest_installable = fields.Boolean(string="Installable", readonly=True)
    technical_name_matches_path = fields.Boolean(
        string="Nombre tecnico correcto",
        readonly=True,
    )
    exposed_in_shared_path = fields.Boolean(string="Expuesto en ruta compartida", readonly=True)
    manifest_error = fields.Text(string="Error de manifest", readonly=True)
    last_validation_message = fields.Text(string="Validacion", readonly=True)
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
