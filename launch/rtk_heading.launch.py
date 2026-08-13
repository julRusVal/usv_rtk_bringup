#!/usr/bin/env python3
"""Launch Septentrio RTK with dual-antenna heading."""
import os
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch_ros.actions import Node

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from septentrio_launch import launch_arg, make_septentrio_driver_actions  # noqa: E402
from vehicle_config import default_vehicle_config_path  # noqa: E402


def launch_setup(context, *args, **kwargs):
    pkg_dir = get_package_share_directory('usv_rtk_bringup')

    rtk_params_file = launch_arg(context, 'rtk_params_file')
    if not rtk_params_file:
        rtk_params_file = os.path.join(pkg_dir, 'config', 'rtk.yaml')

    rtk_heading_params_file = launch_arg(context, 'rtk_heading_params_file')
    if not rtk_heading_params_file:
        rtk_heading_params_file = os.path.join(pkg_dir, 'config', 'rtk_heading.yaml')

    vehicle_config = launch_arg(context, 'vehicle_config')
    if not vehicle_config:
        vehicle_config = default_vehicle_config_path()

    actions = make_septentrio_driver_actions(
        context,
        params_files=[rtk_params_file, rtk_heading_params_file],
        aux_nmea_prefix='rtk_heading_aux_nmea_',
    )
    actions.append(
        Node(
            package='usv_rtk_bringup',
            executable='dual_antenna_attitude_remap',
            name='dual_antenna_attitude_remap',
            output='screen',
            parameters=[{'vehicle_config': vehicle_config}],
        )
    )
    return actions


def generate_launch_description():
    pkg_dir = get_package_share_directory('usv_rtk_bringup')
    default_rtk_params = os.path.join(pkg_dir, 'config', 'rtk.yaml')
    default_rtk_heading_params = os.path.join(pkg_dir, 'config', 'rtk_heading.yaml')

    return LaunchDescription([
        DeclareLaunchArgument(
            'vehicle_config',
            default_value=default_vehicle_config_path(),
            description='Path to USV vehicle YAML',
        ),
        DeclareLaunchArgument(
            'rtk_params_file',
            default_value=default_rtk_params,
            description='Base Septentrio driver parameters (RTK)',
        ),
        DeclareLaunchArgument(
            'rtk_heading_params_file',
            default_value=default_rtk_heading_params,
            description='Dual-antenna heading parameter overlay',
        ),
        DeclareLaunchArgument(
            'enable_aux_nmea',
            default_value='true',
            description='Configure GGA/RMC on aux port for ntrip_aux_client',
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
