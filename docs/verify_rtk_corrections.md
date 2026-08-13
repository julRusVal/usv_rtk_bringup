# Verifying RTK corrections

This stack injects RTCM from [`ntrip_aux_client`](../utilities/ntrip_aux_client) on `/dev/usv-rtk-aux` (receiver **USB2**). The Septentrio driver runs on `/dev/usv-rtk` (**USB1**) and must **not** open the aux port.

Corrections flow through three stages. Use the checks below from **upstream → receiver** depending on what you need to prove.

| Stage | What you prove |
|-------|----------------|
| NTRIP client | Caster → host → serial **write** |
| NMEA GGA | Receiver solution type (quick sanity check) |
| Driver PVT topics | Receiver is **using** differential/RTK corrections (best proof) |

**Prerequisites for RTK verification**

```bash
# terminal 1
ros2 launch usv_rtk_bringup rtk.launch.py

# terminal 2 (after a valid GNSS fix — NTRIP is GGA-gated)
ros2 run usv_rtk_bringup ntrip_aux_client --release-port
```

You need sky view (or a valid fix) so `ntrip_aux_client` connects to the caster. Without fix quality ≥ 1, NTRIP stays disconnected by design.

---

## 1. NTRIP path (caster → host → aux serial)

These confirm RTCM reaches the PC and is forwarded to USB2. They do **not** prove the receiver parsed it.

### Client logs

After a valid GGA fix, expect:

```
NTRIP connected to nrtk-swepos.lm.se:8500/MSM_GNSS
```

With `--publish-rtcm`, periodic lines like:

```
Published RTCM #1 (1074, … bytes) on /rtcm
```

### ROS RTCM topic (optional)

```bash
ros2 run usv_rtk_bringup ntrip_aux_client --release-port --publish-rtcm
ros2 topic hz /rtcm
```

Expect a steady rate (mountpoint-dependent, often ~1 Hz for MSM streams).

### SWEPOS credential / stream test (no hardware)

```bash
ros2 run usv_rtk_bringup check_swepos --stream
```

Confirms caster credentials and RTCM stream before touching the receiver.

---

## 2. NMEA GGA fix quality (aux serial / ROS)

GGA **fix quality** indicates how the receiver is solving position.

| Quality | Meaning |
|---------|---------|
| 0 | Invalid / no fix |
| 1 | Standalone GPS |
| **2** | **DGPS — differential corrections in use** |
| **4** | **RTK fixed** |
| **5** | **RTK float** |

### Serial sniff (aux port)

While the driver holds `/dev/usv-rtk`, query only the aux port:

```bash
ros2 run usv_rtk_bringup check_serial --skip-main-query --nmea-seconds 10
```

Or raw NMEA:

```bash
str2str -in serial://usv-rtk-aux:115200:8:n:1 -out stdout: | grep GGA
```

Look at field 6 (fix quality) in `$GPGGA` / `$GNGGA`.

### ROS GGA topic

When `gpgga: true` in `rtk.yaml` / `gnss.yaml`:

```bash
ros2 topic echo /septentrio_gnss_driver/gpgga --once
```

Quality stuck at **1** while NTRIP is connected usually means the receiver is not consuming RTCM (wrong port, port held by another process, or no fix for NTRIP to connect).

---

## 3. Driver PVT topics (strongest receiver-side proof)

With `pvtgeodetic: true` in `rtk.yaml`:

```bash
ros2 topic echo /septentrio_gnss_driver/pvtgeodetic \
  --field mode --field mean_corr_age --field nr_bases --field h_accuracy
```

| Field | Healthy RTK / DGPS signal |
|-------|---------------------------|
| `mean_corr_age` | **> 0** — corrections active (units: **0.01 s**; e.g. `150` ≈ 1.5 s) |
| `mode` | **2** = DGPS, **3** = RTK fixed, **4** = RTK float |
| `nr_bases` | **≥ 1** when using a network RTK base |
| `h_accuracy` | Drops sharply with RTK (cm) vs standalone (m) |

### NavSatFix / GPSFix

```bash
ros2 topic echo /septentrio_gnss_driver/navsatfix --field status
ros2 topic echo /septentrio_gnss_driver/gpsfix --field status --field position_covariance
```

Status and covariance improve when differential/RTK modes are active (exact enum values depend on `gps_common` / driver mapping).

---

## 4. A/B test (most convincing)

1. Run full stack; note GGA quality, `pvtgeodetic.mode`, and `mean_corr_age`.
2. Stop `ntrip_aux_client` (Ctrl-C in terminal 2).
3. Within ~15 s (`--lost-fix-grace`), expect:
   - GGA quality → **1** (standalone)
   - `mean_corr_age` → **0**
   - `mode` → **1** (standalone)
4. Restart `ntrip_aux_client`; values should return to differential/RTK.

If metrics toggle with NTRIP on/off, the receiver **is** receiving and using corrections.

---

## 5. Troubleshooting map

| Symptom | Likely cause |
|---------|----------------|
| No `NTRIP connected` log | No valid fix yet, bad credentials, or aux NMEA missing — run `rtk.launch.py` (not driver-only without aux commands) |
| NTRIP connected but GGA quality stays 1 | Another process holding `/dev/usv-rtk-aux`, or `rtk_settings.serial_1.port` not `USB2` in `rtk.yaml` |
| `Cannot open /dev/usv-rtk-aux` | Stale `cat` / old `str2str` — use `ntrip_aux_client --release-port` |
| RTCM on `/rtcm` but `mean_corr_age` = 0 | Upstream OK; check receiver USB2 config and that driver uses `rtk.launch.py` with `enable_aux_nmea:=true` |
| Driver `sntp, on : Invalid command` | Set `ntp_server: false` in `rtk.yaml` (mosaic-G5) |

---

## Quick checklist

```bash
# 1. Stack running
ros2 launch usv_rtk_bringup rtk.launch.py
ros2 run usv_rtk_bringup ntrip_aux_client --release-port

# 2. NTRIP connected (terminal 2 logs)

# 3. Receiver using corrections
ros2 topic echo /septentrio_gnss_driver/pvtgeodetic --field mean_corr_age --field mode

# 4. Optional cross-check
ros2 topic echo /septentrio_gnss_driver/gpgga --field quality
```
