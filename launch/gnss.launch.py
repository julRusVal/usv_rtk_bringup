#!/usr/bin/env python3
"""Launch Septentrio GNSS without RTK — NMEA on aux serial for str2str."""
import os
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from septentrio_launch import launch_arg, make_septentrio_driver_actions  # noqa: E402
from vehicle_config import default_vehicle_config_path  # noqa: E402


def launch_setup(context, *args, **kwargs):
    pkg_dir = get_package_share_directory('usv_rtk_bringup')

    gnss_params_file = launch_arg(context, 'gnss_params_file')
    if not gnss_params_file:
        gnss_params_file = os.path.join(pkg_dir, 'config', 'gnss.yaml')

    default_aux_nmea_cmd = os.path.join(pkg_dir, 'config', 'gnss_aux_nmea.cmd')

    return make_septentrio_driver_actions(
        context,
        params_files=[gnss_params_file],
        aux_nmea_cmd_file_arg='aux_nmea_cmd_file',
        default_aux_nmea_cmd=default_aux_nmea_cmd,
        aux_nmea_prefix='gnss_aux_nmea_',
    )


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
