# usv_rtk_bringup — TODO

Tracked follow-ups for GNSS bringup. SBG uses the per-hull vehicle YAML path first; Septentrio is behind.

## Septentrio (vehicle config)

Septentrio launches and `ntrip_aux_client` still read **`config/usv.yaml`** directly. SBG already uses **`config/vehicles/floatsam0.yaml`** via `gnss_stack.yaml` → `vehicle_config`.

- [ ] Point Septentrio launches (`rtk.launch.py`, `gnss.launch.py`, `rtk_heading.launch.py`, `septentrio_launch.py`) at `gnss_stack.yaml` → `vehicle_config` instead of hard-coded `default_vehicle_config_path()` (`config/usv.yaml`).
- [ ] Move Septentrio `network` block (serial devices, aux port, TCP) into per-hull YAML under `config/vehicles/` (e.g. duplicate or split from `floatsam0.yaml`; keep `usv.yaml` as legacy fallback until removed).
- [ ] Wire `all_gnss.launch.py` to pass the same `vehicle_config` to Septentrio children (today only SBG gets `sbg_vehicle_config`).
- [ ] Update `gnss_stack.py` so NTRIP `--vehicle-config` uses the per-hull file when `module:=septentrio` (aux serial paths must match the hull).
- [ ] Document migration: edit `config/vehicles/<hull>.yaml` for geometry + receiver serial; keep `config/rtk.yaml` / `config/gnss.yaml` for driver tuning only.
- [ ] Remove duplicated extrinsics from `config/usv.yaml` once Septentrio is on per-hull YAML (or keep `usv.yaml` as a thin Septentrio-only template).

## Done (SBG)

- [x] `config/vehicles/floatsam0.yaml` — per-hull extrinsics + SBG serial.
- [x] `build_sbg_param_overlay()` — merge vehicle YAML into `sbg_driver` params at launch.
- [x] `sbg.launch.py` + `gnss_stack.yaml` → `vehicle_config`.
- [x] `ntrip_ros_client` — ROS NMEA in, ROS RTCM out (GGA-gated NTRIP for SBG).
- [x] [docs/sbg.md](sbg.md) — SBG usage and configuration guide.
