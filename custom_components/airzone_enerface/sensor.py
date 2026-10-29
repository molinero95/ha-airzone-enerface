"""Dynamic sensors for automatically discovered Airzone energy clamps."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfPower, UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.sensor import RestoreSensor
from datetime import timedelta
import math
import time
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

SENSORS = (
    ("power_total", "Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("current_total", "Current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("voltage_total", "Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
)

async def async_setup_entry(hass, entry, async_add_entities):
    state = hass.data[DOMAIN][entry.entry_id]
    known = set()

    def add_device(device_id):
        if device_id in known:
            return
        known.add(device_id)
        async_add_entities([
            *[EnerfaceSensor(entry, state, device_id, definition) for definition in SENSORS],
            EnerfaceEnergySensor(entry, state, device_id),
        ])

    state["device_listeners"].append(add_device)
    entry.async_on_unload(lambda: state["device_listeners"].remove(add_device))
    for device_id in state["devices"]:
        add_device(device_id)

class EnerfaceSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry, state, device_id, definition):
        self._state = state
        self._device_id = device_id
        self._key, self._attr_name, self._attr_native_unit_of_measurement, self._attr_device_class, self._attr_state_class = definition
        self._attr_unique_id = f"{device_id}_{self._key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"{entry.title} {device_id[-6:]}",
            manufacturer="Airzone",
            model="Enerface",
        )

    @property
    def native_value(self):
        return self._state["devices"].get(self._device_id, {}).get(self._key)

    @property
    def available(self):
        status = self._state["devices"].get(self._device_id, {})
        return self._state["available"] and bool(status.get("isConnected", True))

    async def async_added_to_hass(self):
        self._state["listeners"].append(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        if self.async_write_ha_state in self._state["listeners"]:
            self._state["listeners"].remove(self.async_write_ha_state)


class EnerfaceEnergySensor(RestoreSensor):
    """Accumulate measured power in kWh, preserving the total across restarts.

    This is a locally integrated estimate based on real power measurements, not
    a historical meter register. Gaps while offline are deliberately excluded.
    """

    _attr_has_entity_name = True
    _attr_name = "Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3

    def __init__(self, entry, state, device_id):
        self._state = state
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_energy_total"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"{entry.title} {device_id[-6:]}",
            manufacturer="Airzone",
            model="Enerface",
        )
        self._attr_native_value = 0.0
        self._previous_time = None
        self._previous_power = None

    @property
    def available(self):
        status = self._state["devices"].get(self._device_id, {})
        return self._state["available"] and bool(status.get("isConnected", True))

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        previous = await self.async_get_last_sensor_data()
        if previous is not None:
            try:
                value = float(previous.native_value)
                if math.isfinite(value) and value >= 0:
                    self._attr_native_value = value
            except (ValueError, TypeError):
                pass
        self._state["listeners"].append(self._update_and_write)
        self.async_on_remove(lambda: self._state["listeners"].remove(self._update_and_write))
        self.async_on_remove(async_track_time_interval(
            self.hass, self._periodic_update, timedelta(seconds=60)
        ))
        self._update_and_write()

    @callback
    def _periodic_update(self, now):
        self._update_and_write()

    def _update_and_write(self):
        now = time.monotonic()
        power = self._state["devices"].get(self._device_id, {}).get("power_total")
        if not self.available or not isinstance(power, (int, float)) or isinstance(power, bool) or not math.isfinite(power) or power < 0:
            self._previous_time = None
            self._previous_power = None
        else:
            if self._previous_time is not None:
                seconds = now - self._previous_time
                # Ignore long stalls instead of inventing consumption while offline.
                if 0 <= seconds <= 120:
                    self._attr_native_value += self._previous_power * seconds / 3_600_000
            self._previous_time = now
            self._previous_power = float(power)
        self.async_write_ha_state()
