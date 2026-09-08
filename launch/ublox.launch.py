#!/usr/bin/env python3
"""Launch u-blox GNSS (ublox_dgnss); RTCM from a shared ROS topic (no local NTRIP client)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

from robot_namespace import (
    SENSOR_UBLOX,
    declare_namespace_override_argument,
    declare_robot_name_argument,
    default_rtcm_topic,
    launch_arg,
    resolve_sensor_namespace,
)


def _load_ublox_defaults(pkg_share):
    defaults = {
        'frame_id': 'ublox_gps',
        'device_family': 'F9P',
        'device_serial_string': '',
        'rtcm_topic': '',
    }
    cfg_path = os.path.join(pkg_share, 'config', 'ublox.yaml')
    if os.path.isfile(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as handle:
            section = yaml.safe_load(handle) or {}
        ublox = section.get('ublox', {})
        for key in defaults:
            if key in ublox and ublox[key] is not None:
                defaults[key] = ublox[key]
    return defaults


def launch_setup(context, *args, **kwargs):
    log_level = launch_arg(context, 'log_level')
    robot_name = launch_arg(context, 'robot_name')
    namespace = resolve_sensor_namespace(context, SENSOR_UBLOX)
    device_family = launch_arg(context, 'device_family')
    device_serial_string = launch_arg(context, 'device_serial_string')
    frame_id = launch_arg(context, 'frame_id')
    rtcm_topic = default_rtcm_topic(
        robot_name,
        launch_arg(context, 'rtcm_topic'),
    )

    driver_params = [
        {'DEVICE_FAMILY': device_family},
        {'DEVICE_SERIAL_STRING': device_serial_string},
        {'FRAME_ID': frame_id},
        {'CFG_USBOUTPROT_NMEA': False},
        {'CFG_RATE_MEAS': 10},
        {'CFG_RATE_NAV': 100},
        {'CFG_MSGOUT_UBX_NAV_HPPOSLLH_USB': 1},
        {'CFG_MSGOUT_UBX_NAV_STATUS_USB': 5},
        {'CFG_MSGOUT_UBX_NAV_COV_USB': 1},
        {'CFG_MSGOUT_UBX_RXM_RTCM_USB': 1},
        {'RTCM_INPUT_ENABLED': True},
    ]

    # Driver subscribes to /ntrip_client/rtcm in code; remap to shared RTCM topic.
    rtcm_remap = [('/ntrip_client/rtcm', rtcm_topic)]

    driver_container = ComposableNodeContainer(
        name='ublox_dgnss_container',
        namespace='',
        package='rclcpp_components',
        executable='component_container_mt',
        arguments=['--ros-args', '--log-level', log_level],
        composable_node_descriptions=[
            ComposableNode(
                package='ublox_dgnss_node',
                plugin='ublox_dgnss::UbloxDGNSSNode',
                name='ublox_dgnss',
                namespace=namespace,
                parameters=driver_params,
                remappings=rtcm_remap,
            )
        ],
    )

    navsat_container = ComposableNodeContainer(
        name='ublox_nav_sat_fix_hp_container',
        namespace='',
        package='rclcpp_components',
        executable='component_container_mt',
        arguments=['--ros-args', '--log-level', log_level],
        composable_node_descriptions=[
            ComposableNode(
                package='ublox_nav_sat_fix_hp_node',
                plugin='ublox_nav_sat_fix_hp::UbloxNavSatHpFixNode',
                name='ublox_nav_sat_fix_hp',
                namespace=namespace,
            )
        ],
    )

    return [driver_container, navsat_container]


def generate_launch_description():
    pkg_share = get_package_share_directory('usv_rtk_bringup')
    defaults = _load_ublox_defaults(pkg_share)

    return LaunchDescription([
        declare_robot_name_argument(),
        declare_namespace_override_argument(SENSOR_UBLOX),
        DeclareLaunchArgument(
            'rtcm_topic',
            default_value=defaults['rtcm_topic'],
            description='RTCM topic (default: /{robot_name}/rtcm or /rtcm)',
        ),
        DeclareLaunchArgument(
            'device_family',
            default_value=defaults['device_family'],
            description='F9P, F9R, or X20P',
        ),
        DeclareLaunchArgument(
            'device_serial_string',
            default_value=defaults['device_serial_string'],
            description='Optional u-blox USB serial when multiple devices',
        ),
        DeclareLaunchArgument(
            'frame_id',
            default_value=defaults['frame_id'],
            description='frame_id in published messages',
        ),
        DeclareLaunchArgument(
            'log_level',
            default_value='INFO',
            description='ROS log level',
        ),
        OpaqueFunction(function=launch_setup),
    ])
