"""The project was renamed from VERA to AISC: the package installs and imports under the AISC name."""


def test_package_is_installed_and_imported_as_aisc():
    import importlib.metadata

    import aisc_report_plugin_interface  # noqa: F401

    assert importlib.metadata.distribution("aisc-report-plugin-interface")
