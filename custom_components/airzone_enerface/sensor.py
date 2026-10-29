"""Dynamic sensors for automatically discovered Airzone energy clamps."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfPower
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
            EnerfaceSensor(entry, state, device_id, definition)
            for definition in SENSORS
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
