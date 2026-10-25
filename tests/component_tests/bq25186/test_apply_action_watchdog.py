"""bq25186.apply_configuration is checked against its charger's poll interval during validation."""

from collections.abc import Iterator

import pytest

from esphome import config_validation as cv
from esphome.components.bq25186 import (
    CONF_WATCHDOG_15S_ENABLE,
    CONFIG_SCHEMA,
    CONFIGURE_ACTION_SCHEMA,
    DOMAIN,
    FINAL_VALIDATE_SCHEMA,
    _get_data,
)
from esphome.config import path_context
from esphome.const import CONF_ID, CONF_UPDATE_INTERVAL, CONF_WATCHDOG
from esphome.core import CORE
from esphome.types import ConfigType

ACTION_PATH = ["button", 0, "on_press", "then", 1]


@pytest.fixture(autouse=True)
def _action_context() -> Iterator[None]:
    CORE.data.pop(DOMAIN, None)
    token = path_context.set(ACTION_PATH)
    yield
    path_context.reset(token)
    CORE.data.pop(DOMAIN, None)


def _charger(**options: object) -> ConfigType:
    return CONFIG_SCHEMA({CONF_ID: "charger", CONF_UPDATE_INTERVAL: "60s", **options})


def test_action_is_recorded_with_its_path() -> None:
    config = CONFIGURE_ACTION_SCHEMA("charger")
    (ref,) = _get_data().apply_refs
    assert ref.config is config
    assert ref.component_path == ACTION_PATH


def test_action_tightening_the_watchdog_is_rejected_at_the_action() -> None:
    charger = _charger()
    CONFIGURE_ACTION_SCHEMA({CONF_ID: "charger", CONF_WATCHDOG: "40s_hardware_reset"})
    with pytest.raises(
        cv.FinalExternalInvalid, match="40 s.*charger polls every 60s"
    ) as err:
        FINAL_VALIDATE_SCHEMA(charger)
    assert err.value.path == [cv.ROOT_CONFIG_PATH, *ACTION_PATH]


def test_action_enabling_the_15s_watchdog_is_rejected() -> None:
    charger = _charger()
    CONFIGURE_ACTION_SCHEMA({CONF_ID: "charger", CONF_WATCHDOG_15S_ENABLE: True})
    with pytest.raises(cv.Invalid, match="15 s"):
        FINAL_VALIDATE_SCHEMA(charger)


def test_action_within_the_poll_interval_passes() -> None:
    charger = _charger(update_interval="30s")
    CONFIGURE_ACTION_SCHEMA({CONF_ID: "charger", CONF_WATCHDOG: "40s_hardware_reset"})
    CONFIGURE_ACTION_SCHEMA("charger")
    FINAL_VALIDATE_SCHEMA(charger)


def test_action_on_another_charger_is_ignored() -> None:
    charger = _charger()
    CONFIGURE_ACTION_SCHEMA({CONF_ID: "other", CONF_WATCHDOG: "40s_hardware_reset"})
    FINAL_VALIDATE_SCHEMA(charger)
