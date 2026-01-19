from dataclasses import dataclass, field
import re

from esphome import config_validation as cv
from esphome.const import CONF_ARGS, CONF_FORMAT
from esphome.core import CORE

CONF_IF_NAN = "if_nan"
DOMAIN = "lvgl"

# Default LV uses that are always required
DEFAULT_LV_USES = frozenset(
    {
        "USER_DATA",
        "LOG",
        "STYLE",
        "FONT_PLACEHOLDER",
        "THEME_DEFAULT",
    }
)


@dataclass
class LvglData:
    """State for LVGL component stored in CORE.data."""

    lv_uses: set[str] = field(default_factory=lambda: set(DEFAULT_LV_USES))
    lv_fonts_used: set[str] = field(default_factory=set)
    esphome_fonts_used: set[str] = field(default_factory=set)
    lvgl_components_required: set[str] = field(default_factory=set)
    lv_images_used: set = field(default_factory=set)
    focused_widgets: set = field(default_factory=set)
    refreshed_widgets: set = field(default_factory=set)
    theme_widget_map: dict = field(default_factory=dict)
    styles_used: set[str] = field(default_factory=set)
    lv_defines: dict[str, str] = field(default_factory=dict)
    updated_widgets: dict = field(default_factory=dict)


def get_lvgl_data() -> LvglData:
    """Get or create LVGL data in CORE.data."""
    if DOMAIN not in CORE.data:
        CORE.data[DOMAIN] = LvglData()
    return CORE.data[DOMAIN]


def add_lv_use(*names):
    data = get_lvgl_data()
    for name in names:
        data.lv_uses.add(name)


# noqa
f_regex = re.compile(
    r"""
    (                                  # start of capture group 1
    %                                  # literal "%"
    [-+0 #]{0,5}                   # optional flags
    (?:\d+|\*)?                        # width
    (?:\.(?:\d+|\*))?                  # precision
    (?:h|l|ll|w|I|I32|I64)?            # size
    f                                  # type
    )
    """,
    flags=re.VERBOSE,
)
# noqa
c_regex = re.compile(
    r"""
    (                                  # start of capture group 1
    %                                  # literal "%"
    [-+0 #]{0,5}                   # optional flags
    (?:\d+|\*)?                        # width
    (?:\.(?:\d+|\*))?                  # precision
    (?:h|l|ll|w|I|I32|I64)?            # size
    [cCdiouxXeEfgGaAnpsSZ]             # type
    )
    """,
    flags=re.VERBOSE,
)


def validate_printf(value):
    format_string = value[CONF_FORMAT]
    matches = c_regex.findall(format_string)
    if len(matches) != len(value[CONF_ARGS]):
        raise cv.Invalid(
            f"Found {len(matches)} printf-patterns ({', '.join(matches)}), but {len(value[CONF_ARGS])} args were given!"
        )

    if value.get(CONF_IF_NAN) and len(f_regex.findall(format_string)) != 1:
        raise cv.Invalid(
            "Use of 'if_nan' requires a single valid printf-pattern of type %f"
        )
    return value


def requires_component(comp):
    def validator(value):
        get_lvgl_data().lvgl_components_required.add(comp)
        return cv.requires_component(comp)(value)

    return validator
