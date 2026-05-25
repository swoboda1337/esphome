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

    # Pinned to a master SHA past the IDF 6 guards (i2s_esp32dev moved out
    # of the compiled-source list and feature_flags/enabled.h now disables
    # the I2S driver on IDF >= 6 where PERIPH_I2S1_MODULE was removed; LCD
    # I80 driver files marked .disabled). The last tagged release (3.10.3,
    # 2025-09-20) predates those fixes.
    cg.add_library(
        "FastLED",
        None,
        "https://github.com/FastLED/FastLED.git#f7d4b0e51c6d2636942d8816d67a2270ab6c71ba",
    )
    if CORE.is_esp32:
        from esphome.components.esp32 import include_builtin_idf_component

        include_builtin_idf_component("esp_lcd")
    await light.register_light(var, config)
    return var
