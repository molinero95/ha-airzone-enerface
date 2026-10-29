"""Live Enerface sensors from DEVICE_STATE events."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfPower
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_DEVICE_ID

SENSORS = (
    ("power_total", "Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("current_total", "Current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    ("voltage_total", "Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
)

async def async_setup_entry(hass, entry, async_add_entities):
    state = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EnerfaceSensor(entry, state, item) for item in SENSORS])

class EnerfaceSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry, state, definition):
        self._entry = entry
        self._state = state
        self._key, self._attr_name, self._attr_native_unit_of_measurement, self._attr_device_class, self._attr_state_class = definition
        device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{device_id}_{self._key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)}, name=entry.title, manufacturer="Airzone", model="Enerface")

    @property
    def native_value(self):
        return self._state["status"].get(self._key)

    @property
    def available(self):
        return self._state["available"] and bool(self._state["status"].get("isConnected", True))

    async def async_added_to_hass(self):
        self._state["listeners"].append(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self._state["listeners"].remove(self.async_write_ha_state)
