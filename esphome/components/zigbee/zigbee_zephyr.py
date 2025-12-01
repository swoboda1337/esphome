from datetime import datetime

from esphome import automation, core
import esphome.codegen as cg
from esphome.components.zephyr import zephyr_add_prj_conf
from esphome.const import CONF_ID, CONF_NAME, __version__
from esphome.core import CORE, ID
from esphome.cpp_generator import (
    AssignmentExpression,
    MockObj,
    VariableDeclarationExpression,
)
from esphome.types import ConfigType

from .const_zephyr import (
    CONF_ON_JOIN,
    CONF_WIPE_ON_BOOT,
    CONF_ZIGBEE_ID,
    ESPHOME_ZB_HA_DECLARE_EP,
    KEY_BASIC_ATTRIB_LIST,
    KEY_EP_NUMBER,
    KEY_IDENTIFY_ATTRIB_LIST,
    KEY_ZIGBEE,
    ZB_ZCL_CLUSTER_ID_BASIC,
    ZB_ZCL_CLUSTER_ID_BINARY_INPUT,
    ZB_ZCL_CLUSTER_ID_IDENTIFY,
    ZB_ZCL_DECLARE_BASIC_ATTRIB_LIST_EXT,
    ZB_ZCL_DECLARE_IDENTIFY_ATTRIB_LIST,
    BinaryAttrs,
    zb_char_t_ptr,
    zb_zcl_basic_attrs_ext_t,
    zb_zcl_identify_attrs_t,
    zigbee_ns,
)

ZigbeeBinarySensor = zigbee_ns.class_("ZigbeeBinarySensor", cg.Component)


async def zephyr_to_code(config: ConfigType) -> None:
    zephyr_add_prj_conf("ZIGBEE", True)
    zephyr_add_prj_conf("ZIGBEE_APP_UTILS", True)
    zephyr_add_prj_conf("ZIGBEE_ROLE_END_DEVICE", True)

    zephyr_add_prj_conf("ZIGBEE_CHANNEL_SELECTION_MODE_MULTI", True)

    zephyr_add_prj_conf("CRYPTO", True)

    zephyr_add_prj_conf("NET_IPV6", False)
    zephyr_add_prj_conf("NET_IP_ADDR_CHECK", False)
    zephyr_add_prj_conf("NET_UDP", False)

    if config[CONF_WIPE_ON_BOOT]:
        cg.add_define("USE_ZIGBEE_WIPE_ON_BOOT")
    var = cg.new_Pvariable(config[CONF_ID])

    if on_join_config := config.get(CONF_ON_JOIN):
        await automation.build_automation(var.get_join_trigger(), [], on_join_config)

    await cg.register_component(var, config)

    # Generate the shared basic and identify attribute lists
    await _generate_shared_attrs()


async def _generate_shared_attrs() -> None:
    """Generate the shared basic and identify attribute lists used by all endpoints."""
    data = CORE.data.setdefault(KEY_ZIGBEE, {})

    # Create basic_attrs_ext variable
    basic_attrs_id = ID(
        "zigbee_basic_attrs", is_declaration=True, type=zb_zcl_basic_attrs_ext_t
    )
    basic_attrs = _new_variable(basic_attrs_id)

    # Create basic attrib list
    basic_attrib_list_id = ID(
        "zigbee_basic_attrib_list",
        is_declaration=True,
        type=ZB_ZCL_DECLARE_BASIC_ATTRIB_LIST_EXT,
    )
    _new_attr_list(
        basic_attrib_list_id,
        _assign(basic_attrs.zcl_version, cg.global_ns.namespace("ZB_ZCL_VERSION")),
        _assign(basic_attrs.app_version, 0),
        _assign(basic_attrs.stack_version, 0),
        _assign(basic_attrs.hw_version, 0),
        _set_string(basic_attrs.mf_name, "esphome"),
        _set_string(basic_attrs.model_id, CORE.name),
        _set_string(basic_attrs.date_code, datetime.now().strftime("%d/%m/%y %H:%M")),
        _assign(
            basic_attrs.power_source,
            cg.global_ns.namespace("ZB_ZCL_BASIC_POWER_SOURCE_DC_SOURCE"),
        ),
        _set_string(basic_attrs.location_id, ""),
        _assign(
            basic_attrs.ph_env, cg.global_ns.namespace("ZB_ZCL_BASIC_ENV_UNSPECIFIED")
        ),
        _set_string(basic_attrs.sw_ver, __version__),
    )
    # Store for use by binary sensors
    data[KEY_BASIC_ATTRIB_LIST] = basic_attrib_list_id

    # Create identify_attrs variable
    identify_attrs_id = ID(
        "zigbee_identify_attrs", is_declaration=True, type=zb_zcl_identify_attrs_t
    )
    identify_attrs = _new_variable(identify_attrs_id)

    # Create identify attrib list
    identify_attrib_list_id = ID(
        "zigbee_identify_attrib_list",
        is_declaration=True,
        type=ZB_ZCL_DECLARE_IDENTIFY_ATTRIB_LIST,
    )
    _new_attr_list(
        identify_attrib_list_id,
        _assign(
            identify_attrs.identify_time,
            cg.global_ns.namespace("ZB_ZCL_IDENTIFY_IDENTIFY_TIME_DEFAULT_VALUE"),
        ),
    )
    # Store for use by binary sensors
    data[KEY_IDENTIFY_ATTRIB_LIST] = identify_attrib_list_id


def _new_variable(id_: ID) -> cg.MockObj:
    """Create a new global variable with the given ID."""
    obj = MockObj(id_, ".")
    decl = VariableDeclarationExpression(id_.type, "", id_)
    CORE.add_global(decl)
    CORE.register_variable(id_, obj)
    return obj


def _assign(target: cg.MockObj, expression: cg.MockObj | int) -> cg.MockObj:
    """Assign a value to a target and return the target."""
    cg.add(AssignmentExpression("", "", target, expression))
    return target


def _set_string(target: cg.MockObj, value: str) -> core.ID:
    """Set a ZCL string value."""
    cg.add(
        cg.RawExpression(
            f"ZB_ZCL_SET_STRING_VAL({target}, {cg.safe_exp(value)}, ZB_ZCL_STRING_CONST_SIZE({cg.safe_exp(value)}))"
        )
    )
    return ID(str(target), True, zb_char_t_ptr)


def _new_attr_list(id_: ID, *args: ID | cg.MockObj) -> core.ID:
    """Create a new ZCL attribute list macro invocation."""
    attr_list = []
    for arg in args:
        if str(zb_char_t_ptr) == str(arg.type) or str(arg) == "zb_zcl_time_attrs_t_id":
            attr_list.append(f"{arg}")
        else:
            attr_list.append(f"&{arg}")

    obj = cg.RawExpression(f"{id_.type}({id_}, {', '.join(attr_list)})")
    CORE.add_global(obj)
    CORE.register_variable(id_, obj)
    return id_


class ArrayAssignmentExpression(AssignmentExpression):
    __slots__ = ()

    def __init__(self, type_: cg.MockObj, name: ID, rhs: cg.ArrayInitializer):
        super().__init__(type_, "", name, rhs)

    def __str__(self):
        return f"{self.type} {self.name}[] = {self.rhs}"


class ZigbeeClusterDesc(MockObj):
    def __init__(self, name: str, attr: ID | None = None) -> None:
        self._name = name
        self._attr = attr
        base = ID(self._name + "_ZHA_", True, type)
        super().__init__(base, "")

    @property
    def name(self) -> str:
        return self._name

    @property
    def attr(self) -> ID | None:
        return self._attr

    def __str__(self) -> str:
        role = (
            "ZB_ZCL_CLUSTER_SERVER_ROLE" if self._attr else "ZB_ZCL_CLUSTER_CLIENT_ROLE"
        )
        attr_count = "0"
        attr_desc_list = "NULL"
        if self._attr:
            attr_desc_list = str(self._attr)
            attr_count = f"ZB_ZCL_ARRAY_SIZE({attr_desc_list}, zb_zcl_attr_t)"
        return f"ZB_ZCL_CLUSTER_DESC({self._name}, {attr_count}, {attr_desc_list}, {role}, ZB_ZCL_MANUF_CODE_INVALID)"


def _new_array(
    id_: ID, rhs: list[ZigbeeClusterDesc] | cg.ArrayInitializer
) -> cg.MockObj:
    """Create a new array variable."""
    rhs = cg.safe_exp(rhs)
    obj = MockObj(id_, ".")
    assignment = ArrayAssignmentExpression(id_.type, id_, rhs)
    CORE.add_global(assignment)
    CORE.register_variable(id_, obj)
    return obj


def _new_cluster_list(
    cluster_list_id: ID,
    basic_attrib_list_id: ID,
    identify_attrib_list_id: ID,
    sensor_attr_list: ID,
) -> tuple[cg.MockObj, list[ZigbeeClusterDesc]]:
    """Create a cluster list with basic, identify, and sensor-specific clusters."""
    clusters = [
        ZigbeeClusterDesc(ZB_ZCL_CLUSTER_ID_BASIC, basic_attrib_list_id),
        ZigbeeClusterDesc(ZB_ZCL_CLUSTER_ID_IDENTIFY, identify_attrib_list_id),
        ZigbeeClusterDesc(ZB_ZCL_CLUSTER_ID_BINARY_INPUT, sensor_attr_list),
    ]
    obj = _new_array(cluster_list_id, clusters)
    return (obj, clusters)


def _register_endpoint(
    ep_id: ID,
    cluster_id: cg.MockObj,
    report_attr_count: int,
    clusters: list[ZigbeeClusterDesc],
    slot: int,
) -> None:
    """Register a Zigbee endpoint."""
    in_cluster_num = sum(1 for c in clusters if c.attr)
    out_cluster_num = len(clusters) - in_cluster_num
    attrs = [c.name for c in clusters]

    CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER][slot] = str(ep_id)
    obj = cg.RawExpression(
        f"{ep_id.type}({ep_id}, {slot + 1}, {cluster_id}, {in_cluster_num}, {out_cluster_num}, {report_attr_count}, {', '.join(attrs)})"
    )
    CORE.add_global(obj)


async def _generate_device_context() -> None:
    """Generate the device context after all endpoints are registered."""
    ep_list = CORE.data[KEY_ZIGBEE][KEY_EP_NUMBER]
    cg.add_define("ZIGBEE_ENDPOINTS_COUNT", len(ep_list))
    cg.add_global(
        cg.RawExpression(
            f"ZBOSS_DECLARE_DEVICE_CTX_EP_VA(zb_device_ctx, &{', &'.join(ep_list)})"
        )
    )
    cg.add(cg.RawExpression("ZB_AF_REGISTER_DEVICE_CTX(&zb_device_ctx)"))


async def zephyr_setup_binary_sensor(entity: cg.MockObj, config: ConfigType) -> None:
    CORE.add_job(_add_binary_sensor, entity, config)


async def _add_binary_sensor(entity: cg.MockObj, config: ConfigType) -> None:
    data = CORE.data[KEY_ZIGBEE]
    ep_slots = data[KEY_EP_NUMBER]

    # Find the next empty slot
    slot = next((i for i, v in enumerate(ep_slots) if v == ""), None)
    if slot is None:
        return

    # Create binary attributes for this sensor
    binary_attrs_id = ID(
        f"zigbee_binary_attrs_{slot}", is_declaration=True, type=BinaryAttrs
    )
    binary_attrs = _new_variable(binary_attrs_id)

    # Create binary input attribute list
    binary_input_list_id = ID(
        f"zigbee_binary_input_list_{slot}",
        is_declaration=True,
        type=cg.global_ns.namespace("ESPHOME_ZB_ZCL_DECLARE_BINARY_INPUT_ATTRIB_LIST"),
    )
    attr_list = _new_attr_list(
        binary_input_list_id,
        _assign(binary_attrs.out_of_service, 0),
        _assign(binary_attrs.present_value, 0),
        _assign(binary_attrs.status_flags, 0),
        _set_string(binary_attrs.description, config[CONF_NAME]),
    )

    # Create cluster list for this endpoint
    cluster_list_id = ID(
        f"zigbee_cluster_list_{slot}",
        is_declaration=True,
        type=cg.global_ns.namespace("zb_zcl_cluster_desc_t"),
    )
    cluster_id, clusters = _new_cluster_list(
        cluster_list_id,
        data[KEY_BASIC_ATTRIB_LIST],
        data[KEY_IDENTIFY_ATTRIB_LIST],
        attr_list,
    )

    # Create endpoint
    ep_id = ID(f"zigbee_ep_{slot}", is_declaration=True, type=ESPHOME_ZB_HA_DECLARE_EP)
    _register_endpoint(ep_id, cluster_id, 2, clusters, slot)

    # Create the ZigbeeBinarySensor component
    sensor_id = ID(
        f"zigbee_binary_sensor_{slot}", is_declaration=True, type=ZigbeeBinarySensor
    )
    var = cg.new_Pvariable(sensor_id, entity)
    cg.add(
        var.set_component_source(cg.RawExpression('LOG_STR("zigbee.zigbee_zephyr")'))
    )
    CORE.component_ids.add(sensor_id)
    cg.App.register_component(var)

    cg.add(var.set_end_point(slot + 1))
    cg.add(var.set_cluster_attributes(binary_attrs))
    hub = await cg.get_variable(config[CONF_ZIGBEE_ID])
    cg.add(var.set_parent(hub))

    # Generate device context after all endpoints are registered
    if all(ep != "" for ep in ep_slots):
        await _generate_device_context()
