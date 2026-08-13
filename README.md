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

## Launch

Full RTK bringup (Septentrio driver + static TFs):

```bash
ros2 launch usv_rtk_bringup bringup.launch.py
```

Or launch the GNSS stack directly:

```bash
ros2 launch usv_rtk_bringup rtk.launch.py
```

### Launch arguments

| Argument | Default | Description |
|---|---|---|
| `vehicle_config` | `config/usv.yaml` | Vehicle network and extrinsic settings |
| `rtk_params_file` | `config/rtk.yaml` | Septentrio driver parameters |
| `secrets_file` | `config/secrets.yaml` | NTRIP credentials (optional, gitignored) |
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
| `config/rtk.yaml` | Septentrio driver parameters and topic publish flags |
| `config/secrets.yaml.example` | Template for NTRIP caster credentials |

Copy the secrets template and fill in your NTRIP account:

```bash
cp config/secrets.yaml.example config/secrets.yaml
```

Edit `config/usv.yaml` for your receiver IP/port and antenna lever arms. Edit `config/rtk.yaml` for publish rates, datum, and multi-antenna settings.

## Verify

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
│   ├── rtk.yaml
│   ├── secrets.yaml.example
│   └── usv.yaml
└── launch/
    ├── bringup.launch.py
    ├── rtk.launch.py
    └── vehicle_config.py
```
