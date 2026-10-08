"""Robot namespace helpers for usv_rtk_bringup launch files."""

from launch.actions import DeclareLaunchArgument
from launch.substitutions import EnvironmentVariable, LaunchConfiguration

SENSOR_UBLOX = 'ublox'
SENSOR_SEPTENTRIO = 'septentrio'
SENSOR_SBG = 'sbg'


def launch_arg(context, name):
    return LaunchConfiguration(name).perform(context)


def normalize_name_part(value):
    return (value or '').strip().strip('/')


def sensor_namespace(robot_name, sensor_name):
    """Compose {robot_name}/{sensor_name}, omitting empty parts."""
    robot = normalize_name_part(robot_name)
    sensor = normalize_name_part(sensor_name)
    if robot and sensor:
        return f'{robot}/{sensor}'
    return robot or sensor or ''


def resolve_sensor_namespace(
    context,
    sensor_name,
    *,
    robot_name_arg='robot_name',
    namespace_arg='namespace',
):
    """Use explicit namespace launch arg, else {robot_name}/{sensor_name}."""
    explicit = launch_arg(context, namespace_arg)
    if explicit:
        return normalize_name_part(explicit)
    robot = launch_arg(context, robot_name_arg)
    return sensor_namespace(robot, sensor_name)


def default_rtcm_topic(robot_name, explicit=''):
    """Shared RTCM topic: /{robot_name}/rtcm or /rtcm when unset."""
    if explicit:
        return explicit
    robot = normalize_name_part(robot_name)
    return f'/{robot}/rtcm' if robot else '/rtcm'


def default_nmea_topic(robot_name, explicit=''):
    """Shared NMEA topic for NTRIP GGA: /{robot_name}/nmea or /nmea when unset."""
    if explicit:
        return explicit
    robot = normalize_name_part(robot_name)
    return f'/{robot}/nmea' if robot else '/nmea'


def robot_topic_namespace(robot_name):
    """Prefix for sbg_driver rtcm/nmea.namespace params (e.g. /floatsam_usv_0)."""
    robot = normalize_name_part(robot_name)
    return f'/{robot}' if robot else ''


def declare_robot_name_argument():
    return DeclareLaunchArgument(
        'robot_name',
        default_value=EnvironmentVariable('ROBOT_NAME', default_value=''),
        description='Top-level robot namespace (e.g. floatsam_usv_0). '
        'GNSS topics are under {robot_name}/{ublox|septentrio|sbg}/. '
        'Set ROBOT_NAME in usv-host-setup/config/usv-robot.env.sh.',
    )


def declare_namespace_override_argument(sensor_name):
    return DeclareLaunchArgument(
        'namespace',
        default_value='',
        description=f'Override full ROS namespace (default: {{robot_name}}/{sensor_name})',
    )
