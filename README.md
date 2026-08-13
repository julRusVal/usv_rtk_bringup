# usv_rtk_bringup

ROS 2 bringup package for **USV RTK GNSS** — launch files and configuration for a Septentrio receiver with NTRIP corrections.

## Prerequisites

- ROS 2 Humble
- `septentrio_gnss_driver` built in the workspace (`sonar_ws/src/septentrio_gnss_driver`)

## Building

```bash
cd ~/sonar_ws
colcon build --packages-select usv_rtk_bringup
source install/setup.bash
```

## udev rules (USB serial)

When the Septentrio receiver is connected over USB it appears as two ACM ports (`ttyACM0` / `ttyACM1`). Install the udev rules once to get stable symlinks:

| Symlink | Port | Use |
|---|---|---|
| `/dev/usv-rtk` | interface 0 | Main GNSS data (used by the driver) |
| `/dev/usv-rtk-aux` | interface 2 | Auxiliary serial port |

```bash
sudo cp ~/sonar_ws/install/usv_rtk_bringup/share/usv_rtk_bringup/udev/99-usv-rtk-septentrio.rules \
  /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Verify after replugging the receiver:

```bash
ls -l /dev/usv-rtk /dev/usv-rtk-aux
```

Ensure your user is in the `dialout` group for serial access:

```bash
sudo usermod -aG dialout $USER
```

## Launch

Full RTK bringup (Septentrio driver + static TFs):

```bash
ros2 launch usv_rtk_bringup bringup.launch.py
```

Or launch the GNSS stack directly:

```bash
ros2 launch usv_rtk_bringup rtk.launch.py
```

### RTK with dual-antenna heading

Same RTK/aux-serial setup as `rtk.launch.py`, with dual-antenna heading enabled via a small parameter overlay on `rtk.yaml`:

```bash
ros2 launch usv_rtk_bringup rtk_heading.launch.py
ros2 run usv_rtk_bringup ntrip_aux_client --release-port
```

Requires a second antenna on **AUX1**. Lever arms come from `extrinsics.gnss` and `extrinsics.aux1` in `config/usv.yaml` (`get_spatial_config_from_tf: true`).

**Body-frame attitude** (SMARC units) is published by `dual_antenna_attitude_remap` when using this launch file:

| Topic | Type | Units | Meaning |
|-------|------|-------|---------|
| `/septentrio_rtk/heading` | `std_msgs/Float64` | degrees | Compass heading (0° = North, CW) |
| `/septentrio_rtk/yaw` | `std_msgs/Float64` | radians | ENU yaw (0 = East, CCW) |
| `/septentrio_rtk/pitch` | `std_msgs/Float64` | radians | Body pitch |
| `/septentrio_rtk/roll` | `std_msgs/Float64` | radians | Body roll |
| `/septentrio_rtk/imu` | `sensor_msgs/Imu` | quaternion + cov | Body orientation for `robot_localization` |

#### Why a remap node?

The Septentrio driver publishes raw dual-antenna attitude on `/atteuler` (`septentrio_gnss_driver/AttEuler`). Those angles are **not** body roll/pitch in the SMARC sense — they are defined in the receiver’s attitude frame, which is tied to the **antenna baseline** (main → AUX1), not to `base_link`.

With `use_ros_axis_orientation: true` in `config/rtk.yaml` (recommended), the driver converts receiver axes to ROS REP-103:

- `/atteuler.heading` is **ENU yaw in degrees** (0° = East, CCW), **not** compass north.
- `/atteuler.pitch` and `/atteuler.roll` are still labeled pitch/roll in the **receiver/baseline frame**.

The remap node (`utilities/dual_antenna_attitude_remap`, logic in `utilities/attitude_remap.py`) subscribes to `/atteuler` and `/attcoveuler`, classifies the antenna layout, and publishes body-frame values on `/septentrio_rtk/*`. Raw driver topics are unchanged for debugging.

#### Pitch always tracks the baseline — not the hull

mosaic-G5 defines AttEuler pitch and roll relative to the vector between the two antennas (see mosaic reference guide §1.11). The receiver **does not** rename those fields when you mount antennas port–starboard instead of bow–stern; it always fills the same `pitch` and `roll` slots using the same baseline-centric definition.

On this USV the antennas are on **Y** (`gnss` at `[0, 1, 0]`, `aux1` at `[0, -1, 0]` m in `config/usv.yaml`): a **beam** (port–starboard) baseline. In that geometry:

| Receiver field | Physical meaning on hull |
|----------------|--------------------------|
| `heading` | Yaw (about vertical) — maps directly after axis conversion |
| `pitch` | Rotation about the **lateral** baseline → **body roll** (port/starboard heel) |
| `roll` | Rotation about the **longitudinal** axis → **body pitch** (bow up/down); often **NaN** with a single AUX1 in modes 1–2 |

So if you echo `/atteuler` on a beam-mounted pair, **pitch will look like roll** (and vice versa) — that is expected receiver behavior, not a driver bug. Controllers and loggers that expect SMARC body angles need the remap.

#### Remap rules

Mount mode is chosen from TF `gnss` → `aux1` (fallback: `extrinsics` in `usv.yaml`), or forced with the `mount_mode` parameter (`auto` | `beam` | `longitudinal`):

| Layout | Detected when | Body `roll` | Body `pitch` |
|--------|---------------|-------------|--------------|
| **Longitudinal** (bow–stern baseline) | `abs(dx) > abs(dy)` | `atteuler.roll` (0 if NaN) | `atteuler.pitch` |
| **Beam** (port–starboard baseline) | `abs(dy) > abs(dx)` | `sign(dy) × atteuler.pitch` | `atteuler.roll` (0 if NaN) |

Heading conversion (ROS driver output):

- `compass_deg` = `(90° − heading_ros) mod 360°`
- `yaw_rad` = `heading_ros` converted to radians, wrapped to (−π, π]

Covariance from `/attcoveuler` follows the same pitch↔roll swap on beam mounts. Messages are published only when `atteuler.error == 0` and `atteuler.mode >= 1`.

```bash
ros2 topic echo /septentrio_rtk/heading --once   # compass deg
ros2 topic echo /septentrio_rtk/yaw --once       # ENU rad (~1.57 when bow north)
ros2 topic echo /septentrio_rtk/roll --once      # beam mount: from receiver pitch
ros2 topic echo /septentrio_rtk/imu --once       # orientation + covariance
ros2 run tf2_ros tf2_echo gnss aux1              # [0, -2, 0] → beam detected
```

Run standalone (without launch):

```bash
ros2 run usv_rtk_bringup dual_antenna_attitude_remap
```

### `robot_localization` integration

Use `/septentrio_rtk/imu` as an absolute orientation source in `ekf_localization_node`:

| EKF input | Source | Notes |
|-----------|--------|-------|
| Position | `navsat_transform_node` + `/navsatfix` | Standard GPS fusion |
| Yaw | `/septentrio_rtk/imu` `orientation` | Remapped body roll/pitch/yaw quaternion |
| Covariance | `/attcoveuler` (via node) | Beam mount swaps pitch/roll variance; yaw variance from heading |

`Imu` angular velocity and linear acceleration are unset (`-1` on covariance diagonal). Fuse **yaw** aggressively; treat **roll** cautiously on beam mounts; down-weight or disable **pitch** unless needed for control.

Example `ekf_localization_node` params (snippet):

```yaml
imu0: /septentrio_rtk/imu
imu0_config: [false, false, false,
              false, false, true,   # fuse yaw
              false, false, false,
              false, false, false,
              false, false, false]
imu0_differential: false
imu0_relative: false
imu0_queue_size: 5
```

Position fusion still requires `navsat_transform_node` (or a local ENU position source) wired separately.

### Phase 1: GNSS only (no RTK)

Standalone GNSS with NMEA on the aux serial port for `str2str` GGA relay (phase 2 adds RTCM on the same port):

```bash
ros2 launch usv_rtk_bringup gnss.launch.py
```

### Phase 2: NTRIP on aux serial (GGA-gated)

[`ntrip_aux_client`](utilities/ntrip_aux_client) uses **pygnssutils** (`GNSSNTRIPClient`). It reads GGA from the aux port, connects to the NTRIP caster only with a valid fix, and writes RTCM back on the same port.

**Prerequisites:** `pip install pyserial pygnssutils` · `gnss.launch.py` running (NMEA on aux)

```bash
# relay RTCM to receiver (typical)
ros2 run usv_rtk_bringup ntrip_aux_client --release-port

# also publish RTCM to ROS 2 (rtcm_msgs/Message)
ros2 run usv_rtk_bringup ntrip_aux_client --release-port --publish-rtcm

# custom topic / frame
ros2 run usv_rtk_bringup ntrip_aux_client --release-port --publish-rtcm \
  --rtcm-topic /ntrip/rtcm --rtcm-frame-id gnss
```

Startup prints all parameters (password redacted). Monitor RTCM:

```bash
ros2 topic echo /rtcm --once
ros2 topic hz /rtcm
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--release-port` | off | kill stale holders of `/dev/usv-rtk-aux` (`cat`, old `str2str`) |
| `--gga-interval` | 10 | seconds between GGA sent to caster |
| `--lost-fix-grace` | 15 | disconnect NTRIP after this long without valid GGA |
| `--publish-rtcm` | off | publish `rtcm_msgs/Message` while relaying to serial |
| `--rtcm-topic` | `/rtcm` | ROS 2 RTCM topic |
| `--secrets` | `config/secrets.yaml` | NTRIP credentials |
| `--vehicle-config` | `config/usv.yaml` | aux serial device/baud |

See [docs/verify_rtk_corrections.md](docs/verify_rtk_corrections.md) for verifying corrections end-to-end.

**Two terminals (full stack):**

```bash
# terminal 1 — driver on USB1, RTCM input on USB2, NMEA on aux for GGA
ros2 launch usv_rtk_bringup rtk.launch.py

# terminal 2 — NTRIP credentials from config/secrets.yaml
ros2 run usv_rtk_bringup ntrip_aux_client --release-port --publish-rtcm
```

Phase 1 without RTK (same aux NMEA setup, no `serial_1` RTK config):

```bash
ros2 launch usv_rtk_bringup gnss.launch.py
ros2 run usv_rtk_bringup ntrip_aux_client --release-port
```

Manual NMEA check (no NTRIP):

```bash
str2str -in serial://usv-rtk-aux:115200:8:n:1 -out stdout:
```

ROS NMEA topics are also published (`/septentrio_gnss_driver/gpgga`, `/gprmc`).

### Launch arguments

| Argument | Default | Description |
|---|---|---|
| `vehicle_config` | `config/usv.yaml` | Vehicle network and extrinsic settings |
| `gnss_params_file` | `config/gnss.yaml` | GNSS-only driver parameters (no RTK) |
| `rtk_params_file` | `config/rtk.yaml` | Septentrio driver parameters (external RTCM on USB2) |
| `rtk_heading_params_file` | `config/rtk_heading.yaml` | Dual-antenna heading overlay (with `rtk_heading.launch.py`) |
| `enable_aux_nmea` | `true` | GGA/RMC on aux port for `ntrip_aux_client` (`rtk.launch.py`) |
| `receiver_ip` | _(empty)_ | Override receiver IP from vehicle config |
| `receiver_port` | _(empty)_ | Override receiver TCP port |
| `log_level` | `INFO` | ROS log level |

Example with overrides:

```bash
ros2 launch usv_rtk_bringup rtk.launch.py receiver_ip:=192.168.3.1
```

## Configuration

| File | Purpose |
|---|---|
| `config/usv.yaml` | Receiver connection (TCP/serial), frame extrinsics |
| `config/gnss.yaml` | GNSS-only driver parameters (phase 1, no RTK) |
| `config/gnss_aux_nmea.cmd` | Custom commands: GGA/RMC on USB2 for str2str (override via `aux_nmea_cmd_file`; default commands are generated from `aux_receiver_port`) |
| `config/rtk.yaml` | Driver on `/dev/usv-rtk`; `rtk_settings.serial_1.port: USB2` for RTCM from `ntrip_aux_client` |
| `config/rtk_heading.yaml` | Dual-antenna heading overlay on `rtk.yaml` (`multi_antenna`, attitude topics) |
| `config/secrets.yaml` | NTRIP credentials for `ntrip_aux_client` / `check_swepos` only (gitignored) |
| `config/secrets.yaml.example` | Template for `config/secrets.yaml` |

Copy the secrets template and fill in your NTRIP account:

```bash
cp config/secrets.yaml.example config/secrets.yaml
# edit ntrip: caster, username, password, mountpoint, ...
```

`secrets.yaml` is **not** loaded by `rtk.launch.py`. The driver receives RTCM on receiver port **USB2** (`/dev/usv-rtk-aux` on the host) while `ntrip_aux_client` streams corrections there.

Edit `config/usv.yaml` for serial paths and extrinsics. Edit `config/rtk.yaml` for publish flags and receiver options.

### Driver appears hung at “Setting up Rx.”

This is usually **not a crash** — ROSaic blocks on receiver command/response handshakes during `configure_rx`. On mosaic-G5 it often finishes within a second and prints `Setup complete.`

While `gnss.launch.py` is running:

- Do **not** open `/dev/usv-rtk` or send admin commands on `/dev/usv-rtk-aux` (that can stall setup).
- Use `ros2 run usv_rtk_bringup check_serial --skip-main-query` to test the aux port instead.
- If it sits at “Setting up Rx.” for more than ~30 s, stop the launch (Ctrl-C) and retry once.

After `Setup complete.`, the driver may still look idle until SBF arrives on `/dev/usv-rtk`. mosaic-G5 ships with `USB1` set to `sdio … none`; this package injects `sdio, USB1, auto, SBF+NMEA` via the generated custom-command file so the driver can receive SBF.

Launch with debug logging if you need to see each command:

```bash
ros2 launch usv_rtk_bringup gnss.launch.py log_level:=DEBUG
```

## Verify

Check USB serial aliases and receiver connectivity (model/firmware via `gri`, optional NMEA on aux):

```bash
ros2 run usv_rtk_bringup check_serial
# while gnss.launch.py holds /dev/usv-rtk:
ros2 run usv_rtk_bringup check_serial --skip-main-query
```

**RTK corrections in use** — see **[docs/verify_rtk_corrections.md](docs/verify_rtk_corrections.md)** for a full guide (NTRIP client logs, GGA quality, `pvtgeodetic.mean_corr_age`, A/B test, troubleshooting).

Quick check while `rtk.launch.py` and `ntrip_aux_client` are running:

```bash
ros2 topic echo /septentrio_gnss_driver/pvtgeodetic --field mode --field mean_corr_age
# mean_corr_age > 0 and mode 2/3/4 ⇒ corrections active
```

```bash
ros2 topic echo /septentrio_gnss_driver/navsatfix
ros2 topic echo /septentrio_gnss_driver/pvtgeodetic
```

## Package layout

```
usv_rtk_bringup/
├── CMakeLists.txt
├── package.xml
├── config/
│   ├── gnss.yaml
│   ├── gnss_aux_nmea.cmd
│   ├── rtk.yaml
│   ├── rtk_heading.yaml
│   ├── secrets.yaml.example
│   └── usv.yaml
├── docs/
│   ├── verify_rtk_corrections.md
│   └── mosaic-G5 Firmware … (reference PDFs)
├── udev/
│   └── 99-usv-rtk-septentrio.rules
├── utilities/
│   ├── check_serial
│   ├── dual_antenna_attitude_remap
│   ├── attitude_remap.py
│   ├── check_swepos
│   ├── ntrip_aux_client
│   └── ntrip_secrets.py
└── launch/
    ├── bringup.launch.py
    ├── gnss.launch.py
    ├── rtk.launch.py
    ├── rtk_heading.launch.py
    ├── septentrio_launch.py
    └── vehicle_config.py
```
