"""Load USV vehicle YAML config and build static transforms."""
import copy
import os
import tempfile

import yaml
from ament_index_python.packages import get_package_share_directory


def default_vehicle_config_path():
    pkg_share = get_package_share_directory('usv_rtk_bringup')
    return os.path.join(pkg_share, 'config', 'usv.yaml')


def resolve_config_path(path, pkg_share=None):
    """Resolve package-relative config path to an absolute path."""
    if not path:
        return ''
    if os.path.isabs(path):
        return path
    if pkg_share is None:
        pkg_share = get_package_share_directory('usv_rtk_bringup')
    candidate = os.path.join(pkg_share, path)
    if os.path.isfile(candidate):
        return candidate
    return path


def resolve_sbg(config):
    sbg = dict(config.get('sbg', {}))
    sbg.setdefault('serial_device', '/dev/usv-sbg')
    sbg.setdefault('serial_baudrate', 115200)
    return sbg


def _xyz_tuple(frame):
    xyz = frame.get('xyz', [0.0, 0.0, 0.0])
    return float(xyz[0]), float(xyz[1]), float(xyz[2])


def flu_xyz_to_sbg_frd(x, y, z):
    """Convert ROS FLU offsets (imu/base_link) to SBG IMU FRD lever arms.

    SBG Ellipse alignment in sbg_floatsam_usv_0.yaml uses axisDirectionX=FORWARD,
    axisDirectionY=RIGHT (FRD). Vehicle extrinsics are stored in ROS FLU.
    """
    return float(x), float(-y), float(-z)


def prefixed_frame(robot_name, frame):
    """'<robot_name>/<frame>' (REP-105 multi-robot style); unchanged if robot_name is empty or the
    frame already has a prefix."""
    robot = (robot_name or '').strip('/')
    if not robot or '/' in frame:
        return frame
    return f'{robot}/{frame}'


def build_sbg_param_overlay(config, robot_name=''):
    """Merge vehicle YAML (extrinsics, sbg serial) into sbg_driver ROS parameters.

    With robot_name, all frames are prefixed (<robot>/imu, <robot>/gnss) and the SBG's own INS
    solution goes to a parallel reference branch utm -> <robot>/sbg_odom -> <robot>/sbg_base_link
    (only published in full navigation mode), never the main odom/base_link (robot_localization owns
    those). See usv-host-setup docs/usv-bringup-roadmap.md WS4.
    """
    extrinsics = resolve_extrinsics(config, robot_name)
    sbg = resolve_sbg(config)
    gnss = extrinsics['gnss']
    aux1 = extrinsics['aux1']
    imu = extrinsics['imu']

    px, py, pz = flu_xyz_to_sbg_frd(*_xyz_tuple(gnss))
    sx, sy, sz = flu_xyz_to_sbg_frd(*_xyz_tuple(aux1))

    overlay = {
        'uartConf.portName': sbg['serial_device'],
        'uartConf.baudRate': int(sbg['serial_baudrate']),
        'gnss.primaryLeverArmX': px,
        'gnss.primaryLeverArmY': py,
        'gnss.primaryLeverArmZ': pz,
        'gnss.secondaryLeverArmX': sx,
        'gnss.secondaryLeverArmY': sy,
        'gnss.secondaryLeverArmZ': sz,
        'output.frame_id': imu.get('child_frame', 'imu'),
        'output.gps_frame_id': gnss.get('child_frame', 'gnss'),
        'odometry.initFrameId': 'utm',
        'odometry.odomFrameId': prefixed_frame(robot_name, 'sbg_odom'),
        'odometry.baseFrameId': prefixed_frame(robot_name, 'sbg_base_link'),
    }

    if any(v != 0.0 for v in (sx, sy, sz)):
        overlay['gnss.secondaryLeverMode'] = 3

    return overlay


def build_sbg_launch_overlay(
    vehicle_config,
    robot_name='',
    *,
    rtcm_topic='',
    nmea_topic='',
):
    """Vehicle + robot topic overlay for sbg_driver (launch or merged params file)."""
    from robot_namespace import (
        default_nmea_topic,
        default_rtcm_topic,
        robot_topic_namespace,
    )

    if isinstance(vehicle_config, (str, os.PathLike)):
        vehicle_raw = load_vehicle_config(vehicle_config)
    else:
        vehicle_raw = vehicle_config

    resolved_rtcm = default_rtcm_topic(robot_name, rtcm_topic)
    resolved_nmea = default_nmea_topic(robot_name, nmea_topic)
    topic_namespace = robot_topic_namespace(robot_name)

    return {
        **build_sbg_param_overlay(vehicle_raw, robot_name),
        'rtcm.namespace': topic_namespace,
        'rtcm.topic_name': 'rtcm' if topic_namespace else resolved_rtcm.lstrip('/'),
        'rtcm.subscribe': True,
        'nmea.publish': True,
        'nmea.namespace': topic_namespace,
        'nmea.topic_name': 'nmea' if topic_namespace else resolved_nmea.lstrip('/'),
    }


def nested_from_flat(flat_params):
    """Turn dotted ROS param keys into a nested dict."""
    nested = {}
    for key, value in flat_params.items():
        parts = key.split('.')
        node = nested
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return nested


def deep_merge_dict(base, overlay):
    """Recursively merge overlay into base (mutates and returns base)."""
    for key, value in overlay.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            deep_merge_dict(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def merge_sbg_driver_params(
    sbg_params_path,
    vehicle_config_path,
    robot_name='',
    *,
    rtcm_topic='',
    nmea_topic='',
):
    """Merge sensor YAML + vehicle overlay into one sbg_driver params dict."""
    with open(sbg_params_path, 'r', encoding='utf-8') as handle:
        base = yaml.safe_load(handle) or {}

    if '/**' not in base:
        base['/**'] = {'ros__parameters': {}}
    if 'ros__parameters' not in base['/**']:
        base['/**']['ros__parameters'] = {}

    ros_params = base['/**']['ros__parameters']

    overlay_flat = build_sbg_launch_overlay(
        vehicle_config_path,
        robot_name,
        rtcm_topic=rtcm_topic,
        nmea_topic=nmea_topic,
    )
    deep_merge_dict(ros_params, nested_from_flat(overlay_flat))

    return {
        '/**': {
            'ros__parameters': ros_params,
        }
    }


def write_merged_sbg_params(
    output_path,
    sbg_params_path,
    vehicle_config_path,
    robot_name='',
    *,
    rtcm_topic='',
    nmea_topic='',
):
    merged = merge_sbg_driver_params(
        sbg_params_path,
        vehicle_config_path,
        robot_name,
        rtcm_topic=rtcm_topic,
        nmea_topic=nmea_topic,
    )
    with open(output_path, 'w', encoding='utf-8') as handle:
        yaml.safe_dump(merged, handle, sort_keys=False)
    return output_path


def load_vehicle_config(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def resolve_network(config, overrides):
    network = dict(config.get('network', {}))
    receiver_ip = overrides.get('receiver_ip', '')
    if receiver_ip:
        network['receiver_ip'] = receiver_ip

    receiver_port = overrides.get('receiver_port', '')
    if receiver_port:
        network['receiver_port'] = int(receiver_port)

    network.setdefault('receiver_ip', '192.168.3.1')
    network.setdefault('receiver_port', 28784)
    network.setdefault('connection', 'tcp')
    network.setdefault('serial_device', '/dev/usv-rtk')
    network.setdefault('serial_baudrate', 921600)
    network.setdefault('aux_serial_device', '/dev/usv-rtk-aux')
    network.setdefault('aux_serial_baudrate', 115200)
    network.setdefault('aux_receiver_port', 'USB2')
    return network


def write_temp_commands(commands, prefix='aux_nmea_'):
    """Write Septentrio custom commands to a temp file for the driver."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix='.cmd')
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(commands) + '\n')
    return path


def aux_nmea_commands(aux_port):
    """Custom Septentrio commands injected during driver setup (mosaic-G5).

    Runs after the driver clears existing streams. USB1 must be set to SBF+NMEA
    or the driver receives no SBF on /dev/usv-rtk (G5 defaults to sdio none).

    aux_port is the receiver command port for the aux link (e.g. USB2).
    """
    cmd_port = aux_port or 'USB2'
    # Stream4/5 avoid clashing with driver SBF streams 1–3 on the main port.
    return [
        'sdio, USB1, auto, SBF+NMEA',
        f'sdio, {cmd_port}, auto, NMEA',
        f'sno, Stream4, {cmd_port}, GGA, sec1',
        f'sno, Stream5, {cmd_port}, RMC, sec1',
    ]


def resolve_device_uri(network):
    if network.get('connection', 'tcp') == 'serial':
        device = network['serial_device']
        if not device.startswith('serial:'):
            device = f'serial:{device}'
        return device
    return f"tcp://{network['receiver_ip']}:{network['receiver_port']}"


def resolve_extrinsics(config, robot_name=''):
    """Extrinsics with defaults; frame names prefixed with robot_name when given."""
    extrinsics = dict(config.get('extrinsics', {}))
    extrinsics['base_frame'] = prefixed_frame(robot_name, extrinsics.get('base_frame', 'base_link'))
    for name in ('imu', 'gnss', 'aux1', 'vsm'):
        entry = dict(extrinsics.get(name, {}))
        entry['child_frame'] = prefixed_frame(robot_name, entry.get('child_frame', name))
        entry.setdefault('xyz', [0.0, 0.0, 0.0])
        entry.setdefault('rpy', [0.0, 0.0, 0.0])
        extrinsics[name] = entry
    return extrinsics


def load_resolved_config(vehicle_config_path, overrides, robot_name=''):
    config = load_vehicle_config(vehicle_config_path)
    network = resolve_network(config, overrides)
    extrinsics = resolve_extrinsics(config, robot_name)
    return {
        'vehicle': dict(config.get('vehicle', {})),
        'network': network,
        'extrinsics': extrinsics,
        'device': resolve_device_uri(network),
    }


def static_transform_node(name, parent, child, xyz, rpy):
    from launch_ros.actions import Node

    args = [str(v) for v in (*xyz, *rpy, parent, child)]
    return Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name=name,
        arguments=args,
        output='screen',
    )


def static_transform_nodes(extrinsics):
    base = extrinsics['base_frame']
    nodes = [
        static_transform_node(
            'tf_imu',
            base,
            extrinsics['imu']['child_frame'],
            extrinsics['imu']['xyz'],
            extrinsics['imu']['rpy'],
        ),
        static_transform_node(
            'tf_gnss',
            extrinsics['imu']['child_frame'],
            extrinsics['gnss']['child_frame'],
            extrinsics['gnss']['xyz'],
            extrinsics['gnss']['rpy'],
        ),
        static_transform_node(
            'tf_aux1',
            extrinsics['imu']['child_frame'],
            extrinsics['aux1']['child_frame'],
            extrinsics['aux1']['xyz'],
            extrinsics['aux1']['rpy'],
        ),
        static_transform_node(
            'tf_vsm',
            extrinsics['imu']['child_frame'],
            extrinsics['vsm']['child_frame'],
            extrinsics['vsm']['xyz'],
            extrinsics['vsm']['rpy'],
        ),
    ]
    return nodes
