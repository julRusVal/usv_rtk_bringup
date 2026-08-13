#!/usr/bin/env python3
"""Launch Septentrio GNSS receiver with RTK corrections for USV."""
import os
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vehicle_config import (  # noqa: E402
    default_vehicle_config_path,
    load_resolved_config,
    static_transform_nodes,
)


def _launch_arg(context, name):
    return LaunchConfiguration(name).perform(context)


def launch_setup(context, *args, **kwargs):
    pkg_dir = get_package_share_directory('usv_rtk_bringup')

    vehicle_config_path = _launch_arg(context, 'vehicle_config')
    if not vehicle_config_path:
        vehicle_config_path = default_vehicle_config_path()

    overrides = {
        'receiver_ip': _launch_arg(context, 'receiver_ip'),
        'receiver_port': _launch_arg(context, 'receiver_port'),
    }
    resolved = load_resolved_config(vehicle_config_path, overrides)

    rtk_params_file = _launch_arg(context, 'rtk_params_file')
    if not rtk_params_file:
        rtk_params_file = os.path.join(pkg_dir, 'config', 'rtk.yaml')

    secrets_file = _launch_arg(context, 'secrets_file')
    if not secrets_file:
        secrets_file = os.path.join(pkg_dir, 'config', 'secrets.yaml')

    params = [rtk_params_file, {'device': resolved['device']}]
    if os.path.isfile(secrets_file):
        params.append(secrets_file)

    driver_node = Node(
        package='septentrio_gnss_driver',
        executable='septentrio_gnss_driver_node',
        name='septentrio_gnss_driver',
        emulate_tty=True,
        sigterm_timeout='20',
        parameters=params,
        arguments=['--ros-args', '--log-level', _launch_arg(context, 'log_level')],
        output='screen',
    )

    return [driver_node, *static_transform_nodes(resolved['extrinsics'])]


def generate_launch_description():
    pkg_dir = get_package_share_directory('usv_rtk_bringup')
    default_rtk_params = os.path.join(pkg_dir, 'config', 'rtk.yaml')
    default_secrets = os.path.join(pkg_dir, 'config', 'secrets.yaml')

    return LaunchDescription([
        DeclareLaunchArgument(
            'vehicle_config',
            default_value=default_vehicle_config_path(),
            description='Path to USV vehicle YAML',
        ),
        DeclareLaunchArgument(
            'rtk_params_file',
            default_value=default_rtk_params,
            description='Path to Septentrio driver parameter YAML',
        ),
        DeclareLaunchArgument(
            'secrets_file',
            default_value=default_secrets,
            description='Optional NTRIP credentials YAML (gitignored)',
        ),
        DeclareLaunchArgument(
            'receiver_ip',
            default_value='',
            description='Override receiver IP from vehicle config',
        ),
        DeclareLaunchArgument(
            'receiver_port',
            default_value='',
            description='Override receiver TCP port from vehicle config',
        ),
        DeclareLaunchArgument(
            'log_level',
            default_value='INFO',
            description='ROS log level for the GNSS driver',
        ),
        OpaqueFunction(function=launch_setup),
    ])
