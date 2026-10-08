# GNSS launch guide (`all_gnss.launch.py`)

One entry point for all RTK hardware. Pick the module in [`config/gnss_stack.yaml`](../config/gnss_stack.yaml) or override `module:=…` at launch.

## Before you launch

```bash
source /opt/ros/jazzy/setup.bash
source ~/usv-host-setup/config/ros-zenoh.env.sh   # ROBOT_NAME=floatsam_usv_0, Zenoh RMW
source ~/floatsam_ws/install/setup.bash
ros2 daemon stop   # if node/topic list looks stale
```

## Module selector (`primary.module` in gnss_stack.yaml)

| Module | Config | NTRIP GGA source | RTCM delivery | Topics (under `/floatsam_usv_0/…`) |
|--------|--------|------------------|---------------|-------------------------------|
| `septentrio` + `profile: rtk` **(default)** | `config/rtk.yaml` | aux serial (`/dev/usv-rtk-aux`) | aux serial + optional ROS | `septentrio/navsatfix`, `pvtgeodetic`, … |
| `septentrio` + `profile: gnss` | `config/gnss.yaml` | aux serial | same | same namespace, no RTK on USB2 |
| `septentrio` + `profile: rtk_heading` | `rtk.yaml` + `rtk_heading.yaml` | aux serial | same | + `septentrio/heading`, `yaw`, `imu`, … |
| `sbg` | `config/sbg_floatsam_usv_0.yaml` + `config/vehicles/floatsam_usv_0.yaml` | ROS `/nmea` from driver | ROS `/{robot}/rtcm` only | `sbg/*` — see [docs/sbg.md](../docs/sbg.md) |
| `ublox` | `config/ublox.yaml` | aux serial (if available) | ROS `/{robot}/rtcm` only | `ublox/fix`, … |

Override without editing YAML:

```bash
ros2 launch usv_rtk_bringup all_gnss.launch.py module:=sbg
ros2 launch usv_rtk_bringup all_gnss.launch.py module:=ublox
ros2 launch usv_rtk_bringup all_gnss.launch.py profile:=rtk_heading
```

## Vehicle vs sensor config

| Layer | SBG (`module:=sbg`) | Septentrio (default) |
|-------|---------------------|----------------------|
| Per-hull geometry, serial | `config/vehicles/floatsam_usv_0.yaml` (via `gnss_stack.yaml` → `vehicle_config`) | `config/usv.yaml` |
| Sensor/driver tuning | `config/sbg_floatsam_usv_0.yaml` | `config/rtk.yaml`, `config/gnss.yaml`, … |

See [docs/sbg.md](../docs/sbg.md) for full SBG setup.

`vehicle_config:=/path/to/hull.yaml` overrides the SBG vehicle file only.

> **TODO:** Septentrio still uses `config/usv.yaml` directly — the per-hull `config/vehicles/` split is implemented for SBG first; Septentrio vehicle config is a little behind.

## Advanced: Septentrio + u-blox

```bash
ros2 launch usv_rtk_bringup all_gnss.launch.py module:=septentrio enable_ublox:=true
```

## NTRIP clients

Credentials in `config/secrets.yaml`. All modules can share `/{ROBOT_NAME}/rtcm` when corrections are published to ROS.

| Client | Use when | GGA in | RTCM out |
|--------|----------|--------|----------|
| [`ntrip_aux_client`](../utilities/ntrip_aux_client) | Septentrio (default) | aux serial `/dev/usv-rtk-aux` | aux serial (+ optional ROS) |
| [`ntrip_ros_client`](../utilities/ntrip_ros_client) | SBG, ROS-only paths | `nmea_msgs/Sentence` topic | `rtcm_msgs/Message` topic |

Both clients connect to the caster **only with a valid GGA fix** and disconnect when the fix is lost or stale.

See [docs/TODO.md](../docs/TODO.md) for Septentrio vehicle-config follow-ups.

**Manual (two terminals)** — default (`ntrip.auto_launch: false`):

```bash
# Terminal 1 — driver
ros2 launch usv_rtk_bringup all_gnss.launch.py

# Terminal 2 — Septentrio (after "Setup complete.")
ros2 run usv_rtk_bringup ntrip_aux_client --release-port --publish-rtcm \
  --rtcm-topic /floatsam_usv_0/rtcm

# Terminal 2 — SBG (after /nmea has GGA)
ros2 run usv_rtk_bringup ntrip_ros_client \
  --nmea-topic /floatsam_usv_0/nmea --rtcm-topic /floatsam_usv_0/rtcm

# Terminal 2 — u-blox (GGA from aux serial if wired)
ros2 run usv_rtk_bringup ntrip_aux_client --release-port --publish-rtcm \
  --no-serial-rtcm --rtcm-topic /floatsam_usv_0/rtcm
```

**Auto-launch (single command):**

```bash
ros2 launch usv_rtk_bringup all_gnss.launch.py enable_ntrip:=true
# or set ntrip.auto_launch: true in gnss_stack.yaml
```

Verify: `ros2 run usv_rtk_bringup gnss_link_monitor` — see `docs/verify_rtk_corrections.md`.

## Launch tree

```
all_gnss.launch.py
├── [module=septentrio]  rtk.launch.py | gnss.launch.py | rtk_heading.launch.py
├── [module=sbg]         sbg.launch.py
├── [module=ublox]       ublox.launch.py
├── [enable_ublox]       ublox.launch.py  (with septentrio only)
└── [enable_ntrip]       ntrip_ros_client or ntrip_aux_client (from gnss_stack.yaml)
```

## Launch args

| Arg | Default | Notes |
|-----|---------|-------|
| `module` | from `gnss_stack.yaml` | `septentrio`, `sbg`, `ublox` |
| `profile` | from YAML | Septentrio only: `gnss`, `rtk`, `rtk_heading` |
| `gnss_stack` | `config/gnss_stack.yaml` | Module + NTRIP defaults |
| `enable_ntrip` | from YAML `ntrip.auto_launch` | `true` / `false` |
| `enable_ublox` | `false` | Add u-blox alongside Septentrio |
| `robot_name` | `$ROBOT_NAME` | From `usv-robot.env.sh` |
| `log_level` | `INFO` | |

```bash
ros2 launch usv_rtk_bringup all_gnss.launch.py --show-args
```
