"""Tests for the captive portal OTA authentication warning in web_server.ota."""

from __future__ import annotations

import logging

import pytest

from esphome import final_validate as fv
from esphome.components.web_server.ota import _web_server_ota_final_validate
from esphome.const import CONF_AP, CONF_AUTH, CONF_PASSWORD, CONF_WEB_SERVER

WARNING = "without authentication"


def _final_validate(full_conf: dict) -> None:
    token = fv.full_config.set(full_conf)
    try:
        _web_server_ota_final_validate({})
    finally:
        fv.full_config.reset(token)


def _run(caplog: pytest.LogCaptureFixture, full_conf: dict) -> bool:
    caplog.set_level(logging.WARNING, logger="esphome.components.web_server.ota")
    _final_validate(full_conf)
    return WARNING in caplog.text


def test_warns_on_open_ap_without_web_server_auth(
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert _run(
        caplog,
        {"captive_portal": {}, "wifi": {CONF_AP: {"ssid": "Fallback"}}},
    )


def test_warns_when_web_server_has_no_auth(caplog: pytest.LogCaptureFixture) -> None:
    assert _run(
        caplog,
        {
            "captive_portal": {},
            "wifi": {CONF_AP: {"ssid": "Fallback"}},
            CONF_WEB_SERVER: {"port": 80},
        },
    )


def test_silent_without_captive_portal(caplog: pytest.LogCaptureFixture) -> None:
    assert not _run(caplog, {"wifi": {CONF_AP: {"ssid": "Fallback"}}})


def test_silent_with_ap_password(caplog: pytest.LogCaptureFixture) -> None:
    assert not _run(
        caplog,
        {
            "captive_portal": {},
            "wifi": {CONF_AP: {"ssid": "Fallback", CONF_PASSWORD: "hunter22"}},
        },
    )


def test_silent_with_web_server_auth(caplog: pytest.LogCaptureFixture) -> None:
    assert not _run(
        caplog,
        {
            "captive_portal": {},
            "wifi": {CONF_AP: {"ssid": "Fallback"}},
            CONF_WEB_SERVER: {CONF_AUTH: {"username": "u", CONF_PASSWORD: "p"}},
        },
    )


def test_silent_without_ap(caplog: pytest.LogCaptureFixture) -> None:
    assert not _run(caplog, {"captive_portal": {}, "wifi": {}})
