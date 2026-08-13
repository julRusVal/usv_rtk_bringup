"""Remap Septentrio dual-antenna AttEuler into SMARC body-frame angles."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class MountMode(str, Enum):
    AUTO = 'auto'
    BEAM = 'beam'
    LONGITUDINAL = 'longitudinal'


class ResolvedMount(str, Enum):
    BEAM = 'beam'
    LONGITUDINAL = 'longitudinal'


@dataclass(frozen=True)
class BodyAttitude:
    compass_deg: float
    yaw_rad: float
    pitch_rad: float
    roll_rad: float
    mount: ResolvedMount


ORIENTATION_COV_UNKNOWN = (-1.0,) + (0.0,) * 8
ANGULAR_VEL_COV_UNKNOWN = (-1.0,) + (0.0,) * 8
LINEAR_ACCEL_COV_UNKNOWN = (-1.0,) + (0.0,) * 8

_DEG2RAD_SQ = (math.pi / 180.0) ** 2


def _finite(value: float) -> bool:
    return not (math.isnan(value) or math.isinf(value))


def wrap_yaw_rad(yaw_rad: float) -> float:
    """Wrap radians to (-pi, pi]."""
    return math.atan2(math.sin(yaw_rad), math.cos(yaw_rad))


def classify_mount(baseline_xyz: tuple[float, float, float]) -> ResolvedMount:
    dx, dy, _dz = baseline_xyz
    if abs(dx) > abs(dy):
        return ResolvedMount.LONGITUDINAL
    if abs(dy) > abs(dx):
        return ResolvedMount.BEAM
    return ResolvedMount.LONGITUDINAL


def baseline_from_extrinsics(extrinsics: dict[str, Any]) -> tuple[float, float, float]:
    """Main (gnss) to aux1 vector in the parent frame (ROS FLU)."""
    gnss = extrinsics.get('gnss', {}).get('xyz', [0.0, 0.0, 0.0])
    aux1 = extrinsics.get('aux1', {}).get('xyz', [0.0, 0.0, 0.0])
    return (
        float(aux1[0]) - float(gnss[0]),
        float(aux1[1]) - float(gnss[1]),
        float(aux1[2]) - float(gnss[2]),
    )


def resolve_mount_mode(
    requested: str,
    baseline_xyz: tuple[float, float, float],
) -> ResolvedMount:
    mode = MountMode(requested.lower())
    if mode == MountMode.BEAM:
        return ResolvedMount.BEAM
    if mode == MountMode.LONGITUDINAL:
        return ResolvedMount.LONGITUDINAL
    return classify_mount(baseline_xyz)


def attitude_valid(msg: Any) -> bool:
    return int(msg.error) == 0 and int(msg.mode) >= 1


def covariance_valid(msg: Any) -> bool:
    return int(msg.error) == 0


def roll_sign_from_baseline(baseline_xyz: tuple[float, float, float]) -> float:
    _bx, by, _bz = baseline_xyz
    return math.copysign(1.0, by) if abs(by) > 1e-6 else 1.0


def quaternion_from_rpy(
    roll_rad: float,
    pitch_rad: float,
    yaw_rad: float,
) -> tuple[float, float, float, float]:
    """Quaternion (x, y, z, w) for body roll/pitch/yaw (REP-103, Rz*Ry*Rx)."""
    cy = math.cos(yaw_rad * 0.5)
    sy = math.sin(yaw_rad * 0.5)
    cp = math.cos(pitch_rad * 0.5)
    sp = math.sin(pitch_rad * 0.5)
    cr = math.cos(roll_rad * 0.5)
    sr = math.sin(roll_rad * 0.5)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return (x, y, z, w)


def remap_orientation_covariance(
    msg: Any,
    mount: ResolvedMount,
    baseline_xyz: tuple[float, float, float],
) -> tuple[float, ...] | None:
    """Map AttCovEuler (deg^2) to Imu orientation_covariance (rad^2, roll/pitch/yaw)."""
    if not covariance_valid(msg):
        return None

    chh = float(msg.cov_headhead)
    cpp = float(msg.cov_pitchpitch)
    crr = float(msg.cov_rollroll)
    chp = float(msg.cov_headpitch)
    chr_ = float(msg.cov_headroll)
    cpr = float(msg.cov_pitchroll)
    roll_sign = roll_sign_from_baseline(baseline_xyz)

    if mount == ResolvedMount.BEAM:
        cov_deg2 = (
            cpp,
            roll_sign * cpr,
            roll_sign * chp,
            roll_sign * cpr,
            crr,
            chr_,
            roll_sign * chp,
            chr_,
            chh,
        )
    else:
        cov_deg2 = (
            crr,
            cpr,
            chr_,
            cpr,
            cpp,
            chp,
            chr_,
            chp,
            chh,
        )

    return tuple(value * _DEG2RAD_SQ for value in cov_deg2)


def remap_attitude(
    msg: Any,
    baseline_xyz: tuple[float, float, float],
    mount_mode: str = 'auto',
    *,
    use_ros_axis_orientation: bool = True,
) -> BodyAttitude | None:
    """Convert AttEuler to SMARC body-frame angles.

    When use_ros_axis_orientation is true (default, matches septentrio driver),
    msg.heading is ROS ENU yaw in degrees.
    """
    if not attitude_valid(msg):
        return None

    heading_ros_deg = float(msg.heading)
    pitch_deg = float(msg.pitch)
    roll_deg = float(msg.roll)

    if not _finite(heading_ros_deg):
        return None

    if use_ros_axis_orientation:
        compass_deg = (90.0 - heading_ros_deg) % 360.0
        yaw_rad = wrap_yaw_rad(math.radians(heading_ros_deg))
    else:
        compass_deg = heading_ros_deg % 360.0
        yaw_rad = wrap_yaw_rad(math.radians(90.0 - compass_deg))

    mount = resolve_mount_mode(mount_mode, baseline_xyz)
    roll_sign = roll_sign_from_baseline(baseline_xyz)

    if mount == ResolvedMount.BEAM:
        pitch_rad = math.radians(roll_deg) if _finite(roll_deg) else 0.0
        pitch_source = pitch_deg
        roll_rad = roll_sign * math.radians(pitch_source) if _finite(pitch_source) else 0.0
    else:
        pitch_rad = math.radians(pitch_deg) if _finite(pitch_deg) else 0.0
        roll_rad = math.radians(roll_deg) if _finite(roll_deg) else 0.0

    return BodyAttitude(
        compass_deg=compass_deg,
        yaw_rad=yaw_rad,
        pitch_rad=pitch_rad,
        roll_rad=roll_rad,
        mount=mount,
    )
