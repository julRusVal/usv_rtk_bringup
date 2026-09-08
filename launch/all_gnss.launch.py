#!/usr/bin/env python3
"""Unified GNSS launcher — pick RTK module via config/gnss_stack.yaml.

Quick reference
---------------
  ros2 launch usv_rtk_bringup all_gnss.launch.py
      → module from gnss_stack.yaml (default: Septentrio RTK)

  ros2 launch usv_rtk_bringup all_gnss.launch.py module:=sbg
      → SBG Ellipse-D

  ros2 launch usv_rtk_bringup all_gnss.launch.py module:=ublox
      → u-blox only

  ros2 launch usv_rtk_bringup all_gnss.launch.py enable_ntrip:=true
      → driver + ntrip_aux_client in one launch

NTRIP credentials: config/secrets.yaml. See launch/README.md.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource

from gnss_stack import (
    build_ntrip_argv,
    default_gnss_stack_path,
    ntrip_client_executable,
    resolve_gnss_stack,
)
from robot_namespace import declare_robot_name_argument, launch_arg

SEPTENTRIO_PROFILES = {
    'gnss': 'gnss.launch.py',
    'rtk': 'rtk.launch.py',
    'rtk_heading': 'rtk_heading.launch.py',
}


def _include_launch(pkg_share, launch_file, launch_args, condition):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_share, 'launch', launch_file)
        ),
        launch_arguments=launch_args,
        condition=condition,
    )


def launch_setup(context, *args, **kwargs):
    pkg_share = get_package_share_directory('usv_rtk_bringup')
    robot_name = launch_arg(context, 'robot_name')
    module_arg = launch_arg(context, 'module')
    profile_arg = launch_arg(context, 'profile')
    enable_ntrip_arg = launch_arg(context, 'enable_ntrip')
    gnss_stack_path = launch_arg(context, 'gnss_stack')
    log_level = launch_arg(context, 'log_level')
    vehicle_config_arg = launch_arg(context, 'vehicle_config')

    if not gnss_stack_path:
        gnss_stack_path = default_gnss_stack_path()

    stack = resolve_gnss_stack(
        gnss_stack_path,
        module_override=module_arg,
        profile_override=profile_arg,
        enable_ntrip_override=enable_ntrip_arg,
        vehicle_config_override=vehicle_config_arg,
        robot_name=robot_name,
        pkg_share=pkg_share,
    )

    module = stack['module']
    profile = stack['profile']
    common_args = {
        'robot_name': robot_name,
        'log_level': log_level,
        'gnss_stack': gnss_stack_path,
    }
    sbg_args = {
        **common_args,
        'vehicle_config': vehicle_config_arg or stack['sbg_vehicle_config'],
        'enable_ntrip': enable_ntrip_arg,
    }

    actions = []

    if module == 'septentrio':
        launch_file = SEPTENTRIO_PROFILES.get(profile, 'rtk.launch.py')
        actions.append(
            _include_launch(
                pkg_share,
                launch_file,
                common_args,
                None,
            )
        )
    elif module == 'sbg':
        actions.append(
            _include_launch(
                pkg_share,
                'sbg.launch.py',
                sbg_args,
                None,
            )
        )
    elif module == 'ublox':
        actions.append(
            _include_launch(
                pkg_share,
                'ublox.launch.py',
                common_args,
                None,
            )
        )

    enable_ublox = launch_arg(context, 'enable_ublox')
    if enable_ublox.lower() in ('true', '1', 'yes') and module == 'septentrio':
        actions.append(
            _include_launch(
                pkg_share,
                'ublox.launch.py',
                common_args,
                None,
            )
        )

    if stack['enable_ntrip'] and module != 'sbg':
        ntrip_exe = ntrip_client_executable(stack)
        ntrip_argv = build_ntrip_argv(stack)
        actions.append(
            ExecuteProcess(
                cmd=['ros2', 'run', 'usv_rtk_bringup', ntrip_exe, *ntrip_argv],
                output='screen',
                shell=False,
            )
        )

    return actions


def generate_launch_description():
    pkg_share = get_package_share_directory('usv_rtk_bringup')

    return LaunchDescription([
        declare_robot_name_argument(),
        DeclareLaunchArgument(
            'gnss_stack',
            default_value=default_gnss_stack_path(),
            description='Path to gnss_stack.yaml (primary.module selector)',
        ),
        DeclareLaunchArgument(
            'module',
            default_value='',
            description='Override primary.module: septentrio, sbg, ublox',
            choices=['', 'septentrio', 'sbg', 'ublox'],
        ),
        DeclareLaunchArgument(
            'profile',
            default_value='',
            description='Override Septentrio profile: gnss, rtk, rtk_heading',
            choices=['', 'gnss', 'rtk', 'rtk_heading'],
        ),
        DeclareLaunchArgument(
            'enable_ntrip',
            default_value='',
            description='Launch NTRIP client (ntrip_ros_client or ntrip_aux_client; from gnss_stack)',
            choices=['', 'true', 'false'],
        ),
        DeclareLaunchArgument(
            'enable_ublox',
            default_value='false',
            description='With module:=septentrio, also launch u-blox under {robot_name}/ublox',
        ),
        DeclareLaunchArgument(
            'vehicle_config',
            default_value='',
            description='Override gnss_stack vehicle_config (SBG per-hull YAML only)',
        ),
        DeclareLaunchArgument(
            'log_level',
            default_value='INFO',
            description='ROS log level for GNSS drivers',
        ),
        OpaqueFunction(function=launch_setup),
    ])
