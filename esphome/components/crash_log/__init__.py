import esphome.codegen as cg
from esphome.config_helpers import filter_source_files_from_platform
import esphome.config_validation as cv
from esphome.const import CONF_BUFFER_SIZE, CONF_ID, PlatformFramework

CODEOWNERS = ["@swoboda1337"]
DEPENDENCIES = ["logger"]

# Only supported on Zephyr/nRF52 for now
PLATFORMS = ["nrf52"]

FILTER_SOURCE_FILES = filter_source_files_from_platform(
    {
        "crash_log_zephyr.cpp": {PlatformFramework.NRF52_ZEPHYR},
    }
)

CONF_DUMP_AT_BOOT = "dump_at_boot"

crash_log_ns = cg.esphome_ns.namespace("crash_log")
CrashLog = crash_log_ns.class_("CrashLog", cg.Component)

CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(CrashLog),
            cv.Optional(CONF_BUFFER_SIZE, default=4096): cv.All(
                cv.positive_int, cv.Range(min=256, max=16384)
            ),
            cv.Optional(CONF_DUMP_AT_BOOT, default=True): cv.boolean,
        }
    ).extend(cv.COMPONENT_SCHEMA),
    cv.only_on(["nrf52"]),
)


async def to_code(config):
    # The .noinit section is handled by the linker - no special Kconfig needed
    # Zephyr's default linker script includes .noinit in RAM that isn't zeroed

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_buffer_size(config[CONF_BUFFER_SIZE]))
    cg.add(var.set_dump_at_boot(config[CONF_DUMP_AT_BOOT]))

    cg.add_define("USE_CRASH_LOG")
    cg.add_define("CRASH_LOG_BUFFER_SIZE", config[CONF_BUFFER_SIZE])
