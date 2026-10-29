"""Pure helpers for Airzone device events."""
from collections.abc import Mapping

ENERFACE_TYPE = "az_energy_clamp"


def apply_device_state(devices, ws_ids, payload):
    """Apply a complete Enerface snapshot; return its device ID if valid."""
    if not isinstance(payload, Mapping) or payload.get("device_type") != ENERFACE_TYPE:
        return None
    device_id, status = payload.get("device_id"), payload.get("status")
    if not isinstance(device_id, str) or not device_id or not isinstance(status, dict):
        return None
    devices[device_id] = status.copy()
    if isinstance(payload.get("ws_id"), str):
        ws_ids[device_id] = payload["ws_id"]
    return device_id


def apply_device_update(devices, ws_ids, event, payload):
    """Merge a partial update only for a known device and controller."""
    if not isinstance(event, str) or not event.startswith("DEVICES_UPDATE."):
        return False
    parts = event.split(".")
    if len(parts) != 3:
        return False
    _, ws_id, device_id = parts
    if device_id not in devices or ws_ids.get(device_id) != ws_id:
        return False
    if not isinstance(payload, Mapping) or payload.get("device_id") not in (None, device_id):
        return False
    change = payload.get("change")
    if not isinstance(change, Mapping):
        return False
    status = change.get("status")
    if not isinstance(status, Mapping):
        return False
    devices[device_id].update(status)
    return True
