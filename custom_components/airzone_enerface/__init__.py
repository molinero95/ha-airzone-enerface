"""Experimental Airzone Enerface cloud integration."""
import asyncio
import logging
from urllib.parse import quote

import aiohttp
import socketio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_DEVICE_ID, LOGIN_URL, WS_HOST, WS_PATH

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
    state = {"status": {}, "available": False, "client": client, "listeners": []}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = state

    def notify():
        for callback in list(state["listeners"]):
            callback()

    @client.event
    async def connect():
        state["available"] = True
        notify()

    @client.event
    async def disconnect():
        state["available"] = False
        notify()

    @client.on("DEVICE_STATE")
    async def device_state(data):
        if not isinstance(data, dict) or data.get("device_id") != entry.data[CONF_DEVICE_ID]:
            return
        status = data.get("status")
        if isinstance(status, dict):
            state["status"] = status
            notify()

    async def login(session):
        async with session.post(
            LOGIN_URL,
            json={"email": entry.data[CONF_EMAIL], "password": entry.data[CONF_PASSWORD]},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            response.raise_for_status()
            payload = await response.json()
            token = payload.get("token")
            if not isinstance(token, str) or not token:
                raise ValueError("Airzone login response has no access token")
            return token

    async def connect_loop():
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    token = await login(session)
                    url = WS_HOST + "?jwt=" + quote(token, safe="")
                    await client.connect(
                        url,
                        socketio_path=WS_PATH,
                        transports=["websocket"],
                        wait_timeout=15,
                    )
                    await client.wait()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    _LOGGER.warning("Airzone cloud connection failed (%s); retrying", type(exc).__name__)
                finally:
                    if client.connected:
                        await client.disconnect()
                    state["available"] = False
                    notify()
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
