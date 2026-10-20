"""Helpers of the interface tests.

`want(module, name)` is `need` that also turns a missing MODULE into a failed test body
("missing feature: module ..."), so new modules (richtext, charts, i18n) never break collection.
"""
import importlib

import pytest


def want(module: str, name: str | None = None):
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name and (exc.name == module or module.startswith(exc.name + ".")):
            pytest.fail(f"missing feature: module {module}", pytrace=False)
        raise
    if name is None:
        return mod
    value = getattr(mod, name, None)
    if value is None:
        pytest.fail(f"missing feature: {module}.{name}", pytrace=False)
    return value
