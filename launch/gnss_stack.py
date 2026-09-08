"""Load gnss_stack.yaml and resolve module / NTRIP settings."""

import os

import yaml
from ament_index_python.packages import get_package_share_directory

from robot_namespace import default_rtcm_topic, default_nmea_topic, normalize_name_part, sensor_namespace
from vehicle_config import (
    default_vehicle_config_path,
    resolve_config_path,
)

VALID_MODULES = ('septentrio', 'sbg', 'ublox')
VALID_PROFILES = ('gnss', 'rtk', 'rtk_heading')
VALID_GGA_SOURCES = ('auto', 'aux_serial', 'ros_topic')


def default_gnss_stack_path():
    pkg_share = get_package_share_directory('usv_rtk_bringup')
    return os.path.join(pkg_share, 'config', 'gnss_stack.yaml')


def _resolve_config_path(path, pkg_share):
    return resolve_config_path(path, pkg_share)


def load_gnss_stack(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle) or {}


def resolve_sbg(config):
    from vehicle_config import resolve_sbg as _resolve_sbg

    return _resolve_sbg(config)


def resolve_gnss_stack(
    gnss_stack_path,
    *,
    module_override='',
    profile_override='',
    enable_ntrip_override='',
    vehicle_config_override='',
    robot_name='',
    pkg_share=None,
):
    """Return resolved stack dict for launch and NTRIP argv building."""
    if pkg_share is None:
        pkg_share = get_package_share_directory('usv_rtk_bringup')

    stack = load_gnss_stack(gnss_stack_path)
    primary = dict(stack.get('primary', {}))
    ntrip = dict(stack.get('ntrip', {}))

    module = (module_override or primary.get('module', 'septentrio')).strip().lower()
    if module not in VALID_MODULES:
        raise ValueError(f'Invalid GNSS module "{module}" — use: {", ".join(VALID_MODULES)}')

    septentrio = dict(primary.get('septentrio', {}))
    profile = (profile_override or septentrio.get('profile', 'rtk')).strip().lower()
    if module == 'septentrio' and profile not in VALID_PROFILES:
        raise ValueError(
            f'Invalid Septentrio profile "{profile}" — use: {", ".join(VALID_PROFILES)}'
        )

    sbg_section = dict(primary.get('sbg', {}))
    ublox_section = dict(primary.get('ublox', {}))

    sbg_params = _resolve_config_path(
        sbg_section.get('params_file', 'config/sbg_ellipse_d.yaml'),
        pkg_share,
    )
    ublox_params = _resolve_config_path(
        ublox_section.get('params_file', 'config/ublox.yaml'),
        pkg_share,
    )

    if enable_ntrip_override != '':
        enable_ntrip = enable_ntrip_override.lower() in ('true', '1', 'yes')
    else:
        enable_ntrip = bool(ntrip.get('auto_launch', False))

    robot = normalize_name_part(robot_name)
    rtcm_topic = ntrip.get('rtcm_topic') or default_rtcm_topic(robot)
    secrets_path = _resolve_config_path(
        ntrip.get('secrets', 'config/secrets.yaml'),
        pkg_share,
    )
    # Septentrio / NTRIP aux serial still use config/usv.yaml (see TODO in gnss_stack.yaml).
    ntrip_vehicle_config = default_vehicle_config_path()
    sbg_vehicle_config = _resolve_config_path(
        vehicle_config_override or stack.get('vehicle_config', 'config/vehicles/floatsam0.yaml'),
        pkg_share,
    )

    gga_source = (ntrip.get('gga_source') or 'auto').strip().lower()
    if gga_source not in VALID_GGA_SOURCES:
        raise ValueError(
            f'Invalid gga_source "{gga_source}" — use: {", ".join(VALID_GGA_SOURCES)}'
        )

    gga_topic = (ntrip.get('gga_topic') or '').strip()
    ros_only = False

    if gga_source == 'auto':
        if module == 'sbg':
            gga_source = 'ros_topic'
            ros_only = True
        elif module == 'ublox':
            gga_source = 'aux_serial'
            ros_only = False
        else:
            gga_source = 'aux_serial'
            ros_only = False
    elif gga_source == 'ros_topic':
        ros_only = True

    if gga_source == 'ros_topic' and not gga_topic:
        gga_topic = default_nmea_topic(robot)

    return {
        'module': module,
        'profile': profile,
        'enable_ntrip': enable_ntrip,
        'sbg_params_file': sbg_params,
        'ublox_params_file': ublox_params,
        'ntrip': {
            'publish_rtcm': bool(ntrip.get('publish_rtcm', True)),
            'gga_source': gga_source,
            'gga_topic': gga_topic,
            'rtcm_topic': rtcm_topic,
            'secrets': secrets_path,
            'release_port': bool(ntrip.get('release_port', True)),
            'gga_interval': int(ntrip.get('gga_interval', 10)),
            'gga_max_age': float(ntrip.get('gga_max_age', 5.0)),
            'lost_fix_grace': float(ntrip.get('lost_fix_grace', 15.0)),
            'rtcm_frame_id': ntrip.get('rtcm_frame_id', 'gnss'),
            'ros_only': ros_only,
            'rtcm_serial_relay': module == 'septentrio',
        },
        'vehicle_config': ntrip_vehicle_config,
        'sbg_vehicle_config': sbg_vehicle_config,
        'robot_name': robot,
        'sbg_sensor_namespace': sensor_namespace(robot, 'sbg'),
    }


def ntrip_client_executable(resolved_stack):
    """Return ros2 run executable name for this stack's NTRIP path."""
    ntrip = resolved_stack['ntrip']
    if ntrip['gga_source'] == 'ros_topic' and ntrip.get('ros_only'):
        return 'ntrip_ros_client'
    return 'ntrip_aux_client'


def build_ntrip_ros_argv(resolved_stack):
    """Build argv for ntrip_ros_client (without the executable name)."""
    ntrip = resolved_stack['ntrip']
    return [
        '--secrets', ntrip['secrets'],
        '--nmea-topic', ntrip['gga_topic'],
        '--rtcm-topic', ntrip['rtcm_topic'],
        '--rtcm-frame-id', ntrip['rtcm_frame_id'],
        '--gga-interval', str(ntrip['gga_interval']),
        '--gga-max-age', str(ntrip['gga_max_age']),
        '--lost-fix-grace', str(ntrip['lost_fix_grace']),
    ]


def build_ntrip_argv(resolved_stack):
    """Build argv for the selected NTRIP client (without the executable name)."""
    if ntrip_client_executable(resolved_stack) == 'ntrip_ros_client':
        return build_ntrip_ros_argv(resolved_stack)
    return build_ntrip_aux_argv(resolved_stack)


def build_ntrip_aux_argv(resolved_stack):
    """Build argv for ntrip_aux_client (without the executable name)."""
    ntrip = resolved_stack['ntrip']
    argv = [
        '--secrets', ntrip['secrets'],
        '--vehicle-config', resolved_stack['vehicle_config'],
        '--gga-interval', str(ntrip['gga_interval']),
        '--gga-max-age', str(ntrip['gga_max_age']),
        '--lost-fix-grace', str(ntrip['lost_fix_grace']),
        '--rtcm-topic', ntrip['rtcm_topic'],
        '--rtcm-frame-id', ntrip['rtcm_frame_id'],
        '--gga-source', ntrip['gga_source'],
    ]

    if ntrip['publish_rtcm']:
        argv.append('--publish-rtcm')

    if ntrip['gga_source'] == 'ros_topic':
        argv.extend(['--gga-topic', ntrip['gga_topic']])

    if ntrip['ros_only']:
        argv.append('--ros-only')
    elif not ntrip.get('rtcm_serial_relay', True):
        argv.append('--no-serial-rtcm')
    elif ntrip['release_port']:
        argv.append('--release-port')

    return argv
