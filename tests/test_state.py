"""Unit tests for Enerface event processing (no Home Assistant dependency)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "enerface_state",
    Path(__file__).resolve().parents[1] / "custom_components" / "airzone_enerface" / "state.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
apply_device_state = module.apply_device_state
apply_device_update = module.apply_device_update


def test_discovery_and_partial_update():
    devices, ws_ids = {}, {}
    assert apply_device_state(devices, ws_ids, {
        "device_id": "meter1", "device_type": "az_energy_clamp",
        "ws_id": "controller1", "status": {"power_total": 10, "voltage_total": 230}
    }) == "meter1"
    assert apply_device_update(devices, ws_ids, "DEVICES_UPDATE.controller1.meter1", {
        "device_id": "meter1", "change": {"status": {"power_total": 15}}
    })
    assert devices["meter1"] == {"power_total": 15, "voltage_total": 230}


def test_rejects_unrelated_and_malformed_updates():
    devices, ws_ids = {}, {}
    assert apply_device_state(devices, ws_ids, {
        "device_id": "other", "device_type": "az_zone", "status": {}
    }) is None
    apply_device_state(devices, ws_ids, {
        "device_id": "meter1", "device_type": "az_energy_clamp",
        "ws_id": "controller1", "status": {"power_total": 10}
    })
    assert not apply_device_update(devices, ws_ids, "DEVICES_UPDATE.wrong.meter1", {
        "change": {"status": {"power_total": 99}}
    })
    assert not apply_device_update(devices, ws_ids, "DEVICES_UPDATE.controller1.meter1", {
        "device_id": "meter2", "change": {"status": {"power_total": 99}}
    })
    assert not apply_device_update(devices, ws_ids, "DEVICES_UPDATE.controller1.meter1", {
        "change": {"status": None}
    })
    assert devices["meter1"]["power_total"] == 10
