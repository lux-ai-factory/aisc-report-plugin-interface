from abc import ABC, abstractmethod
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from sqlalchemy.orm import Session

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader, select_autoescape

class BaseReporterPlugin(ABC):
    """
    Base class for reporter plugins.

    Plugin authors typically only implement:
    - `get_template_relative_path`: template location inside the plugin package
    - `build_template_context`: context dict passed to Jinja template rendering

    The default `generate_content` method handles rendering.
    """
    def __init__(self, db_session: Session):
        self.shared_session = db_session
        self.session = db_session

    def _template_package(self) -> str:
        module_name = self.__class__.__module__
        return module_name.rsplit(".", 1)[0] if "." in module_name else module_name
    
    def _resolve_shared_templates_dir(self) -> Path:
        start = Path(__file__).resolve()
        for parent in [start.parent, *start.parents]:
            candidate = parent / "resources" / "templates"
            if candidate.is_dir():
                return candidate
        raise FileNotFoundError(
            "Could not locate shared templates directory 'resources/templates' from base_report_plugin.py"
        )

    def _template_environment(self) -> Environment:
        shared_templates_dir = self._resolve_shared_templates_dir()
        return Environment(
            loader=ChoiceLoader([
                PackageLoader(self._template_package(), "."),
                FileSystemLoader(str(shared_templates_dir)),
            ]),
            autoescape=select_autoescape(["html", "xml"]),
        )

    @staticmethod
    def _validate_relative_template_path(template_relative_path: str) -> str:
        path_obj = PurePosixPath(template_relative_path)

        if not template_relative_path or template_relative_path.strip() == "":
            raise ValueError("Template path must be a non-empty relative path")
        if path_obj.is_absolute():
            raise ValueError("Template path must be relative to the plugin package")
        if any(part in {"..", ""} for part in path_obj.parts):
            raise ValueError("Template path cannot navigate outside the plugin package")

        return path_obj.as_posix()

    def render_package_template(self, template_relative_path: str, **context: Any) -> str:
        safe_template_path = self._validate_relative_template_path(template_relative_path)
        template = self._template_environment().get_template(safe_template_path)
        return template.render(**context)

    def render_template(self, template_name: str, **context: Any) -> str:
        return self.render_package_template(template_name, **context)

    @abstractmethod
    def get_template_relative_path(self) -> str:
        raise NotImplementedError("Subclasses must implement get_template_relative_path to provide the path to the template directory relative from the package root.")

    @abstractmethod
    def build_template_context(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("Subclasses must implement build_template_context.")

    def generate_content(self, **kwargs: Any) -> str:
        template_relative_path = self.get_template_relative_path()
        context = self.build_template_context(**kwargs)
        try:
            report_content = self.render_package_template(template_relative_path, **context)
        except Exception as e:
            report_content = f"[ERROR] Failed to generate content for plugin {self.__class__.__name__}: Check logs for details."
        return report_content