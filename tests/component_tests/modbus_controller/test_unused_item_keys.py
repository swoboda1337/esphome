"""Read-side item keys are dropped with a warning on outputs and text sensors."""

import pytest

from esphome.components.modbus_controller import output, text_sensor
from esphome.components.modbus_controller.const import CONF_BITMASK, CONF_RESPONSE_SIZE
from esphome.const import CONF_ADDRESS, CONF_NAME


@pytest.mark.parametrize("register_type", ["holding", "coil"])
def test_output_drops_bitmask_and_response_size(
    register_type: str, caplog: pytest.LogCaptureFixture
) -> None:
    config = output.CONFIG_SCHEMA(
        {
            "register_type": register_type,
            CONF_ADDRESS: 1,
            CONF_BITMASK: 0x80,
            CONF_RESPONSE_SIZE: 4,
        }
    )
    assert CONF_BITMASK not in config
    assert CONF_RESPONSE_SIZE not in config
    assert "'bitmask' has no effect on outputs" in caplog.text
    assert "'response_size' has no effect on outputs" in caplog.text


def test_output_without_read_keys_is_quiet(caplog: pytest.LogCaptureFixture) -> None:
    config = output.CONFIG_SCHEMA({"register_type": "holding", CONF_ADDRESS: 1})
    assert CONF_BITMASK not in config
    assert "has no effect on outputs" not in caplog.text


def test_text_sensor_drops_bitmask(caplog: pytest.LogCaptureFixture) -> None:
    config = text_sensor.CONFIG_SCHEMA(
        {
            CONF_NAME: "Register 1002",
            "register_type": "holding",
            CONF_ADDRESS: 1002,
            CONF_BITMASK: 0,
        }
    )
    assert CONF_BITMASK not in config
    assert config[CONF_RESPONSE_SIZE] == 2
    assert "Register 1002: 'bitmask' has no effect on text sensors" in caplog.text
    assert "2027.5.0" in caplog.text
