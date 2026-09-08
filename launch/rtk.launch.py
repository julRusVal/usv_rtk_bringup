#!/usr/bin/env python3
"""Launch Septentrio GNSS receiver with RTK corrections for USV."""
import os
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from robot_namespace import (  # noqa: E402
    declare_namespace_override_argument,
    declare_robot_name_argument,
    launch_arg,
)
from septentrio_launch import make_septentrio_driver_actions  # noqa: E402
from vehicle_config import default_vehicle_config_path  # noqa: E402


def launch_setup(context, *args, **kwargs):
    pkg_dir = get_package_share_directory('usv_rtk_bringup')

    rtk_params_file = launch_arg(context, 'rtk_params_file')
    if not rtk_params_file:
        rtk_params_file = os.path.join(pkg_dir, 'config', 'rtk.yaml')

    return make_septentrio_driver_actions(
        context,
        params_files=[rtk_params_file],
        aux_nmea_prefix='rtk_aux_nmea_',
    )


def generate_launch_description():
    pkg_dir = get_package_share_directory('usv_rtk_bringup')
    default_rtk_params = os.path.join(pkg_dir, 'config', 'rtk.yaml')

    return LaunchDescription([
        declare_robot_name_argument(),
        declare_namespace_override_argument('septentrio'),
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
