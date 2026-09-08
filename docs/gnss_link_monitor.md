# GNSS link monitor (`gnss_link_monitor`)

Live terminal dashboard for GNSS fix quality across multiple sensors. Refreshes in-place (no scrolling log) and is meant for bring-up, RTK verification, and comparing receivers side by side.

```bash
ros2 run usv_rtk_bringup gnss_link_monitor
```

By default the monitor **scans the ROS graph every 3 s** for all `NavSatFix`, `AttEuler`, and `rtcm_msgs/Message` publishers, then groups GNSS data by namespace (`/{robot}/{sensor}`, e.g. `floatsam0/septentrio`).

---

## What it shows

### GNSS sensors (per namespace / NavSatFix topic)

Each block is labeled by namespace when the topic is `/{robot}/{sensor}/…`:

| Field | Source | Notes |
|-------|--------|-------|
| Fix type | `pvtgeodetic.mode` → `sbg/gps_pos` → `gpgga` → `gpsfix` → `navsatfix.status` | Best available; Septentrio PVT or SBG `SbgGpsPos.status.type` for RTK Fixed/Float |
| Position | `navsatfix` | lat / lon / alt |
| Cov ENU | `navsatfix.position_covariance` | σE, σN, σU (m); diagonal of ENU covariance |
| Quality | `pvtgeodetic`, `gpsfix`, or covariance fallback | SV count, horizontal/vertical accuracy, base count |
| Heading | `atteuler` + `attcoveuler` | For any `/{robot}/{sensor}/` namespace; see [Dual-antenna heading](#dual-antenna-heading) |
| Updated | message receive time | Age since last `navsatfix` |

Companion topics in the same namespace are subscribed automatically when present:

| NavSatFix topic | Auto companions |
|-----------------|-----------------|
| `…/navsatfix` | `gpsfix`, `pvtgeodetic`, `gpgga` |
| `…/imu/nav_sat_fix` (SBG) | `sbg/gps_pos`, `sbg/gps_hdt` |
| any under `/{robot}/{sensor}/` (non-SBG) | `atteuler`, `attcoveuler` |

### RTCM streams (per `rtcm_msgs/Message` topic)

| Field | Meaning |
|-------|---------|
| Rate | Message rate (Hz) and throughput (B/s) over a 5 s window |
| Last | Decoded RTCM message type (e.g. `GPS MSM7`) and payload size |
| Recent | Compact histogram of message types seen in the window |

RTCM type is parsed from the message preamble (no `pyrtcm` dependency).

---

## Prerequisites

```bash
source /opt/ros/jazzy/setup.bash
source ~/usv-host-setup/config/ros-zenoh.env.sh
source ~/floatsam_ws/install/setup.bash
```

---

## Usage

### Default (recommended)

```bash
ros2 run usv_rtk_bringup gnss_link_monitor
```

Discovers **all** publishers on the graph:

- every `sensor_msgs/NavSatFix` topic (e.g. `/floatsam0/septentrio/navsatfix`, `/floatsam0/sbg/imu/nav_sat_fix`)
- every `rtcm_msgs/Message` topic (e.g. `/floatsam0/rtcm`)
- every `septentrio_gnss_driver/AttEuler` topic (heading merged into the matching namespace)

New publishers appearing after the monitor starts are picked up on the next scan (~3 s). The monitor can start before the driver or NTRIP client.

### Full RTK stack example

```bash
# terminal 1
ros2 launch usv_rtk_bringup rtk.launch.py

# terminal 2
ros2 run usv_rtk_bringup ntrip_aux_client --release-port --publish-rtcm \
  --rtcm-topic /floatsam0/rtcm

# terminal 3 (can start first)
ros2 run usv_rtk_bringup gnss_link_monitor
```

Healthy output signals:

- **Fix:** `RTK Fixed` or `DGPS` with `corr > 0 s` on Septentrio
- **Quality:** `SVs` > 0, `σH` in cm range with RTK, `bases ≥ 1` for network RTK
- **RTCM:** steady Hz (often ~1 Hz for MSM mountpoints), `active`, recent MSM types

See also [verify_rtk_corrections.md](verify_rtk_corrections.md) for stage-by-stage proof and A/B tests.

### SBG Ellipse-D

With `sbg.launch.py` running:

```bash
ros2 run usv_rtk_bringup gnss_link_monitor
# or explicitly:
ros2 run usv_rtk_bringup gnss_link_monitor --topic /floatsam0/sbg/imu/nav_sat_fix
```

The monitor auto-subscribes to `sbg/gps_pos` and `sbg/gps_hdt` in the same namespace. **Fix** uses SBG position type (RTK Fixed/Float, DGPS, …) and **Heading** uses dual-antenna `gps_hdt` (true heading, pitch, baseline).

Healthy SBG + NTRIP:

- **Fix:** `RTK Fixed` with `(corr …s)` from `diff_age`
- **Quality:** `SVs` > 0, σE/N in cm range with RTK
- **RTCM:** active on `/floatsam0/rtcm`
- **Heading:** `h …°` with valid baseline when dual-antenna is configured

### Dual-antenna heading

With `profile:=rtk_heading`:

```bash
ros2 launch usv_rtk_bringup all_gnss.launch.py profile:=rtk_heading
ros2 run usv_rtk_bringup gnss_link_monitor
```

When `atteuler` is published under `/floatsam0/septentrio/`, the Septentrio block gains a **Heading** line:

```
[floatsam0/septentrio]  /floatsam0/septentrio/navsatfix
  ...
  Heading:  h 127.45°  pitch 1.20°  roll -0.30°  SVs 12  σ_h 0.15°  mode 4
```

Values are raw receiver-frame angles from `AttEuler` (not remapped body-frame `heading`/`yaw` from `dual_antenna_attitude_remap`). For body-frame attitude, use the remap topics documented in the [package README](../README.md#rtk-with-dual-antenna-heading).

### Fixed topic list (no discovery)

```bash
ros2 run usv_rtk_bringup gnss_link_monitor \
  --no-discover \
  --topic /floatsam0/septentrio/navsatfix \
  --rtcm-topic /floatsam0/rtcm
```

Repeat `--topic` or `--rtcm-topic` for multiple streams.

### GNSS only (no RTCM section)

```bash
ros2 run usv_rtk_bringup gnss_link_monitor --no-rtcm
```

---

## Command-line options

| Flag | Default | Description |
|------|---------|-------------|
| `--topic TOPIC` | _(discover)_ | NavSatFix topic; repeatable; disables GNSS discovery |
| `--rtcm-topic TOPIC` | _(discover)_ | RTCM topic; repeatable; disables RTCM discovery |
| `--rate HZ` | `2` | Terminal refresh rate |
| `--discover-interval SEC` | `3` | Graph scan period |
| `--discover` | **on** | Scan for NavSatFix, AttEuler, and RTCM topics |
| `--no-discover` | — | Require explicit `--topic` / `--rtcm-topic` |
| `--no-rtcm` | off | Hide RTCM section |

```bash
ros2 run usv_rtk_bringup gnss_link_monitor --help
```

---

## Discovery behaviour

| Mode | Behaviour |
|------|-----------|
| Default | Rescan graph every ~3 s; add/remove topics as publishers appear or disappear |
| `--no-discover` + `--topic` | Fixed GNSS list only; still discovers RTCM unless `--rtcm-topic` or `--no-rtcm` |
| `--topic` / `--rtcm-topic` | That stream uses a fixed topic name; other streams still discover unless also pinned |

Example: monitor starts first, then `ntrip_aux_client --publish-rtcm` comes up → RTCM block appears within one scan interval.

---

## Interpreting fix types

### Septentrio `pvtgeodetic.mode` (preferred)

| Mode | Label |
|------|-------|
| 0 | No PVT |
| 1 | Standalone |
| 2 | DGPS |
| 4 | RTK Fixed |
| 5 | RTK Float |

`mean_corr_age > 0` (units 0.01 s) means differential corrections are active.

### NMEA GGA (`gpgga.gps_qual`)

| Quality | Meaning |
|---------|---------|
| 1 | Standalone |
| 2 | DGPS |
| 4 | RTK Fixed |
| 5 | RTK Float |

### `sensor_msgs/NavSatFix` alone

RTK modes are collapsed to `GBAS/DGNSS` — use `pvtgeodetic` or `gpsfix` for RTK Fixed vs Float.

---

## Example output

```
GNSS link monitor
uptime 42s · refresh 2.0 Hz · GNSS 2 · RTCM 1

GNSS sensors
[floatsam0/septentrio]  /floatsam0/septentrio/navsatfix
  Fix:      RTK Fixed (corr 1.2s)
  Position: lat  59.1234567  lon  18.1234567  alt    12.34 m
  Cov ENU:  σE 0.012 m   σN 0.011 m   σU 0.024 m   (known)
  Quality:  SVs 14 · σH 0.02 m · σV 0.03 m · bases 1
  Heading:  h 127.45°  pitch 1.20°  roll -0.30°  SVs 12  σ_h 0.15°  mode 4
  Updated:  120 ms ago

[floatsam0/ublox]  /floatsam0/ublox/fix
  Fix:      Fix
  ...

RTCM streams
[floatsam0/rtcm]  /floatsam0/rtcm
  Rate:     1.05 Hz  (1520 B/s)  active
  Last:     GPS MSM7  342 B  (890 ms ago)
  Recent:   GPS MSM7×5, Galileo MSM7×4

Ctrl-C to exit
```

---

## Related utilities

| Tool | Use when |
|------|----------|
| [verify_rtk_corrections.md](verify_rtk_corrections.md) | Step-by-step RTK proof, A/B test, troubleshooting |
| `check_serial` | USB aliases, receiver firmware, aux NMEA |
| `check_swepos` | NTRIP credentials / stream without hardware |
| `ros2 topic echo` / `ros2 topic hz` | One-off inspection of a single field |

---

## Implementation

- Script: [`utilities/gnss_link_monitor`](../utilities/gnss_link_monitor)
- ROS node: `gnss_link_monitor` (rclpy)
- Dependencies: `sensor_msgs`, `gps_msgs`, `nmea_msgs`, `rtcm_msgs`, `septentrio_gnss_driver` (optional companions)
