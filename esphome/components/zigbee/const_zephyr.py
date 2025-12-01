import esphome.codegen as cg

zigbee_ns = cg.esphome_ns.namespace("zigbee")
ZigbeeComponent = zigbee_ns.class_("ZigbeeComponent", cg.Component)

zb_char_t_ptr = cg.global_ns.namespace("zb_char_t *")

CONF_MAX_EP_NUMBER = 8
CONF_EP = "ep"
CONF_ZIGBEE_ID = "zigbee_id"
CONF_ON_JOIN = "on_join"
CONF_WIPE_ON_BOOT = "wipe_on_boot"
KEY_ZIGBEE = "zigbee"
KEY_EP_NUMBER = "ep_number"
KEY_BASIC_ATTRIB_LIST = "basic_attrib_list"
KEY_IDENTIFY_ATTRIB_LIST = "identify_attrib_list"

zb_zcl_basic_attrs_ext_t = cg.global_ns.namespace("zb_zcl_basic_attrs_ext_t")
zb_zcl_identify_attrs_t = cg.global_ns.namespace("zb_zcl_identify_attrs_t")
zb_zcl_groups_attrs_t = cg.global_ns.namespace("zb_zcl_groups_attrs_t")
zb_zcl_scenes_attrs_t = cg.global_ns.namespace("zb_zcl_scenes_attrs_t")

# C++ macro types - used as type identifiers for ID generation
ZB_ZCL_DECLARE_BASIC_ATTRIB_LIST_EXT = cg.global_ns.namespace(
    "ZB_ZCL_DECLARE_BASIC_ATTRIB_LIST_EXT"
)
ZB_ZCL_DECLARE_IDENTIFY_ATTRIB_LIST = cg.global_ns.namespace(
    "ZB_ZCL_DECLARE_IDENTIFY_ATTRIB_LIST"
)
BinaryAttrs = zigbee_ns.struct("BinaryAttrs")
ESPHOME_ZB_HA_DECLARE_EP = cg.global_ns.namespace("ESPHOME_ZB_HA_DECLARE_EP")


# clusters
ZB_ZCL_CLUSTER_ID_BASIC = "ZB_ZCL_CLUSTER_ID_BASIC"
ZB_ZCL_CLUSTER_ID_IDENTIFY = "ZB_ZCL_CLUSTER_ID_IDENTIFY"
ZB_ZCL_CLUSTER_ID_GROUPS = "ZB_ZCL_CLUSTER_ID_GROUPS"
ZB_ZCL_CLUSTER_ID_SCENES = "ZB_ZCL_CLUSTER_ID_SCENES"

ZB_ZCL_CLUSTER_ID_BINARY_INPUT = "ZB_ZCL_CLUSTER_ID_BINARY_INPUT"
ZB_ZCL_CLUSTER_ID_BINARY_OUTPUT = "ZB_ZCL_CLUSTER_ID_BINARY_OUTPUT"
ZB_ZCL_CLUSTER_ID_TIME = "ZB_ZCL_CLUSTER_ID_TIME"
ZB_ZCL_CLUSTER_ID_ANALOG_INPUT = "ZB_ZCL_CLUSTER_ID_ANALOG_INPUT"
ZB_ZCL_CLUSTER_ID_ANALOG_OUTPUT = "ZB_ZCL_CLUSTER_ID_ANALOG_OUTPUT"
