"""Shared Septentrio GNSS driver launch setup."""

import os

from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from vehicle_config import (
    aux_nmea_commands,
    default_vehicle_config_path,
    load_resolved_config,
    static_transform_nodes,
    write_temp_commands,
)


def launch_arg(context, name):
    return LaunchConfiguration(name).perform(context)


def filtered_custom_commands_file(source_path, prefix='aux_nmea_'):
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

    return write_temp_commands(commands, prefix=prefix)


def resolve_aux_nmea_commands_file(
    context,
    resolved,
    *,
    enable_aux_nmea_arg='enable_aux_nmea',
    aux_nmea_cmd_file_arg=None,
    default_aux_nmea_cmd=None,
    prefix='aux_nmea_',
):
    if launch_arg(context, enable_aux_nmea_arg) == 'false':
        return None

    if aux_nmea_cmd_file_arg is not None:
        aux_nmea_cmd = launch_arg(context, aux_nmea_cmd_file_arg)
        if (
            default_aux_nmea_cmd
            and aux_nmea_cmd
            and aux_nmea_cmd != default_aux_nmea_cmd
        ):
            return filtered_custom_commands_file(aux_nmea_cmd, prefix=prefix)

    aux_port = resolved['network'].get('aux_receiver_port', 'USB2')
    return write_temp_commands(aux_nmea_commands(aux_port), prefix=prefix)


def make_septentrio_driver_actions(
    context,
    *,
    params_files,
    enable_aux_nmea_arg='enable_aux_nmea',
    aux_nmea_cmd_file_arg=None,
    default_aux_nmea_cmd=None,
    aux_nmea_prefix='aux_nmea_',
    log_level_arg='log_level',
    vehicle_config_arg='vehicle_config',
    receiver_ip_arg='receiver_ip',
    receiver_port_arg='receiver_port',
):
    vehicle_config_path = launch_arg(context, vehicle_config_arg)
    if not vehicle_config_path:
        vehicle_config_path = default_vehicle_config_path()

    overrides = {
        'receiver_ip': launch_arg(context, receiver_ip_arg),
        'receiver_port': launch_arg(context, receiver_port_arg),
    }
    resolved = load_resolved_config(vehicle_config_path, overrides)

    param_overlay = {'device': resolved['device']}
    aux_cmd = resolve_aux_nmea_commands_file(
        context,
        resolved,
        enable_aux_nmea_arg=enable_aux_nmea_arg,
        aux_nmea_cmd_file_arg=aux_nmea_cmd_file_arg,
        default_aux_nmea_cmd=default_aux_nmea_cmd,
        prefix=aux_nmea_prefix,
    )
    if aux_cmd:
        param_overlay['custom_commands_file'] = aux_cmd

    driver_node = Node(
        package='septentrio_gnss_driver',
        executable='septentrio_gnss_driver_node',
        name='septentrio_gnss_driver',
        emulate_tty=True,
        sigterm_timeout='20',
        parameters=[*params_files, param_overlay],
        arguments=['--ros-args', '--log-level', launch_arg(context, log_level_arg)],
        output='screen',
    )

    return [driver_node, *static_transform_nodes(resolved['extrinsics'])]
