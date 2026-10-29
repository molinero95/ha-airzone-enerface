"""Experimental Airzone Enerface cloud integration."""
import asyncio
import logging
import random
from urllib.parse import quote

import aiohttp
import socketio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, LOGIN_URL, WS_HOST, WS_PATH
from .state import apply_device_state, apply_device_update

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


class AirzoneRequestError(Exception):
    """HTTP failure with a safe operation label and status, no URLs or tokens."""

    def __init__(self, stage: str, status: int) -> None:
        self.stage = stage
        self.status = status
        super().__init__(f"{stage}: HTTP {status}")

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
    state = {"devices": {}, "available": False, "client": client, "listeners": [], "device_listeners": [], "installation_ids": [], "ws_ids": {}}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = state

    def notify():
        for callback in list(state["listeners"]):
            callback()

    @client.event
    async def connect():
        state["available"] = True
        notify()
        # Do not await acknowledgements inside the connect callback: Socket.IO
        # needs to finish dispatching the connection event first.
        async def subscribe():
            await client.emit("ready")
            await client.call("clear_listeners", timeout=10)
            for installation_id in state["installation_ids"]:
                await client.call("listen_installation", installation_id, timeout=10)
        async def guarded_subscribe():
            try:
                await subscribe()
            except Exception as exc:
                _LOGGER.warning("Airzone subscription failed (%s)", type(exc).__name__)
                await client.disconnect()
        hass.async_create_task(guarded_subscribe(), "Enerface installation subscription")

    @client.event
    async def disconnect():
        state["available"] = False
        notify()

    @client.on("DEVICE_STATE")
    async def device_state(data):
        previous = set(state["devices"])
        device_id = apply_device_state(state["devices"], state["ws_ids"], data)
        if device_id is None:
            return
        if device_id not in previous:
            for callback in list(state["device_listeners"]):
                callback(device_id)
        notify()

    @client.on("*")
    async def on_dynamic_event(event, *args):
        """Socket.IO names updates using controller and device identifiers."""
        if args and apply_device_update(state["devices"], state["ws_ids"], event, args[0]):
            notify()

    async def discover_installations(session, token):
        async with session.get(
            "https://app.airzonecloud.com/api/v1/installations",
            params={"items": 9},
            headers={"Authorization": f"Bearer {token}"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            if response.status >= 400:
                raise AirzoneRequestError("installation discovery", response.status)
            payload = await response.json()
        installations = payload.get("installations", [])
        if not isinstance(installations, list):
            raise ValueError("Unexpected Airzone installations response")
        ids = [item["installation_id"] for item in installations if isinstance(item, dict) and isinstance(item.get("installation_id"), str)]
        if payload.get("total", len(ids)) > len(ids):
            _LOGGER.warning("Airzone returned a partial installations list; pagination is not implemented")
        return ids

    async def refresh(session, refresh_token):
        async with session.get(
            "https://app.airzonecloud.com/api/v1/auth/refreshToken/" + quote(refresh_token, safe=""),
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            if response.status >= 400:
                raise AirzoneRequestError("token refresh", response.status)
            payload = await response.json()
        token = payload.get("token")
        new_refresh = payload.get("refreshToken")
        if not isinstance(token, str) or not token or not isinstance(new_refresh, str) or not new_refresh:
            raise ValueError("Unexpected Airzone refresh response")
        return token, new_refresh

    async def connect_loop():
        async with aiohttp.ClientSession() as session:
            token = None
            refresh_token = None
            retry = 0
            while True:
                try:
                    if refresh_token:
                        try:
                            token, refresh_token = await refresh(session, refresh_token)
                        except AirzoneRequestError as exc:
                            if exc.status not in (401, 403):
                                raise
                            token = None
                            refresh_token = None
                    if not token:
                        async with session.post(
                            LOGIN_URL,
                            json={"email": entry.data[CONF_EMAIL], "password": entry.data[CONF_PASSWORD]},
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as response:
                            if response.status >= 400:
                                raise AirzoneRequestError("login", response.status)
                            payload = await response.json()
                        token = payload.get("token")
                        if not isinstance(token, str) or not token:
                            raise ValueError("Airzone login response has no token")
                        refresh_token = payload.get("refreshToken")
                    state["installation_ids"] = await discover_installations(session, token)
                    retry = 0
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
                except AirzoneRequestError as exc:
                    retry = min(retry + 1, 7)
                    _LOGGER.warning("Airzone Cloud %s failed (HTTP %s); retrying", exc.stage, exc.status)
                except Exception as exc:
                    retry = min(retry + 1, 7)
                    _LOGGER.warning("Airzone cloud connection failed (%s); retrying", type(exc).__name__)
                finally:
                    if client.connected:
                        await client.disconnect()
                    state["available"] = False
                    notify()
                await asyncio.sleep(min(300, 5 * 2 ** retry) + random.uniform(0, 3))

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
