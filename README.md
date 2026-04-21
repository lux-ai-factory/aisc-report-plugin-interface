# vera-report-plugin-interface

Definition of the plugin interface for report generation.

---

## Plugin directory structure and plugin management

## Plugin root

By default, plugins are loaded from `./plugins`. Each immediate subdirectory is treated as one plugin package root candidate.

Example:

```text
plugins/
	lexcheck/
		__init__.py
		data_loader.py
		lexcheck_report_plugin.py
		template_section.html.j2
	mlareject/
		__init__.py
		data_loader.py
		mlareject_reporter.py
		template_section.html.j2
```

## Package discovery rules (`PluginRegistry`)

For each plugin folder, the registry resolves the package using this order:

1. `<pkg_root>/__init__.py`
2. `<pkg_root>/src/<module_name>/__init__.py`
3. `<pkg_root>/<module_name>/__init__.py` (any child dir except `src`)

Then it imports that package and registers every class that:
- is a subclass of `BaseReporterPlugin`
- is not `BaseReporterPlugin` itself

## Mapping DB tool names to plugin classes

During report generation, tool names from the DB are normalized and resolved to class names following this contract:

`<NORMALIZED_TOOL_NAME>ReportPlugin`

Examples:
- `LEXCHECK` -> `LEXCHECKReportPlugin`
- `MLAREJECT` -> `MLAREJECTReportPlugin`

Ensure the class is importable from your plugin package `__init__.py`.

---

## Report plugin development guide

This project uses `vera_report_plugin_interface/base_report_plugin.py` as the plugin interface.

## What to implement

Create a class that inherits `BaseReporterPlugin` and implement:

1. `get_template_relative_path(self) -> str`
	 - Return a **relative** path to the plugin template inside your plugin package.
	 - Example: `"template_section.html.j2"`

2. `build_template_context(self, **kwargs) -> dict[str, Any]`
	 - Query/aggregate tool-specific data (typically through a helper loader).
	 - Return a context dictionary used by Jinja.
	 - If you want plots, pass through `kwargs.get("tool_plots")`.

You typically also provide:
- `__init__(self, db_session)` to set `self.tool_name` and call `super().__init__(db_session)`.

## What you get for free from `BaseReporterPlugin`

- `generate_content(**kwargs)`
	- Calls `get_template_relative_path()`
	- Calls `build_template_context(**kwargs)`
	- Renders the template and returns HTML
- Template rendering helpers:
	- `render_package_template(...)`
	- Shared template availability via `resources/templates` (e.g. includes like `tool_plots_subsection.html.j2`)

## Minimal plugin scaffold

```python
# plugins/mytool/mytool_report_plugin.py
from sqlalchemy.orm import Session
from vera_report_plugin_interface.base_report_plugin import BaseReporterPlugin


class MYTOOLReportPlugin(BaseReporterPlugin):
		def __init__(self, db_session: Session | None = None):
				self.tool_name = "MYTOOL"
				super().__init__(db_session)

		def get_template_relative_path(self) -> str:
				return "template_section.html.j2"

		def build_template_context(self, **kwargs: object) -> dict[str, object]:
				statistics = {"example": 1}
				return {
						"tool_name": self.tool_name,
						"statistics": statistics,
						"tool_plots": kwargs.get("tool_plots") or {},
				}
```

```python
# plugins/mytool/__init__.py
from .mytool_report_plugin import MYTOOLReportPlugin

__all__ = ["MYTOOLReportPlugin"]
```

```jinja
{# plugins/mytool/template_section.html.j2 #}
<div class="tool-section">
	<h3>Executive Summary</h3>
	<p>{{ tool_name }} results</p>
	{% include 'tool_plots_subsection.html.j2' %}
</div>
```

## End-to-end plugin workflow

1. Create `plugins/<your_tool>/` package.
2. Add plugin class inheriting `BaseReporterPlugin`.
3. Implement `get_template_relative_path` + `build_template_context`.
4. Add `template_section.html.j2`.
5. Export your class from plugin `__init__.py`.
6. Ensure your DB `Tool.name` matches your plugin naming contract.
7. Run generator and verify your section appears under each matching evaluation.
