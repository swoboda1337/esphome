"""Unit tests for script/ci_check_schema_coverage.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import textwrap

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "script"
    / "ci_check_schema_coverage.py"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "ci_check_schema_coverage", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_cov = _load_script_module()


def _write_component(tmp_path: Path, files: dict[str, str]) -> Path:
    component = tmp_path / "my_comp"
    component.mkdir()
    for name, source in files.items():
        target = component / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(source), encoding="utf-8")
    return component


def test_declared_keys_literal_and_constant(tmp_path: Path) -> None:
    component = _write_component(
        tmp_path,
        {
            "__init__.py": """
                import esphome.config_validation as cv

                CONF_FOO = "foo"

                CONFIG_SCHEMA = cv.Schema(
                    {
                        cv.Required(CONF_FOO): cv.string,
                        cv.Optional("bar", default=1): cv.int_,
                        cv.GenerateID(): cv.declare_id(object),
                    }
                )
            """,
        },
    )
    keys = _cov.declared_keys(component)
    assert set(keys) == {"foo", "bar"}
    assert keys["foo"][0][1] == 8


def test_declared_keys_skips_removed_keys(tmp_path: Path) -> None:
    component = _write_component(
        tmp_path,
        {
            "__init__.py": """
                import esphome.config_validation as cv

                CONFIG_SCHEMA = cv.Schema(
                    {
                        cv.Optional("old"): cv.invalid("removed"),
                        cv.Optional("new"): cv.string,
                    }
                )
            """,
        },
    )
    assert set(_cov.declared_keys(component)) == {"new"}


def test_declared_keys_resolves_relative_and_aliased_imports(tmp_path: Path) -> None:
    component = _write_component(
        tmp_path,
        {
            "__init__.py": "",
            "const.py": 'CONF_ALPHA = "alpha"\n',
            "defines.py": 'CONF_BETA = "beta"\n',
            "sensor.py": """
                import esphome.config_validation as cv

                from . import defines as df
                from .const import CONF_ALPHA

                CONFIG_SCHEMA = cv.Schema(
                    {
                        cv.Optional(CONF_ALPHA): cv.string,
                        cv.Optional(df.CONF_BETA): cv.string,
                    }
                )
            """,
        },
    )
    assert set(_cov.declared_keys(component)) == {"alpha", "beta"}


def test_schema_keys_include_nested_and_typed(tmp_path: Path) -> None:
    (tmp_path / "x.json").write_text(
        '{"x": {"schemas": {"CONFIG_SCHEMA": {"type": "typed", "typed_key": "kind",'
        ' "types": {"a": {"config_vars": {"inner": {"schema": {"config_vars":'
        ' {"deep": {}}}}}}}}}}}',
        encoding="utf-8",
    )
    assert _cov.schema_keys_from_dir(tmp_path) == {"kind", "inner", "deep"}
