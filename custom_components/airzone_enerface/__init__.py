"""Experimental cloud-push integration for Airzone Enerface."""
import asyncio
import logging
import socketio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_TOKEN, CONF_DEVICE_ID, WS_URL

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = socketio.AsyncClient(reconnection=True, reconnection_delay=2, reconnection_delay_max=60, logger=False)
    state = {"status": {}, "available": False, "client": client, "listeners": []}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = state

    @client.event
    async def connect():
        state["available"] = True
        for callback in list(state["listeners"]):
            callback()

    @client.event
    async def disconnect():
        state["available"] = False
        for callback in list(state["listeners"]):
            callback()

    @client.on("DEVICE_STATE")
    async def device_state(data):
        if not isinstance(data, dict) or data.get("device_id") != entry.data[CONF_DEVICE_ID]:
            return
        status = data.get("status")
        if isinstance(status, dict):
            state["status"] = status
            for callback in list(state["listeners"]):
                callback()

    async def connect_loop():
        # Socket.IO client handles reconnects after an established connection.
        # Initial failures are retried here; token refresh is not yet implemented.
        while True:
            try:
                await client.connect(
                    WS_URL,
                    socketio_path="api/v1/websockets/conn",
                    transports=["websocket"],
                    headers={"Authorization": f"Bearer {entry.data[CONF_TOKEN]}"},
                    wait_timeout=15,
                )
                await client.wait()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _LOGGER.warning("Enerface connection failed (%s); retrying", type(exc).__name__)
            await asyncio.sleep(30)

    state["task"] = entry.async_create_background_task(hass, connect_loop(), "Enerface websocket")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        state = hass.data[DOMAIN].pop(entry.entry_id)
        state["task"].cancel()
        await state["client"].disconnect()
    return unloaded
