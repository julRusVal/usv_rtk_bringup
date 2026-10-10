#!/usr/bin/env python3
"""Launch SBG Ellipse INS (sbg_driver) with vehicle overlay and optional NTRIP.

Standalone entry point — same overlay as all_gnss module:=sbg, without the switchboard:

  ros2 launch usv_rtk_bringup sbg.launch.py
  ros2 launch usv_rtk_bringup sbg.launch.py enable_ntrip:=true

Before sbg_driver starts (and takes the serial port), the device's stored settings are read with
sbg_settings and saved to ~/.ros/sbg_device_settings/<robot>-<time>.json; sbg_settings_publisher then
publishes them latched on /<robot>/sbg/device_settings so bags carry them (record_device_settings:=false
to skip).

Direct sbg_driver (no launch file) — bake params first:

  ros2 run usv_rtk_bringup merge_sbg_params --robot-name floatsam_usv_0 -o /tmp/sbg.yaml
  ros2 run sbg_driver sbg_device --ros-args -r __ns:=/floatsam_usv_0/sbg --params-file /tmp/sbg.yaml
"""
import datetime
import os
import subprocess
import sys
import tempfile

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, LogInfo, OpaqueFunction
from launch_ros.actions import Node

from gnss_stack import (
    build_ntrip_argv,
    default_gnss_stack_path,
    ntrip_client_executable,
    resolve_gnss_stack,
)
from robot_namespace import (
    SENSOR_SBG,
    declare_namespace_override_argument,
    declare_robot_name_argument,
    default_nmea_topic,
    default_rtcm_topic,
    launch_arg,
    resolve_sensor_namespace,
)
from vehicle_config import (
    build_sbg_launch_overlay,
    load_resolved_config,
    load_vehicle_config,
    static_transform_nodes,
)


def launch_setup(context, *args, **kwargs):
    pkg_share = get_package_share_directory('usv_rtk_bringup')
    robot_name = launch_arg(context, 'robot_name')
    log_level = launch_arg(context, 'log_level')
    namespace = resolve_sensor_namespace(context, SENSOR_SBG)
    enable_ntrip_arg = launch_arg(context, 'enable_ntrip')

    gnss_stack_path = launch_arg(context, 'gnss_stack')
    if not gnss_stack_path:
        gnss_stack_path = default_gnss_stack_path()

    stack = resolve_gnss_stack(
        gnss_stack_path,
        module_override='sbg',
        enable_ntrip_override=enable_ntrip_arg,
        vehicle_config_override=launch_arg(context, 'vehicle_config'),
        robot_name=robot_name,
        pkg_share=pkg_share,
    )

    params_file = launch_arg(context, 'sbg_params_file')
    if not params_file:
        params_file = stack['sbg_params_file']

    vehicle_config_path = stack['sbg_vehicle_config']
    vehicle_raw = load_vehicle_config(vehicle_config_path)
    resolved = load_resolved_config(vehicle_config_path, {}, robot_name)

    param_overlay = build_sbg_launch_overlay(
        vehicle_raw,
        robot_name,
        rtcm_topic=launch_arg(context, 'rtcm_topic'),
        nmea_topic=launch_arg(context, 'nmea_topic'),
    )
    # sbg_device reads its params through an internal helper node ("npv") and also creates a
    # "tf_broadcaster" node, so the overlay must reach every node in the process: write it under
    # /** (a dict in `parameters` would be scoped to the main node's name only). This lets us skip
    # name= on the Node — that remaps *all* nodes in the process to the same name (duplicate
    # /<ns>/sbg/sbg_device in `ros2 node list`).
    with tempfile.NamedTemporaryFile('w', prefix='sbg_overlay_', suffix='.yaml', delete=False) as f:
        yaml.safe_dump({'/**': {'ros__parameters': param_overlay}}, f)
        overlay_file = f.name

    settings_actions = []
    if launch_arg(context, 'record_device_settings').lower() == 'true':
        settings_actions = record_device_settings(robot_name, namespace)

    nmea_topic = default_nmea_topic(robot_name, launch_arg(context, 'nmea_topic'))
    rtcm_topic = default_rtcm_topic(robot_name, launch_arg(context, 'rtcm_topic'))

    actions = [
        LogInfo(msg=(
            f'sbg.launch: params={params_file} vehicle={vehicle_config_path} '
            f'ns=/{namespace} nmea={nmea_topic} rtcm={rtcm_topic}'
        )),
        Node(
            package='sbg_driver',
            executable='sbg_device',
            namespace=namespace,
            output='screen',
            parameters=[params_file, overlay_file],
            arguments=['--ros-args', '--log-level', log_level],
        ),
        *static_transform_nodes(resolved['extrinsics']),
        *settings_actions,
    ]

    if stack['enable_ntrip']:
        ntrip_exe = ntrip_client_executable(stack)
        actions.append(
            ExecuteProcess(
                cmd=['ros2', 'run', 'usv_rtk_bringup', ntrip_exe, *build_ntrip_argv(stack)],
                output='screen',
                shell=False,
            )
        )

    return actions


def record_device_settings(robot_name, namespace):
    """Read the SBG's stored settings now (port still free) and publish the snapshot for bags."""
    snapshot_dir = os.path.expanduser('~/.ros/sbg_device_settings')
    os.makedirs(snapshot_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    path = os.path.join(snapshot_dir, f'{robot_name or "sbg"}-{stamp}.json')
    tool = os.path.join(get_package_prefix('usv_rtk_bringup'), 'lib', 'usv_rtk_bringup', 'sbg_settings')
    try:
        result = subprocess.run([tool, '--json', '--output', path, '--robot-name', robot_name],
                                capture_output=True, text=True, timeout=60)
        summary = (result.stdout.strip() or result.stderr.strip()).splitlines()[-1:] or ['(no output)']
        summary = summary[0]
    except subprocess.TimeoutExpired:
        summary = 'sbg_settings timed out after 60 s'
    return [
        LogInfo(msg=f'sbg.launch: device settings: {summary}'),
        Node(
            package='usv_rtk_bringup',
            executable='sbg_settings_publisher',
            namespace=namespace,
            output='screen',
            parameters=[{'settings_file': path}],
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        declare_robot_name_argument(),
        declare_namespace_override_argument(SENSOR_SBG),
        DeclareLaunchArgument(
            'record_device_settings',
            default_value='true',
            description='Read the SBG settings before the driver starts and publish them on sbg/device_settings',
        ),
        DeclareLaunchArgument(
            'gnss_stack',
            default_value=default_gnss_stack_path(),
            description='gnss_stack.yaml — selects vehicle_config + sbg params_file',
        ),
        DeclareLaunchArgument(
            'vehicle_config',
            default_value='',
            description='Override gnss_stack vehicle_config (per-hull extrinsics + sbg serial)',
        ),
        DeclareLaunchArgument(
            'sbg_params_file',
            default_value='',
            description='SBG sensor YAML (default: gnss_stack primary.sbg.params_file)',
        ),
        DeclareLaunchArgument(
            'rtcm_topic',
            default_value='',
            description='Shared RTCM topic (default: /{robot_name}/rtcm)',
        ),
        DeclareLaunchArgument(
            'nmea_topic',
            default_value='',
            description='Shared NMEA topic (default: /{robot_name}/nmea)',
        ),
        DeclareLaunchArgument(
            'enable_ntrip',
            default_value='',
            description='Launch ntrip_ros_client (default: gnss_stack ntrip.auto_launch)',
            choices=['', 'true', 'false'],
        ),
        DeclareLaunchArgument(
            'log_level',
            default_value='INFO',
            description='ROS log level',
        ),
        OpaqueFunction(function=launch_setup),
    ])
