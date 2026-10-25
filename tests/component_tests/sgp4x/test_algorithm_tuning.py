"""The NOx algorithm has no std_initial parameter; VOC keeps it."""

import pytest

from esphome.components.sgp4x.sensor import NOX_SENSOR, VOC_SENSOR
from esphome.const import CONF_ALGORITHM_TUNING, CONF_STD_INITIAL


def test_nox_std_initial_is_dropped_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = NOX_SENSOR({CONF_ALGORITHM_TUNING: {CONF_STD_INITIAL: 50}})
    assert CONF_STD_INITIAL not in config[CONF_ALGORITHM_TUNING]
    assert "'std_initial' has no effect on the NOx algorithm" in caplog.text
    assert "2027.5.0" in caplog.text


def test_nox_tuning_without_std_initial_is_quiet(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = NOX_SENSOR({CONF_ALGORITHM_TUNING: {"index_offset": 1}})
    assert CONF_STD_INITIAL not in config[CONF_ALGORITHM_TUNING]
    assert "std_initial" not in caplog.text


def test_voc_tuning_keeps_std_initial_default() -> None:
    config = VOC_SENSOR({CONF_ALGORITHM_TUNING: {}})
    assert config[CONF_ALGORITHM_TUNING][CONF_STD_INITIAL] == 50
