# SBG Ellipse-D — usage and configuration

Guide for the SBG Ellipse INS/GNSS on floatsam0 via `sbg_driver` and `usv_rtk_bringup`.

## Prerequisites

```bash
source /opt/ros/jazzy/setup.bash
source ~/usv-host-setup/config/ros-zenoh.env.sh   # ROBOT_NAME=floatsam_usv_0
source ~/floatsam_ws/install/setup.bash
```

| Requirement | Detail |
|-------------|--------|
| Driver package | [`sbg_ros2_driver`](https://github.com/SBG-Systems/sbg_ros2_driver) in workspace (`floatsam_ws/src/sbg_ros2_driver`) |
| Bringup package | `usv_rtk_bringup` |
| Robot namespace | `ROBOT_NAME=floatsam_usv_0` in `usv-host-setup/config/usv-robot.env.sh` |
| NTRIP credentials | `config/secrets.yaml` (from `config/secrets.yaml.example`) |
| USB device | `/dev/usv-sbg` (udev rule below) |

Build:

```bash
cd ~/floatsam_ws
colcon build --packages-select sbg_driver usv_rtk_bringup
source install/setup.bash
```

---

## Hardware and udev

The Ellipse-D is on a single FTDI USB serial link:

| Host | Device |
|------|--------|
| Symlink | `/dev/usv-sbg` |
| Baud (PORT_A) | **921600** on floatsam0 (device flash) |
| Driver namespace | `/floatsam_usv_0/sbg` |

Install udev once ([`udev/99-usv-sbg.rules`](../udev/99-usv-sbg.rules)):

```bash
sudo cp ~/floatsam_ws/install/usv_rtk_bringup/share/usv_rtk_bringup/udev/99-usv-sbg.rules \
  /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
ls -l /dev/usv-sbg
```

---

## Configuration model (three layers)

SBG config is split so hull-specific layout stays separate from sensor tuning:

| Layer | File | What to edit |
|-------|------|----------------|
| **Stack selector** | [`config/gnss_stack.yaml`](../config/gnss_stack.yaml) | `primary.module: sbg`, `vehicle_config`, NTRIP defaults |
| **Per-hull vehicle** | [`config/vehicles/floatsam_usv_0.yaml`](../config/vehicles/floatsam_usv_0.yaml) | Serial port/baud, antenna extrinsics (ROS FLU), TF frames |
| **Sensor / driver** | [`config/sbg_floatsam_usv_0.yaml`](../config/sbg_floatsam_usv_0.yaml) | Motion profile, output rates, `confWithRos`, magnetometer, GNSS rejection |

At launch, `sbg.launch.py` merges **vehicle** into the driver via `build_sbg_launch_overlay()`:

- `uartConf.portName` / `baudRate` from `vehicles/floatsam_usv_0.yaml` → `sbg.serial_*`
- GNSS lever arms from `extrinsics.gnss` / `aux1` with **ROS FLU → SBG FRD** conversion
- `output.frame_id` / `gps_frame_id` from vehicle extrinsics
- Shared NMEA and RTCM topic namespaces under `/{ROBOT_NAME}/`

Lever arms in vehicle YAML are **ROS FLU** (X forward, Y port/left, Z up). The overlay maps them to SBG IMU FRD (X forward, Y right, Z down) to match `imuAlignementLeverArm` in the sensor YAML.

Templates:

- [`config/sbg_ellipse_d.yaml`](../config/sbg_ellipse_d.yaml) — package default (`confWithRos: false`, SBG Center flash)
- Upstream example: `sbg_ros2_driver/config/example/ellipse_D_default.yaml`

### `confWithRos` — two modes

| `confWithRos` | Behaviour |
|---------------|-----------|
| `false` | Driver reads device flash only; YAML sensor sections are ignored on connect. Use when SBG Center is the source of truth. |
| `true` | Driver pushes `sensorParameters`, `gnss`, `output`, etc. from YAML on each start. |

RTCM subscribe and NMEA publish apply in both modes (set by launch overlay).

On floatsam0, `sbg_floatsam_usv_0.yaml` currently has `confWithRos: true`. Set `false` if you prefer flash-only and only need the launch overlay for serial/topics/lever arms.

---

## Launch

### Recommended — standalone

```bash
ros2 launch usv_rtk_bringup sbg.launch.py
```

With NTRIP in the same launch:

```bash
ros2 launch usv_rtk_bringup sbg.launch.py enable_ntrip:=true
```

### Via module switchboard

Set `primary.module: sbg` in `gnss_stack.yaml`, or:

```bash
ros2 launch usv_rtk_bringup all_gnss.launch.py module:=sbg enable_ntrip:=true
```

### Launch arguments (`sbg.launch.py`)

| Argument | Default | Description |
|----------|---------|-------------|
| `robot_name` | `$ROBOT_NAME` | Robot namespace prefix |
| `gnss_stack` | `config/gnss_stack.yaml` | Stack + vehicle + sensor file paths |
| `vehicle_config` | from `gnss_stack` | Override per-hull YAML |
| `sbg_params_file` | from `gnss_stack` | Override sensor YAML |
| `enable_ntrip` | from `gnss_stack` `ntrip.auto_launch` | Start `ntrip_ros_client` |
| `nmea_topic` | `/{robot}/nmea` | NMEA GGA topic for NTRIP |
| `rtcm_topic` | `/{robot}/rtcm` | Shared RTCM corrections topic |
| `log_level` | `INFO` | Driver log level |

---

## RTK / NTRIP (ROS path)

SBG has one UART — no Septentrio-style aux port. Corrections use ROS topics:

```
sbg_driver  →  /floatsam_usv_0/nmea     (GGA for caster)
ntrip_ros_client  ← subscribes GGA, publishes RTCM
sbg_driver  ←  /floatsam_usv_0/rtcm    (RTCM input)
```

NTRIP client: [`utilities/ntrip_ros_client`](../utilities/ntrip_ros_client) — connects only when valid GGA is present.

**Two terminals:**

```bash
# terminal 1 — driver
ros2 launch usv_rtk_bringup sbg.launch.py

# terminal 2 — NTRIP (after /floatsam_usv_0/nmea has GGA)
ros2 run usv_rtk_bringup ntrip_ros_client \
  --nmea-topic /floatsam_usv_0/nmea --rtcm-topic /floatsam_usv_0/rtcm
```

**One launch:**

```bash
ros2 launch usv_rtk_bringup sbg.launch.py enable_ntrip:=true
```

Credentials: `config/secrets.yaml`. Caster settings are **not** loaded by the SBG driver.

---

## ROS topics and TF

With `ROBOT_NAME=floatsam_usv_0`:

| Topic | Type | Notes |
|-------|------|-------|
| `/floatsam_usv_0/sbg/imu/data` | `sensor_msgs/Imu` | Standard IMU |
| `/floatsam_usv_0/sbg/imu/nav_sat_fix` | `sensor_msgs/NavSatFix` | GNSS fix |
| `/floatsam_usv_0/sbg/sbg/gps_pos` | `sbg_driver/SbgGpsPos` | Raw GNSS + RTK type, diff age |
| `/floatsam_usv_0/sbg/sbg/gps_hdt` | `sbg_driver/SbgGpsHdt` | Dual-antenna heading |
| `/floatsam_usv_0/sbg/sbg/ekf_nav` | `sbg_driver/SbgEkfNav` | INS navigation |
| `/floatsam_usv_0/nmea` | `nmea_msgs/Sentence` | GGA for NTRIP |
| `/floatsam_usv_0/rtcm` | `rtcm_msgs/Message` | RTCM corrections |

Static TF from vehicle extrinsics: `base_link` → `imu` → `gnss` / `aux1` / `vsm`.

---

## Monitoring

Live dashboard (auto-discovers SBG + RTCM):

```bash
ros2 run usv_rtk_bringup gnss_link_monitor
```

Shows RTK fix from `SbgGpsPos`, heading from `gps_hdt`, RTCM rate on `/floatsam_usv_0/rtcm`. See [gnss_link_monitor.md](gnss_link_monitor.md).

Quick checks:

```bash
ros2 topic hz /floatsam_usv_0/sbg/imu/data
ros2 topic echo /floatsam_usv_0/sbg/sbg/gps_pos --once
ros2 topic echo /floatsam_usv_0/nmea --once
ros2 param get /floatsam_usv_0/sbg/sbg_device gnss.primaryLeverArmY
```

---

## Direct `sbg_driver` (no launch file)

Bake vehicle overlay into one params file:

```bash
ros2 run usv_rtk_bringup merge_sbg_params --robot-name floatsam_usv_0 -o /tmp/sbg_merged.yaml
ros2 run sbg_driver sbg_device --ros-args \
  -r __ns:=/floatsam_usv_0/sbg \
  --params-file /tmp/sbg_merged.yaml
```

`merge_sbg_params` reads `gnss_stack.yaml` for vehicle + sensor paths. Override with `--vehicle-config`, `--sbg-params`, `--gnss-stack`.

---

## Editing checklist

### New hull or antenna layout

1. Copy `config/vehicles/floatsam_usv_0.yaml` → `config/vehicles/<hull>.yaml`
2. Edit `extrinsics` (ROS FLU, metres in IMU frame) and `sbg.serial_*`
3. Point `gnss_stack.yaml` → `vehicle_config: config/vehicles/<hull>.yaml`

### Sensor tuning (rates, marine profile, mag off, etc.)

Edit `config/sbg_floatsam_usv_0.yaml` — do **not** duplicate serial or lever arms there (launch overlay wins).

### Switch stack to SBG

In `config/gnss_stack.yaml`:

```yaml
primary:
  module: sbg
  sbg:
    params_file: config/sbg_floatsam_usv_0.yaml
vehicle_config: config/vehicles/floatsam_usv_0.yaml
```

Rebuild and source after YAML changes in the package.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| `SBG_TIME_OUT` on device info | Wrong baud | floatsam0 uses **921600**; check `vehicles/floatsam_usv_0.yaml` `serial_baudrate` |
| `SBG_INVALID_FRAME` / huge payload sizes | Baud mismatch (garbage on wire) | Same as above; `fallbackBaudRates` in sensor YAML helps auto-detect |
| No `/floatsam_usv_0/nmea` | Driver not publishing or wrong namespace | Confirm launch log: `nmea=/floatsam_usv_0/nmea`; check `nmea.publish: true` in overlay |
| NTRIP never connects | No valid GGA | Wait for sky view; `ros2 topic echo /floatsam_usv_0/nmea` — GGA quality ≥ 1 |
| RTK stays standalone | No RTCM | Run `ntrip_ros_client`; check `ros2 topic hz /floatsam_usv_0/rtcm` |
| Heading `Insufficient obs` | Dual-antenna not configured or no sky | Check SBG Center / `gps_hdt` output enabled; verify lever arms in vehicle YAML |
| Wrong lever arms in driver | Edited sensor YAML only | Edit `config/vehicles/floatsam_usv_0.yaml`; overlay sets `gnss.primaryLeverArm*` |

Debug launch:

```bash
ros2 launch usv_rtk_bringup sbg.launch.py log_level:=DEBUG
```

Healthy startup log includes:

```
SBG_DRIVER - serial interface /dev/usv-sbg at 921600 bps
SBG_DRIVER - productCode = ELLIPSE-D-...
```

---

## Related docs

- [launch/README.md](../launch/README.md) — module switchboard, NTRIP clients
- [gnss_link_monitor.md](gnss_link_monitor.md) — live fix/RTCM dashboard
- [TODO.md](TODO.md) — Septentrio vehicle YAML merge still pending
- [Upstream sbg_ros2_driver](https://github.com/SBG-Systems/sbg_ros2_driver)
