#!/usr/bin/env python3
"""USV RTK bringup — alias for all_gnss with profile:=rtk."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    pkg_dir = get_package_share_directory('usv_rtk_bringup')
    all_gnss_launch = os.path.join(pkg_dir, 'launch', 'all_gnss.launch.py')

    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(all_gnss_launch),
            launch_arguments={'profile': 'rtk'}.items(),
        ),
    ])
