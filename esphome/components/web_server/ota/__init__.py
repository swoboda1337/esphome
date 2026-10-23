import logging

import esphome.codegen as cg
from esphome.components.captive_portal import DOMAIN as CAPTIVE_PORTAL_DOMAIN
from esphome.components.esp32 import add_idf_component
from esphome.components.ota import (
    BASE_OTA_SCHEMA,
    DOMAIN as OTA_DOMAIN,
    OTAComponent,
    ota_to_code,
)
from esphome.components.wifi import DOMAIN as WIFI_DOMAIN
from esphome.config_helpers import merge_config
import esphome.config_validation as cv
from esphome.const import (
    CONF_AP,
    CONF_AUTH,
    CONF_ID,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_WEB_SERVER,
)
from esphome.core import CORE, coroutine_with_priority
from esphome.coroutine import CoroPriority
import esphome.final_validate as fv
from esphome.types import ConfigType

from .. import DOMAIN

_LOGGER = logging.getLogger(__name__)

CODEOWNERS = ["@esphome/core"]
DEPENDENCIES = ["network", "web_server_base"]

web_server_ns = cg.esphome_ns.namespace("web_server")
WebServerOTAComponent = web_server_ns.class_("WebServerOTAComponent", OTAComponent)


def _warn_unauthenticated_captive_portal_ota(full_conf: ConfigType) -> None:
    """Warn when the captive portal serves /update on an open AP with no login."""
    if CAPTIVE_PORTAL_DOMAIN not in full_conf:
        return
    web_server_conf = full_conf.get(CONF_WEB_SERVER)
    if web_server_conf is not None and CONF_AUTH in web_server_conf:
        return
    ap_conf = full_conf.get(WIFI_DOMAIN, {}).get(CONF_AP)
    if ap_conf is None or ap_conf.get(CONF_PASSWORD):
        return
    _LOGGER.warning(
        "'%s' serves the %s OTA '/update' endpoint on the open fallback access "
        "point without authentication. Set a '%s' on 'wifi.%s' or configure "
        "'%s.%s' so firmware uploads require a login",
        CAPTIVE_PORTAL_DOMAIN,
        CONF_WEB_SERVER,
        CONF_PASSWORD,
        CONF_AP,
        CONF_WEB_SERVER,
        CONF_AUTH,
    )


def _web_server_ota_final_validate(config: ConfigType) -> None:
    """Merge multiple web_server OTA instances into one.

    Multiple web_server OTA instances register duplicate HTTP handlers for /update,
    causing undefined behavior. Merge them into a single instance.
    """
    full_conf = fv.full_config.get()
    _warn_unauthenticated_captive_portal_ota(full_conf)
    ota_confs = full_conf.get(OTA_DOMAIN, [])

    web_server_ota_configs: list[ConfigType] = []
    other_ota_configs: list[ConfigType] = []

    for ota_conf in ota_confs:
        if ota_conf.get(CONF_PLATFORM) == DOMAIN:
            web_server_ota_configs.append(ota_conf)
        else:
            other_ota_configs.append(ota_conf)

    if len(web_server_ota_configs) <= 1:
        return

    # Merge all web_server OTA configs into the first one
    merged = web_server_ota_configs[0]
    for ota_conf in web_server_ota_configs[1:]:
        # Validate that IDs are consistent if manually specified
        if (
            merged[CONF_ID].is_manual
            and ota_conf[CONF_ID].is_manual
            and merged[CONF_ID] != ota_conf[CONF_ID]
        ):
            raise cv.Invalid(
                f"Found multiple web_server OTA configurations but {CONF_ID} is inconsistent"
            )
        merged = merge_config(merged, ota_conf)

    _LOGGER.warning(
        "Found and merged %d web_server OTA configurations into one instance",
        len(web_server_ota_configs),
    )

    # Replace OTA configs with merged web_server + other OTA platforms
    other_ota_configs.append(merged)
    full_conf[OTA_DOMAIN] = other_ota_configs
    fv.full_config.set(full_conf)


CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(WebServerOTAComponent),
        }
    )
    .extend(BASE_OTA_SCHEMA)
    .extend(cv.COMPONENT_SCHEMA)
)

FINAL_VALIDATE_SCHEMA = _web_server_ota_final_validate


@coroutine_with_priority(CoroPriority.WEB_SERVER_OTA)
async def to_code(config: ConfigType) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await ota_to_code(var, config)
    await cg.register_component(var, config)
    cg.add_define("USE_WEBSERVER_OTA")
    if CORE.is_esp32:
        add_idf_component(name="zorxx/multipart-parser", ref="1.0.1")
