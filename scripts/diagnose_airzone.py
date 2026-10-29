"""Long-running Airzone diagnostics. Never log credentials, tokens or device IDs."""
import argparse
import asyncio
import getpass
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import aiohttp
import socketio

BASE = "https://app.airzonecloud.com/api/v1"
WS = "https://prodctrl.airzonecloud.com"
PATH = "api/v1/websockets/conn"


async def main():
    parser = argparse.ArgumentParser(description="Monitor Airzone websocket stability")
    parser.add_argument("--minutes", type=float, default=60)
    parser.add_argument("--output", default="airzone-diagnostics.json")
    parser.add_argument("--reconnect-test", action="store_true",
                        help="Force a reconnect halfway through the run")
    args = parser.parse_args()
    if not 0 < args.minutes <= 1440:
        parser.error("--minutes must be between 0 and 1440")
    start = time.monotonic()
    deadline = start + args.minutes * 60
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_minutes": args.minutes,
        "connections": 0, "disconnects": 0, "energy_events": 0,
        "updates": 0, "max_event_gap_seconds": None,
        "subscription_results": [], "errors": [], "reconnect_test": args.reconnect_test,
    }
    last_event = None

    def record_error(stage, exc):
        # Exception messages may include sensitive URLs. Store only class names.
        report["errors"].append({"stage": stage, "type": type(exc).__name__})
        print(f"{stage}: {type(exc).__name__} (details hidden)")

    def record_event():
        nonlocal last_event
        now = time.monotonic()
        if last_event is not None:
            gap = round(now - last_event, 2)
            report["max_event_gap_seconds"] = max(report["max_event_gap_seconds"] or 0, gap)
        last_event = now

    email = os.environ.get("AIRZONE_EMAIL") or input("Airzone email: ").strip()
    password = os.environ.get("AIRZONE_PASSWORD") or getpass.getpass("Airzone password: ")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.post(BASE + "/auth/login", json={"email": email, "password": password}) as response:
                print(f"Login HTTP {response.status}")
                if response.status != 200:
                    return
                token = (await response.json()).get("token")
                if not isinstance(token, str) or not token:
                    print("Missing token")
                    return
            async with session.get(
                BASE + "/installations", params={"items": 9},
                headers={"Authorization": f"Bearer {token}"},
            ) as response:
                print(f"Installations HTTP {response.status}")
                if response.status != 200:
                    return
                installations = (await response.json()).get("installations", [])
                ids = [item["installation_id"] for item in installations
                       if isinstance(item, dict) and isinstance(item.get("installation_id"), str)]
            print(f"Installations found: {len(ids)}")
            if not ids:
                return

            async def connect_once(run_until):
                client = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
                @client.event
                async def connect():
                    report["connections"] += 1
                    print("WebSocket connected")

                @client.event
                async def disconnect():
                    report["disconnects"] += 1
                    print("WebSocket disconnected")

                @client.on("DEVICE_STATE")
                async def device_state(payload):
                    if isinstance(payload, dict) and payload.get("device_type") == "az_energy_clamp":
                        report["energy_events"] += 1
                        record_event()

                @client.on("*")
                async def dynamic_event(event, *payload):
                    if isinstance(event, str) and event.startswith("DEVICES_UPDATE."):
                        report["updates"] += 1
                        record_event()

                try:
                    await client.connect(
                        WS + "?jwt=" + quote(token, safe=""),
                        socketio_path=PATH, transports=["websocket"], wait_timeout=15,
                    )
                    await client.emit("ready")
                    for stage, installation_id in [
                        ("clear_listeners", None),
                        *[("listen_installation", item) for item in ids],
                    ]:
                        started = time.monotonic()
                        try:
                            if installation_id is None:
                                await client.call(stage, timeout=20)
                            else:
                                await client.call(stage, installation_id, timeout=20)
                            result = "ok"
                        except Exception as exc:
                            result = type(exc).__name__
                            record_error(stage, exc)
                        report["subscription_results"].append({
                            "stage": stage, "result": result,
                            "elapsed_seconds": round(time.monotonic() - started, 2),
                        })
                        print(f"{stage}: {result}")
                        if result != "ok":
                            return
                    while client.connected and time.monotonic() < run_until:
                        await asyncio.sleep(min(5, max(0, run_until - time.monotonic())))
                except Exception as exc:
                    record_error("connection", exc)
                finally:
                    if client.connected:
                        await client.disconnect()

            if args.reconnect_test:
                await connect_once(start + args.minutes * 30)
                if time.monotonic() < deadline:
                    print("Forced reconnect test")
                    await connect_once(deadline)
            else:
                await connect_once(deadline)
    except Exception as exc:
        record_error("http", exc)
    finally:
        report["ended_at"] = datetime.now(timezone.utc).isoformat()
        # Only aggregate statistics and operation labels; never raw payloads.
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Report saved: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
