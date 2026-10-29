"""Experimental Airzone Enerface cloud integration."""
import asyncio
import logging
from urllib.parse import quote

import aiohttp
import socketio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, LOGIN_URL, WS_HOST, WS_PATH

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
    state = {"devices": {}, "available": False, "client": client, "listeners": [], "device_listeners": [], "installation_ids": []}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = state

    def notify():
        for callback in list(state["listeners"]):
            callback()

    @client.event
    async def connect():
        state["available"] = True
        notify()
        await client.call("clear_listeners", timeout=10)
        for installation_id in state["installation_ids"]:
            await client.call("listen_installation", installation_id, timeout=10)

    @client.event
    async def disconnect():
        state["available"] = False
        notify()

    @client.on("DEVICE_STATE")
    async def device_state(data):
        if not isinstance(data, dict) or data.get("device_type") != "az_energy_clamp":
            return
        device_id = data.get("device_id")
        status = data.get("status")
        if not isinstance(device_id, str) or not device_id or not isinstance(status, dict):
            return
        is_new = device_id not in state["devices"]
        state["devices"][device_id] = status
        if is_new:
            for callback in list(state["device_listeners"]):
                callback(device_id)
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

    async def discover_installations(session, token):
        async with session.get(
            "https://app.airzonecloud.com/api/v1/installations",
            params={"items": 100},
            headers={"Authorization": f"Bearer {token}"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            response.raise_for_status()
            payload = await response.json()
        installations = payload.get("installations", [])
        if not isinstance(installations, list):
            raise ValueError("Unexpected Airzone installations response")
        ids = [item["installation_id"] for item in installations if isinstance(item, dict) and isinstance(item.get("installation_id"), str)]
        if payload.get("total", len(ids)) > len(ids):
            _LOGGER.warning("Airzone returned a partial installations list; pagination is not implemented")
        return ids

    async def connect_loop():
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    token = await login(session)
                    state["installation_ids"] = await discover_installations(session, token)
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
