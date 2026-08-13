"""Load USV vehicle YAML config and build static transforms."""
import os
import tempfile

import yaml
from ament_index_python.packages import get_package_share_directory


def default_vehicle_config_path():
    pkg_share = get_package_share_directory('usv_rtk_bringup')
    return os.path.join(pkg_share, 'config', 'usv.yaml')


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


def resolve_extrinsics(config):
    extrinsics = dict(config.get('extrinsics', {}))
    extrinsics.setdefault('base_frame', 'base_link')
    for name in ('imu', 'gnss', 'aux1', 'vsm'):
        extrinsics.setdefault(name, {})
        extrinsics[name].setdefault('child_frame', name)
        extrinsics[name].setdefault('xyz', [0.0, 0.0, 0.0])
        extrinsics[name].setdefault('rpy', [0.0, 0.0, 0.0])
    return extrinsics


def load_resolved_config(vehicle_config_path, overrides):
    config = load_vehicle_config(vehicle_config_path)
    network = resolve_network(config, overrides)
    extrinsics = resolve_extrinsics(config)
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
