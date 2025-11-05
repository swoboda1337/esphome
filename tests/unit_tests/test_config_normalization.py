"""Unit tests for esphome.config module."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from esphome import config, yaml_util
from esphome.core import CORE


@pytest.fixture
def mock_get_platform() -> Generator[Mock, None, None]:
    """Fixture for mocking get_platform."""
    with patch("esphome.config.get_platform") as mock_get_platform:
        # Default mock platform
        mock_get_platform.return_value = MagicMock()
        yield mock_get_platform


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the fixtures directory."""
    return Path(__file__).parent / "fixtures"


def test_ota_component_configs_with_proper_platform_list(
    mock_get_component: Mock,
    mock_get_platform: Mock,
) -> None:
    """Test iter_component_configs handles OTA properly configured as a list."""
    test_config = {
        "ota": [
            {"platform": "esphome", "password": "test123", "id": "my_ota"},
        ],
    }

    mock_get_component.return_value = MagicMock(
        is_platform_component=True, multi_conf=False
    )

    configs = list(config.iter_component_configs(test_config))
    assert len(configs) == 2

    assert configs[0][0] == "ota"
    assert configs[0][2] == test_config["ota"]  # The list itself

    assert configs[1][0] == "ota.esphome"
    assert configs[1][2]["platform"] == "esphome"
    assert configs[1][2]["password"] == "test123"


def test_iter_component_configs_with_multi_conf(mock_get_component: Mock) -> None:
    """Test that iter_component_configs handles multi_conf components correctly."""
    test_config = {
        "switch": [
            {"name": "Switch 1"},
            {"name": "Switch 2"},
        ],
    }

    mock_get_component.return_value = MagicMock(
        is_platform_component=False, multi_conf=True
    )

    configs = list(config.iter_component_configs(test_config))
    assert len(configs) == 2

    for domain, component, conf in configs:
        assert domain == "switch"
        assert "name" in conf


def test_ota_no_platform_with_captive_portal(fixtures_dir: Path) -> None:
    """Test OTA with no platform (ota:) gets normalized when captive_portal auto-loads."""
    CORE.config_path = fixtures_dir / "dummy.yaml"

    config_file = fixtures_dir / "ota_no_platform.yaml"
    raw_config = yaml_util.load_yaml(config_file)
    result = config.validate_config(raw_config, {})

    assert "ota" in result
    assert isinstance(result["ota"], list), f"Expected list, got {type(result['ota'])}"
    platforms = {p.get("platform") for p in result["ota"]}
    assert "web_server" in platforms, f"Expected web_server platform in {platforms}"


def test_ota_empty_dict_with_captive_portal(fixtures_dir: Path) -> None:
    """Test OTA with empty dict ({}) gets normalized when captive_portal auto-loads."""
    CORE.config_path = fixtures_dir / "dummy.yaml"

    config_file = fixtures_dir / "ota_empty_dict.yaml"
    raw_config = yaml_util.load_yaml(config_file)
    result = config.validate_config(raw_config, {})

    assert "ota" in result
    assert isinstance(result["ota"], list), f"Expected list, got {type(result['ota'])}"
    platforms = {p.get("platform") for p in result["ota"]}
    assert "web_server" in platforms, f"Expected web_server platform in {platforms}"


def test_ota_with_platform_list_and_captive_portal(fixtures_dir: Path) -> None:
    """Test OTA with proper platform list remains valid when captive_portal auto-loads."""
    CORE.config_path = fixtures_dir / "dummy.yaml"

    config_file = fixtures_dir / "ota_with_platform_list.yaml"
    raw_config = yaml_util.load_yaml(config_file)
    result = config.validate_config(raw_config, {})

    assert "ota" in result
    assert isinstance(result["ota"], list), f"Expected list, got {type(result['ota'])}"
    platforms = {p.get("platform") for p in result["ota"]}
    assert "esphome" in platforms, f"Expected esphome platform in {platforms}"
    assert "web_server" in platforms, f"Expected web_server platform in {platforms}"


def test_platform_config_strips_unused_id(fixtures_dir: Path) -> None:
    """Test that platforms without id in schema can have id stripped for !remove functionality."""
    config_file = fixtures_dir / "wifi_info_with_id.yaml"
    CORE.config_path = config_file

    raw_config = yaml_util.load_yaml(config_file)
    result = config.validate_config(raw_config, {})

    # The config should validate successfully even though wifi_info doesn't have id in its schema
    # The id field should be silently stripped during validation
    assert not result.errors, f"Expected no errors, but got: {result.errors}"
    assert "text_sensor" in result


def test_platform_config_allows_remove_with_id(fixtures_dir: Path) -> None:
    """Test that !remove works on platforms that have id field for merge/include use case."""
    config_file = fixtures_dir / "wifi_info_remove_test.yaml"
    CORE.config_path = config_file

    raw_config = yaml_util.load_yaml(config_file)
    result = config.validate_config(raw_config, {})

    # The config should validate successfully and the wifi_info platform should be removed
    assert not result.errors, f"Expected no errors, but got: {result.errors}"
    assert "text_sensor" in result
    # wifi_info should have been removed, so text_sensor list should be empty
    assert isinstance(result["text_sensor"], list)
    assert len(result["text_sensor"]) == 0
