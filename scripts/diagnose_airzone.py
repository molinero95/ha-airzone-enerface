"""Standalone Airzone Cloud diagnostics. Never print credentials or tokens."""
import asyncio
import getpass
import json
import os

import aiohttp
import socketio

BASE = "https://app.airzonecloud.com/api/v1"
WS = "https://prodctrl.airzonecloud.com"
PATH = "api/v1/websockets/conn"


async def main():
    email = os.environ.get("AIRZONE_EMAIL") or input("Airzone email: ").strip()
    password = os.environ.get("AIRZONE_PASSWORD") or getpass.getpass("Airzone password: ")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        try:
            async with session.post(BASE + "/auth/login", json={"email": email, "password": password}) as response:
                print(f"Login HTTP {response.status}")
                if response.status != 200:
                    return
                body = await response.json()
                token = body.get("token")
                if not isinstance(token, str) or not token:
                    print("Login response lacks a valid token")
                    return
            print("Authentication successful (token hidden)")
            installation_ids = []
            for items in (9, 100):
                async with session.get(
                    BASE + "/installations",
                    params={"items": items},
                    headers={"Authorization": f"Bearer {token}"},
                ) as response:
                    print(f"Installations items={items}: HTTP {response.status}")
                    if response.status != 200:
                        continue
                    payload = await response.json()
                    installation_ids = [
                        item["installation_id"] for item in payload.get("installations", [])
                        if isinstance(item, dict) and isinstance(item.get("installation_id"), str)
                    ]
                    print(f"Installations found: {len(installation_ids)}")
                    break
            if not installation_ids:
                print("No installations discovered; skipping websocket test")
                return
            client = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
            found = asyncio.Event()

            @client.event
            async def connect():
                print("WebSocket connected")

            @client.on("DEVICE_STATE")
            async def device_state(payload):
                if isinstance(payload, dict) and payload.get("device_type") == "az_energy_clamp":
                    status = payload.get("status") or {}
                    print("Enerface received: " + json.dumps({
                        key: status.get(key) for key in ("power_total", "current_total", "voltage_total")
                    }))
                    found.set()

            try:
                await client.connect(
                    WS + "?jwt=" + token,
                    socketio_path=PATH,
                    transports=["websocket"],
                    wait_timeout=15,
                )
                await client.emit("ready")
                await client.call("clear_listeners", timeout=10)
                for installation_id in installation_ids:
                    await client.call("listen_installation", installation_id, timeout=10)
                try:
                    await asyncio.wait_for(found.wait(), timeout=20)
                except asyncio.TimeoutError:
                    print("No Enerface DEVICE_STATE within 20 seconds")
            finally:
                if client.connected:
                    await client.disconnect()
        except (aiohttp.ClientError, asyncio.TimeoutError, socketio.exceptions.SocketIOError) as exc:
            print(f"Diagnostic failed: {type(exc).__name__} (details hidden to protect tokens)")


if __name__ == "__main__":
    asyncio.run(main())
