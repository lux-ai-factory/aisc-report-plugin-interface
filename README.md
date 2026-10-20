# aisc-report-plugin-interface

`aisc-report-plugin-interface` (import name `aisc_report_plugin_interface`) is the Python library
that report plugins are written against. AISC (the AI Assessment Sandbox Configurator) runs an
assessment in four steps: 1 Qualify the AI system, 2 Set control objectives, 3 Choose tests and
checklists, 4 Collect evidence. In step 4 the report composer lets a user assemble a report from **blocks**, and the
report renderer (`apps/report-generator`, compose service `report-renderer`) draws each block into
an HTML, PDF or DOCX document. This library defines the contracts the renderer and its plugins share:
block types, the renderers that draw one evaluation tool's run inside the Test results block, and
helpers for templates, safe Markdown, bar charts and translated texts.

It is a library, not a service: nothing here listens on a port or opens a database.

## How it works

| Module | What it holds |
|---|---|
| `blocks.py` | `BaseBlockRenderer`, `BlockResult`, `InvalidBlockType`, `SOURCES`, the common options every block accepts |
| `tools.py` | `BaseToolRenderer`, `ToolRun`, `normalise_tool_name`, `tool_keys`, `headline_items` |
| `templating.py` | `render_package_template(package, path, **context)` and `render_class_template(cls, path, **context)`: Jinja templates from a plugin's own folder, autoescaped |
| `richtext.py` | `render(text)`: a small Markdown dialect to HTML cleaned against an allowlist; never raises |
| `charts.py` | `svg(spec, colours)`: bar and horizontal bar charts as inline SVG, deterministic; without `axis_min` the axis reaches a negative value, and bars start at zero |
| `i18n.py` | message catalogues (`i18n/<code>.json` in a package), `translator`, `translator_for`, `format_number`, `format_percent` |
| `base_report_plugin.py` | `BaseReporterPlugin`, the legacy plugin contract (needs SQLAlchemy; imported only when used) |

`INTERFACE_VERSION` is 2.

**Block types.** A subclass of `BaseBlockRenderer` declares `type_id` (a lowercase slug), `title`,
`contract_version` (an integer from 1), `options_schema` (JSON Schema draft 2020-12),
`default_options` and `reads`, the data sources it reads among `SOURCES` (`platform`,
`qualification`, `control_objectives`, `engine`, `controls`, `superset`). Optional: `description`
(one sentence for the composer's palette), `new_instance_options`, `choice_options` with
`choices(ctx, option_name)`. It implements `load(ctx, options)` and `render(data, options, ctx)`,
which returns a `BlockResult(html, status, notices)`: an HTML fragment (never a whole document) and a
status among `ok`, `empty`, `stale` and `error`. Every block also accepts the common options `title`,
`page_break_before`, `commentary` and `commentary_position`. `validate_declaration()` checks a class
against the contract; `options_problems(options)` lists invalid options as `{pointer, message}`.
The composer understands the schema annotations described in the docstring of `blocks.py`
(`x-aisc-enum-labels`, `x-aisc-more`, `x-aisc-show-if`, `x-aisc-reference`, `x-aisc-prose`).

**Tool renderers.** A subclass of `BaseToolRenderer` draws one plugin run inside the Test results
block. It declares `tool_names`, implements `render(run, ctx)` (an HTML fragment; tool options are in
`getattr(ctx, "tool_options", {})`) and may implement `verdict(run)` (`"pass"`, `"fail"` or `None`).
With `contract_version = 2` it can also give `headline(run, ctx=None)` (up to four key numbers) and
`charts(run)` (chart specs, named in `chart_ids`). A renderer is matched to the engine's plugin by
normalised names (`tool_keys`: display name, class name with or without a trailing `Plugin` or
`EvaluationPlugin`, package name without `aisc-plugin-`). A `ToolRun` is read-only and carries no
database session: the evaluation, the plugin, the tool, components, observations, measurements,
artifacts, and `target`, what the run assessed (`{key, kind, component_kind, label, card_version,
status}`, kind `system` or `component`, status `current`, `stale` or `not a target`), or `None`.

**How the renderer finds plugins.** Through the entry-point groups `aisc_report.blocks` and
`aisc_report.tools` of installed packages:

```toml
[project.entry-points."aisc_report.tools"]
mytool = "my_package:MyToolRenderer"
```

and through the plugin directories of `REPORT_PLUGIN_PATH` (set on the renderer, not read by this
library): each `.py` file or package folder there is imported and its block types, tool renderers and
legacy `<KEY>ReportPlugin` classes are registered. Two declarations of one block type, or two
renderers of one tool, stop the renderer at start.

Templates go next to the plugin's code and are rendered with `self.render_package_template(path,
**context)`. The path is relative to the folder of the module the renderer class is defined in (a
package's own folder for a class in its `__init__`, the file's folder for a one-file plugin) and may not
contain `..`. Autoescape is on
for every extension, `.html.j2` included.

**The legacy contract.** `BaseReporterPlugin` is the contract of the earlier report generator: a
class named `<KEY>ReportPlugin` implements `get_template_relative_path()` and
`build_template_context(**kwargs)`, and `generate_content(**kwargs)` renders the template. The report
renderer still runs such a class as a tool renderer for the tool `<KEY>` (with `db_session=None`)
when no real tool renderer claims that tool. Its shared templates folder, `resources/templates`, is
looked up in the parent folders of the installed package; when rendering fails, `generate_content`
returns a string starting with `[ERROR]`. New plugins use `BaseToolRenderer`.

## Install

Requires Python 3.12 or newer. Dependencies: `jinja2`, `jsonschema`, `markdown-it-py`, `nh3` and
`sqlalchemy` (the last for the legacy class only).

The package is not on PyPI. Install it from git:

```bash
uv add git+https://github.com/lux-ai-factory/aisc-report-plugin-interface --branch feat/unified-modules
```

or from a checkout, as the report renderer does in its `pyproject.toml`:

```toml
[tool.uv.sources]
aisc-report-plugin-interface = { path = "../../shared/report-plugin-interface", editable = true }
```

### Inside the AISC stack

The library has no compose service of its own. The `report-renderer` service in
`docker-compose.development.yml` builds its image from `apps/report-generator` with this folder as the
extra build context `interface` (override with `REPORT_INTERFACE_DIR`); the Dockerfile copies it to
`/aisc/shared/report-plugin-interface` and installs it. The code is copied at build time, so a change
here reaches the stack only after the image is rebuilt: from the aisc repo root, after
`./scripts/secrets.sh` has been run once, use the `docker compose ... up` command of the aisc README
with `--build report-renderer`.

## Configuration

The library reads no environment variables and no files at import time. Plugin directories, data
sources and the report context are the renderer's; see `apps/report-generator/README.md`.

## Tests

The tests need no database, no network and no running stack.

```bash
uv run --extra dev pytest -q
```

No test reads the package's comments or docstrings; `tests/test_prose_annotation.py` checks the `x-aisc-prose`
annotation on the common options themselves.

## Layout

```text
aisc_report_plugin_interface/   the library (see the table above)
tests/                          contract tests; fake_block_pkg/ and fake_i18n_pkg/ are sample plugin packages
```

## Contributing

`feat/unified-modules` is the branch the AISC stack uses and the only one to work on. A test
(`tests/test_target.py`) requires the version in `pyproject.toml` to be at least 0.2.0, the version
that added `ToolRun.target`.
