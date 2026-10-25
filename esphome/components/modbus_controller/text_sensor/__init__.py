import logging

import esphome.codegen as cg
from esphome.components import text_sensor
from esphome.components.modbus.helpers import MODBUS_REGISTER_TYPE
import esphome.config_validation as cv
from esphome.const import CONF_ADDRESS, CONF_ID
from esphome.types import ConfigType

from .. import (
    RANGE_REUSE,
    ModbusItemBaseSchema,
    SensorItem,
    add_modbus_base_properties,
    entity_label,
    modbus_calc_properties,
    modbus_controller_ns,
    validate_custom_pdu_item,
    validate_modbus_register,
    validate_range_reuse_migration,
)
from ..const import (
    CONF_BITMASK,
    CONF_MODBUS_CONTROLLER_ID,
    CONF_RAW_ENCODE,
    CONF_REGISTER_TYPE,
    CONF_RESPONSE_SIZE,
    CONF_REUSE_PREVIOUS_RANGE,
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["modbus_controller"]
CODEOWNERS = ["@martgras"]


def _warn_unused_bitmask(config: ConfigType) -> ConfigType:
    # The register bytes are decoded as text, so there is no numeric value to mask.
    if config.pop(CONF_BITMASK, None) is not None:
        _LOGGER.warning(
            "%s: '%s' has no effect on text sensors; remove it. Removed in 2027.5.0",
            entity_label(config),
            CONF_BITMASK,
        )
    return config


ModbusTextSensor = modbus_controller_ns.class_(
    "ModbusTextSensor", cg.Component, text_sensor.TextSensor, SensorItem
)

RawEncoding_ns = modbus_controller_ns.namespace("RawEncoding")
RawEncoding = RawEncoding_ns.enum("RawEncoding")
RAW_ENCODING = RawEncoding.options("NONE", "HEXBYTES", "COMMA", "ANSI")

CONFIG_SCHEMA = cv.All(
    text_sensor.text_sensor_schema()
    .extend(cv.COMPONENT_SCHEMA)
    .extend(ModbusItemBaseSchema)
    .extend(
        {
            cv.GenerateID(): cv.declare_id(ModbusTextSensor),
            cv.Optional(CONF_REGISTER_TYPE): cv.enum(MODBUS_REGISTER_TYPE),
            cv.Optional(CONF_RESPONSE_SIZE, default=2): cv.int_range(min=1, max=250),
            cv.Optional(CONF_RAW_ENCODE, default="ANSI"): cv.enum(RAW_ENCODING),
            cv.Optional(CONF_BITMASK): cv.hex_uint32_t,
        }
    ),
    _warn_unused_bitmask,
    validate_modbus_register,
    validate_range_reuse_migration,
)

FINAL_VALIDATE_SCHEMA = validate_custom_pdu_item


async def to_code(config):
    byte_offset = modbus_calc_properties(config)
    var = cg.new_Pvariable(
        config[CONF_ID],
        config[CONF_REGISTER_TYPE],
        config[CONF_ADDRESS],
        byte_offset,
        config[CONF_RESPONSE_SIZE],
        config[CONF_RAW_ENCODE],
        RANGE_REUSE[config[CONF_REUSE_PREVIOUS_RANGE]],
    )

    await cg.register_component(var, config)
    await text_sensor.register_text_sensor(var, config)

    paren = await cg.get_variable(config[CONF_MODBUS_CONTROLLER_ID])
    cg.add(paren.add_sensor_item(var))
    await add_modbus_base_properties(
        var, config, ModbusTextSensor, cg.std_string, cg.std_string
    )
