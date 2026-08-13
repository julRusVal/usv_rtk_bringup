#!/usr/bin/env python3
"""USV RTK bringup entry point."""
import os

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_dir = get_package_share_directory('usv_rtk_bringup')
    rtk_launch = os.path.join(pkg_dir, 'launch', 'rtk.launch.py')

    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(rtk_launch),
        ),
    ])
