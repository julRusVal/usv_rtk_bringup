#!/usr/bin/env python3
"""Launch Septentrio GNSS without RTK — NMEA on aux serial for str2str."""
import os
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vehicle_config import (  # noqa: E402
    aux_nmea_commands,
    default_vehicle_config_path,
    load_resolved_config,
    static_transform_nodes,
    write_temp_commands,
)


def _launch_arg(context, name):
    return LaunchConfiguration(name).perform(context)


def _filtered_custom_commands_file(source_path):
    """Strip blank/comment lines; driver sends every line verbatim to the Rx."""
    commands = []
    with open(source_path, encoding='utf-8') as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            commands.append(stripped)

    if not commands:
        return source_path

    return write_temp_commands(commands, prefix='gnss_aux_nmea_')


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

    gnss_params_file = _launch_arg(context, 'gnss_params_file')
    if not gnss_params_file:
        gnss_params_file = os.path.join(pkg_dir, 'config', 'gnss.yaml')

    aux_nmea_cmd = _launch_arg(context, 'aux_nmea_cmd_file')
    default_aux_nmea_cmd = os.path.join(pkg_dir, 'config', 'gnss_aux_nmea.cmd')
    enable_aux_nmea = _launch_arg(context, 'enable_aux_nmea')

    if enable_aux_nmea == 'false':
        aux_nmea_cmd = None
    elif aux_nmea_cmd and aux_nmea_cmd != default_aux_nmea_cmd:
        aux_nmea_cmd = _filtered_custom_commands_file(aux_nmea_cmd)
    else:
        aux_port = resolved['network'].get('aux_receiver_port', 'USB2')
        aux_nmea_cmd = write_temp_commands(
            aux_nmea_commands(aux_port), prefix='gnss_aux_nmea_'
        )

    param_overlay = {'device': resolved['device']}
    if aux_nmea_cmd:
        param_overlay['custom_commands_file'] = aux_nmea_cmd

    params = [
        gnss_params_file,
        param_overlay,
    ]

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
    default_gnss_params = os.path.join(pkg_dir, 'config', 'gnss.yaml')
    default_aux_nmea_cmd = os.path.join(pkg_dir, 'config', 'gnss_aux_nmea.cmd')

    return LaunchDescription([
        DeclareLaunchArgument(
            'vehicle_config',
            default_value=default_vehicle_config_path(),
            description='Path to USV vehicle YAML',
        ),
        DeclareLaunchArgument(
            'gnss_params_file',
            default_value=default_gnss_params,
            description='Path to GNSS-only Septentrio driver parameter YAML',
        ),
        DeclareLaunchArgument(
            'aux_nmea_cmd_file',
            default_value=default_aux_nmea_cmd,
            description='Override aux-port Septentrio commands (default: generated for aux_receiver_port)',
        ),
        DeclareLaunchArgument(
            'enable_aux_nmea',
            default_value='true',
            description='Set false to skip NMEA output on the aux serial port',
        ),
        DeclareLaunchArgument(
            'receiver_ip',
            default_value='',
            description='Override receiver IP from vehicle config (TCP only)',
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
