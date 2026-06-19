import esphome.codegen as cg
from esphome.components import light
import esphome.config_validation as cv
from esphome.const import (
    CONF_MAX_REFRESH_RATE,
    CONF_NUM_LEDS,
    CONF_OUTPUT_ID,
    CONF_RGB_ORDER,
)
from esphome.core import CORE

CODEOWNERS = ["@OttoWinter"]
fastled_base_ns = cg.esphome_ns.namespace("fastled_base")
FastLEDLightOutput = fastled_base_ns.class_(
    "FastLEDLightOutput", light.AddressableLight
)

RGB_ORDERS = [
    "RGB",
    "RBG",
    "GRB",
    "GBR",
    "BRG",
    "BGR",
]

BASE_SCHEMA = light.ADDRESSABLE_LIGHT_SCHEMA.extend(
    {
        cv.GenerateID(CONF_OUTPUT_ID): cv.declare_id(FastLEDLightOutput),
        cv.Required(CONF_NUM_LEDS): cv.positive_not_null_int,
        cv.Optional(CONF_RGB_ORDER): cv.one_of(*RGB_ORDERS, upper=True),
        cv.Optional(CONF_MAX_REFRESH_RATE): cv.positive_time_period_microseconds,
    }
).extend(cv.COMPONENT_SCHEMA)


async def new_fastled_light(config):
    var = cg.new_Pvariable(config[CONF_OUTPUT_ID])
    await cg.register_component(var, config)

    if CONF_MAX_REFRESH_RATE in config:
        cg.add(var.set_max_refresh_rate(config[CONF_MAX_REFRESH_RATE]))

    if CORE.is_esp32:
        from esphome.components.esp32 import add_idf_component

        add_idf_component(
            name="fastled/FastLED",
            repo="https://github.com/FastLED/FastLED.git",
            ref="adedfc40e73fb80f8e930318781036d8fe1dbd9f",  # 3.10.4
        )
        cg.add_library("SPI", None)
        # WS2812B on the classic ESP32 (no RMT DMA) goes black with FastLED's
        # default RMT5 "BALANCED" preset (timer-ISR refill). Force the LEGACY
        # preset (threshold-ISR refill) instead. See #17063.
        cg.add_build_flag("-DFASTLED_RMT5_PRESET_LEGACY")
    else:
        cg.add_library("fastled/FastLED", "3.9.16")
    await light.register_light(var, config)
    return var
